import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from .aggregation import generate_daily_report


logger = logging.getLogger(__name__)


def _risk_score(data: Dict[str, Any], config: Optional[models.DeviceConfig]) -> float:
    avg_lux = float(data.get("avg_lux") or 0)
    poor_ratio = float(data.get("poor_light_ratio") or 0)
    max_sit = float(data.get("max_sit_cont_min") or 0)
    avg_humidity = float(data.get("avg_humidity") or 50)
    avg_temperature = float(data.get("avg_temperature") or 24)
    high_threshold = float(config.lux_max if config else 1000)

    score = 0.08
    if avg_lux < 300:
        score += 0.22 * min(1.0, (300 - avg_lux) / 300)
    if avg_lux > high_threshold:
        score += 0.18 * min(1.0, (avg_lux - high_threshold) / max(high_threshold, 1))
    score += 0.30 * min(1.0, poor_ratio)
    score += 0.35 * min(1.0, max_sit / 60)
    if avg_humidity < 40 or avg_humidity > 70:
        score += 0.08
    if avg_temperature < 18 or avg_temperature > 26:
        score += 0.08
    return round(min(0.99, score), 2)


def _risk_level(score: float) -> str:
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _build_insights(
    data: Dict[str, Any],
    config: Optional[models.DeviceConfig],
    level: str,
) -> List[Dict[str, str]]:
    insights: List[Dict[str, str]] = []
    avg_lux = data.get("avg_lux")
    poor_ratio = float(data.get("poor_light_ratio") or 0)
    max_sit = int(data.get("max_sit_cont_min") or 0)
    avg_humidity = float(data.get("avg_humidity") or 50)
    avg_temperature = float(data.get("avg_temperature") or 24)
    high_threshold = config.lux_max if config else 1000
    warn_threshold = config.sit_warn_min if config else 45
    strong_threshold = config.sit_strong_min if config else 60

    if avg_lux is not None and avg_lux < 300:
        insights.append(
            {
                "title": "光照偏低",
                "detail": (
                    f"平均照度 {avg_lux} lux，偏低光照占比 "
                    f"{round(poor_ratio * 100)}%。建议优先改善读写区域照明。"
                ),
                "level": "warn",
            }
        )
    if avg_lux is not None and avg_lux > high_threshold:
        insights.append(
            {
                "title": "强光或眩光风险",
                "detail": (
                    f"平均照度 {avg_lux} lux，高于设定上限 "
                    f"{high_threshold} lux，注意窗帘和台灯角度。"
                ),
                "level": "warn",
            }
        )
    if max_sit >= strong_threshold:
        insights.append(
            {
                "title": "连续久坐时间偏长",
                "detail": (
                    f"最长连续久坐 {max_sit} 分钟，超过强提醒阈值 "
                    f"{strong_threshold} 分钟。"
                ),
                "level": "high",
            }
        )
    elif max_sit >= warn_threshold:
        insights.append(
            {
                "title": "久坐接近提醒阈值",
                "detail": (
                    f"最长连续久坐 {max_sit} 分钟，已达到轻提醒阈值 "
                    f"{warn_threshold} 分钟。"
                ),
                "level": "warn",
            }
        )
    if avg_humidity < 40 or avg_humidity > 70:
        insights.append(
            {
                "title": "湿度不在舒适区",
                "detail": f"平均湿度 {avg_humidity}%，建议通风或使用加湿器。",
                "level": "warn",
            }
        )
    if avg_temperature < 18 or avg_temperature > 26:
        insights.append(
            {
                "title": "温度偏离舒适区",
                "detail": f"平均温度 {avg_temperature}°C，注意空调或通风。",
                "level": "warn",
            }
        )
    if not insights:
        insights.append(
            {
                "title": "整体状态稳定",
                "detail": "今日光照、久坐和温湿度均处于相对可控区间。",
                "level": "good",
            }
        )
    elif level == "high":
        insights.insert(
            0,
            {
                "title": "综合风险偏高",
                "detail": "多项指标叠加，建议优先安排休息和光照调整。",
                "level": "high",
            },
        )
    return insights


def _build_recommendations(
    data: Dict[str, Any], config: Optional[models.DeviceConfig]
) -> List[str]:
    recommendations: List[str] = []
    avg_lux = data.get("avg_lux")
    max_sit = int(data.get("max_sit_cont_min") or 0)
    avg_humidity = float(data.get("avg_humidity") or 50)
    strong_threshold = config.sit_strong_min if config else 60

    if avg_lux is not None and avg_lux < 300:
        recommendations.append("把台灯调亮一档，或把工位移到更靠窗的位置")
    if avg_lux is not None and avg_lux > (config.lux_max if config else 1000):
        recommendations.append("拉上窗帘或调整台灯角度，避免直射和眩光")
    if max_sit >= strong_threshold:
        recommendations.append("立即起身活动 5 分钟，并设置 45 分钟久坐提醒")
    else:
        recommendations.append("每工作 45-60 分钟起身活动 5 分钟")
    if avg_humidity < 40 or avg_humidity > 70:
        recommendations.append("通风或使用加湿器，把湿度保持在 40%-70%")
    recommendations.append("下午安排一次 5 分钟远眺，放松眼部调节")
    return recommendations


def _maybe_llm(
    data: Dict[str, Any],
    insights: List[Dict[str, str]],
    recommendations: List[str],
    risk_level: str,
) -> Optional[Dict[str, Any]]:
    if not settings.llm_api_url or not settings.llm_api_key:
        return None
    prompt = {
        "task": "根据工位用眼健康数据生成简洁中文日报",
        "requirements": {
            "output": "JSON",
            "fields": ["summary", "risk_level", "insights", "recommendations"],
            "insights_item": {"title": "string", "detail": "string", "level": "good|warn|high"},
            "avoid": "不要做医疗诊断，只给用眼负担和行为建议",
        },
        "stats": data,
        "rule_insights": insights,
        "rule_recommendations": recommendations,
        "rule_risk_level": risk_level,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                settings.llm_api_url,
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model or "default",
                    "temperature": settings.llm_temperature,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是工位用眼健康分析助手，只输出 JSON。",
                        },
                        {
                            "role": "user",
                            "content": json.dumps(prompt, ensure_ascii=False),
                        },
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if "```" in content:
                content = content.replace("```json", "").replace("```", "").strip()
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                content = content[start : end + 1]
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM report failed, fallback to rules: %s", exc)
    return None


def generate_ai_report(
    db: Session, device_id: str, report_date: date
) -> Optional[models.Report]:
    report = generate_daily_report(db, device_id, report_date)
    if report is None:
        return None

    config = db.get(models.DeviceConfig, device_id)
    data = dict(report.data or {})
    score = _risk_score(data, config)
    level = _risk_level(score)
    insights = _build_insights(data, config, level)
    recommendations = _build_recommendations(data, config)
    summary = (
        f"{report_date.isoformat()} 共记录 {data.get('sample_count', 0)} 条数据；"
        f"平均照度 {data.get('avg_lux', '--')} lux，"
        f"最长连续久坐 {data.get('max_sit_cont_min', 0)} 分钟；"
        f"综合风险 {level}。"
        f"建议：{'；'.join(recommendations[:3])}。"
    )
    source = "rule+risk-model"

    llm = _maybe_llm(data, insights, recommendations, level)
    if llm:
        if isinstance(llm.get("summary"), str):
            summary = llm["summary"]
        if llm.get("risk_level") in {"low", "medium", "high"}:
            level = llm["risk_level"]
        if isinstance(llm.get("insights"), list):
            insights = llm["insights"]
        if isinstance(llm.get("recommendations"), list):
            recommendations = [str(item) for item in llm["recommendations"]]
        source = "llm"

    data.update(
        {
            "risk": score,
            "risk_level": level,
            "insights": insights,
            "recommendations": recommendations,
            "source": source,
            "generated_at": models.utcnow().isoformat(),
        }
    )
    report.data = data
    report.summary = summary
    report.risk_level = level
    db.commit()
    db.refresh(report)
    return report
