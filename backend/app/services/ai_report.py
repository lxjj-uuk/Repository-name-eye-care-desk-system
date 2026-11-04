import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from .aggregation import generate_daily_report
from .ai_context import build_ai_context
from .ai_memory import get_or_create_memory
from .ai_tools import TOOL_DEFINITIONS, normalize_actions
from .knowledge import retrieve_knowledge
from .local_llm import (
    generate_json as generate_local_json,
    get_model_name as get_local_model_name,
    is_available as local_llm_available,
)


logger = logging.getLogger(__name__)


def _risk_score(data: Dict[str, Any], config: Optional[models.DeviceConfig]) -> float:
    avg_lux = float(data.get("avg_lux") or 0)
    poor_ratio = float(
        data.get("poor_light_occupied_ratio")
        if data.get("poor_light_occupied_ratio") is not None
        else data.get("poor_light_ratio")
        or 0
    )
    max_sit = float(data.get("max_sit_cont_min") or 0)
    avg_humidity = float(data.get("avg_humidity") or 50)
    avg_temperature = float(data.get("avg_temperature") or 24)
    high_threshold = float(config.lux_max if config else 1000)
    occupied_ratio = data.get("occupied_ratio")
    high_risk_ratio = float(data.get("high_risk_ratio") or 0)

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
    if high_risk_ratio > 0:
        score += 0.10 * min(1.0, high_risk_ratio)
    if isinstance(occupied_ratio, (int, float)):
        score *= 0.75 + 0.25 * min(1.0, max(0.0, occupied_ratio))
    return round(min(0.99, score), 2)


def _risk_level(score: float) -> str:
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _build_signals(
    data: Dict[str, Any],
    config: Optional[models.DeviceConfig],
) -> List[Dict[str, str]]:
    signals: List[Dict[str, str]] = []
    avg_lux = data.get("avg_lux")
    poor_light_ratio = float(data.get("poor_light_ratio") or 0)
    occupied_poor_ratio = data.get(
        "poor_light_occupied_ratio"
    )
    effective_poor_ratio = (
        float(occupied_poor_ratio)
        if occupied_poor_ratio is not None
        else poor_light_ratio
    )
    max_sit = int(data.get("max_sit_cont_min") or 0)
    avg_humidity = float(data.get("avg_humidity") or 50)
    avg_temperature = float(data.get("avg_temperature") or 24)
    occupied_ratio = data.get("occupied_ratio")
    lux_min = config.lux_min if config else 150
    lux_max = config.lux_max if config else 1000
    sit_warn = config.sit_warn_min if config else 45

    if effective_poor_ratio >= 0.3:
        signals.append(
            {
                "key": "light",
                "level": "warn",
                "fact": (
                    f"在座时低照度占比 {round(effective_poor_ratio * 100)}%，"
                    f"平均照度 {avg_lux} lux，舒适下限 {lux_min} lux"
                ),
            }
        )
    elif avg_lux is not None and float(avg_lux) > lux_max:
        signals.append(
            {
                "key": "light",
                "level": "warn",
                "fact": f"平均照度 {avg_lux} lux，超过上限 {lux_max} lux",
            }
        )
    if max_sit >= sit_warn:
        signals.append(
            {
                "key": "sitting",
                "level": "high" if max_sit >= 60 else "warn",
                "fact": f"最长连续久坐 {max_sit} 分钟，提醒阈值 {sit_warn} 分钟",
            }
        )
    if avg_humidity < 40 or avg_humidity > 70:
        signals.append(
            {
                "key": "humidity",
                "level": "warn",
                "fact": f"平均湿度 {avg_humidity}%，舒适区为 40%-70%",
            }
        )
    if avg_temperature < 18 or avg_temperature > 26:
        signals.append(
            {
                "key": "temperature",
                "level": "warn",
                "fact": f"平均温度 {avg_temperature}°C，舒适区为 18-26°C",
            }
        )
    if (
        isinstance(occupied_ratio, (int, float))
        and data.get("sample_count", 0) >= 20
        and occupied_ratio < 0.05
    ):
        signals.append(
            {
                "key": "data_quality",
                "level": "warn",
                "fact": f"在座样本仅占 {round(occupied_ratio * 100)}%，结论可信度有限",
            }
        )

    if not signals:
        signals.append(
            {
                "key": "stable",
                "level": "good",
                "fact": (
                    f"平均照度 {avg_lux} lux，平均湿度 {avg_humidity}%，"
                    f"最长连续久坐 {max_sit} 分钟，均在舒适区间"
                ),
            }
        )
    return signals


def _build_insights(
    data: Dict[str, Any],
    config: Optional[models.DeviceConfig],
    level: str,
) -> List[Dict[str, str]]:
    insights: List[Dict[str, str]] = []
    avg_lux = data.get("avg_lux")
    poor_ratio = float(data.get("poor_light_ratio") or 0)
    occupied_poor_ratio = float(
        data.get("poor_light_occupied_ratio")
        if data.get("poor_light_occupied_ratio") is not None
        else poor_ratio
    )
    max_sit = int(data.get("max_sit_cont_min") or 0)
    avg_humidity = float(data.get("avg_humidity") or 50)
    avg_temperature = float(data.get("avg_temperature") or 24)
    high_threshold = config.lux_max if config else 1000
    warn_threshold = config.sit_warn_min if config else 45
    strong_threshold = config.sit_strong_min if config else 60
    occupied_ratio = data.get("occupied_ratio")
    coverage = data.get("coverage") if isinstance(data.get("coverage"), dict) else {}

    if avg_lux is not None and avg_lux < 300:
        detail = (
            f"平均照度 {avg_lux} lux，偏低光照占比 "
            f"{round(poor_ratio * 100)}%。"
        )
        if occupied_poor_ratio > poor_ratio:
            detail += f"在座时低照光占比达到 {round(occupied_poor_ratio * 100)}%，实际用眼暴露更集中。"
        else:
            detail += "建议优先改善读写区域照明。"
        insights.append(
            {
                "title": "光照偏低",
                "detail": detail,
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
    if (
        isinstance(occupied_ratio, (int, float))
        and data.get("sample_count", 0) >= 20
        and occupied_ratio < 0.05
    ):
        insights.append(
            {
                "title": "在座样本不足",
                "detail": (
                    f"今日有人样本仅占 {round(occupied_ratio * 100)}%，"
                    "久坐和用眼暴露结论的置信度较低，需要先确认人体感应器状态。"
                ),
                "level": "warn",
            }
        )
    if coverage and any(
        isinstance(value, (int, float)) and value < 0.8
        for value in coverage.values()
    ):
        insights.append(
            {
                "title": "传感器数据不完整",
                "detail": "部分传感器覆盖率低于 80%，平均值可能无法代表全天真实状态。",
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


def _build_prompt(
    data: Dict[str, Any],
    config: Optional[models.DeviceConfig],
    signals: List[Dict[str, str]],
    context: Dict[str, Any],
    knowledge: List[Dict[str, Any]],
) -> Dict[str, Any]:
    raw_curve = list(context.get("recent_light_curve") or [])[-8:]
    last_command = context.get("last_command") or {}
    prompt_context = {
        "current": context.get("current"),
        "recent_light_curve": [
            [
                str(item.get("ts") or "")[11:16],
                item.get("lux"),
                item.get("occupied"),
            ]
            for item in raw_curve
        ],
        "time_context": context.get("time_context"),
        "last_command": {
            key: last_command.get(key)
            for key in ("name", "status", "result", "acked_at")
        }
        if last_command
        else None,
        "user_memory": context.get("user_memory"),
        "data_quality": {
            key: (context.get("data_quality") or {}).get(key)
            for key in ("sample_count", "coverage", "device_online")
        },
    }
    compact_tools = [
        {
            "name": item["name"],
            "kind": item["kind"],
            **({"params": item["params"]} if "params" in item else {}),
        }
        for item in TOOL_DEFINITIONS
    ]
    return {
        "task": "根据工位用眼健康数据生成可执行的中文深度分析",
        "requirements": {
            "output": "JSON",
            "summary": "80-120字，引用两个真实数值，不写风险等级",
            "insights": "恰好2条，每条含 title/detail/level",
            "recommendations": "恰好2条纯字符串，是今天可直接执行的动作",
            "avoid": (
                "不做医疗诊断，不虚构数据，不输出 Markdown；"
                "occupied_ratio 是在座样本占比，不是拥挤率"
            ),
            "proposed_actions": (
                "最多1个动作，无必要时为空；只能使用 tools，不能声称已执行"
            ),
            "action_item": {
                "tool": "buzz|set_thresholds",
                "reason": "为什么现在需要这个动作",
                "params": "符合 tools 参数约束的对象",
            },
        },
        "stats": data,
        "signals": signals,
        "live_context": prompt_context,
        "knowledge": knowledge,
        "tools": compact_tools,
        "signal_rule": (
            "只分析 signals 中的项目。signals 为 stable 时，所有指标均健康，"
            "不要编造任何不足、低湿度、久坐过长或其他风险。"
        ),
        "field_notes": {
            "sample_count": "采样点数量，不是人数",
            "occupied_ratio": "在座样本占比，不是拥挤率",
            "poor_light_occupied_ratio": "在座时低照度样本占比，是光照风险的主要依据",
            "max_sit_cont_min": "最长连续久坐分钟数",
            "coverage": "有效数据覆盖比例，低于0.8可信度有限",
            "knowledge": "RAG知识，id可用于判断依据",
        },
        "thresholds": {
            "lux_min": config.lux_min if config else 150,
            "lux_max": config.lux_max if config else 1000,
            "sit_warn_min": config.sit_warn_min if config else 45,
            "sit_strong_min": config.sit_strong_min if config else 60,
        },
    }


def _parse_llm_content(
    content: str,
    signals: List[Dict[str, str]],
    risk_level: str,
) -> Optional[Dict[str, Any]]:
    if "```" in content:
        content = content.replace("```json", "").replace("```", "").strip()
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        content = content[start : end + 1]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON")
        return None
    if not isinstance(parsed, dict):
        return None

    normalized_insights: List[Dict[str, str]] = []
    for item in parsed.get("insights", []):
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        detail = item.get("detail")
        level = item.get("level")
        if not isinstance(title, str) or not isinstance(detail, str):
            continue
        if level not in {"good", "warn", "high"}:
            level = "warn"
        normalized_insights.append(
            {
                "title": title.strip()[:60],
                "detail": detail.strip()[:300],
                "level": level,
            }
        )
    normalized_recommendations = [
        str(item).strip()[:200]
        for item in parsed.get("recommendations", [])
        if str(item).strip()
    ][:4]
    if (
        len(normalized_recommendations) == 2
        and normalized_recommendations[0].lower().startswith(("title:", "title："))
        and normalized_recommendations[1].lower().startswith(
            ("description:", "description：")
        )
    ):
        title = normalized_recommendations[0].split(":", 1)[-1].split("：", 1)[-1]
        description = (
            normalized_recommendations[1]
            .split(":", 1)[-1]
            .split("：", 1)[-1]
        )
        normalized_recommendations = [
            f"{title.strip()}：{description.strip()}"[:200]
        ]
    summary = parsed.get("summary")
    if (
        not normalized_insights
        or not normalized_recommendations
        or not isinstance(summary, str)
        or not summary.strip()
    ):
        logger.warning("LLM report rejected: incomplete structured content")
        return None

    parsed["summary"] = summary.strip()[:500]
    parsed["insights"] = normalized_insights
    parsed["recommendations"] = normalized_recommendations
    if risk_level == "low" and any(
        signal["key"] == "stable" for signal in signals
    ):
        combined = parsed["summary"] + "".join(
            item["detail"] for item in normalized_insights
        )
        negative_terms = (
            "不足",
            "偏低",
            "过高",
            "低照",
            "久坐过长",
            "需要改善",
            "需引起",
        )
        if any(term in combined for term in negative_terms):
            logger.warning("LLM report contradicted healthy signals")
            return None
        for item in normalized_insights:
            item["level"] = "good"
    return parsed


def _maybe_llm(
    data: Dict[str, Any],
    risk_level: str,
    config: Optional[models.DeviceConfig],
    context: Dict[str, Any],
    knowledge: List[Dict[str, Any]],
) -> Optional[Tuple[Dict[str, Any], str, str]]:
    if not settings.llm_api_url and not local_llm_available():
        return None

    signals = _build_signals(data, config)
    if len(signals) == 1 and signals[0]["key"] == "stable":
        return None
    prompt = _build_prompt(data, config, signals, context, knowledge)
    messages = [
        {
            "role": "system",
            "content": (
                "你是工位用眼健康分析助手。根据真实统计数据给出"
                "具体、有因果关系的分析和行动建议。读取 live_context、"
                "knowledge 和 user_memory；控制动作必须留给用户确认。"
                "只输出合法 JSON。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(prompt, ensure_ascii=False),
        },
    ]

    local_content = generate_local_json(
        messages,
        settings.llm_max_tokens,
        settings.llm_temperature,
    )
    if local_content:
        parsed = _parse_llm_content(local_content, signals, risk_level)
        if parsed:
            return parsed, get_local_model_name(), "local"

    if not settings.llm_api_url:
        return None
    try:
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"
        with httpx.Client(timeout=settings.llm_timeout_s) as client:
            response = client.post(
                settings.llm_api_url,
                headers=headers,
                json={
                    "model": settings.llm_model or "default",
                    "temperature": settings.llm_temperature,
                    "max_tokens": settings.llm_max_tokens,
                    "stream": False,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = _parse_llm_content(content, signals, risk_level)
            if parsed:
                return parsed, settings.llm_model or "remote-llm", "api"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Remote LLM report failed, fallback to rules: %s", exc)
    return None


def _build_evidence(
    signals: List[Dict[str, str]],
    knowledge: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    source_ids = [item["id"] for item in knowledge[:2]]
    return [
        {
            "fact": signal["fact"],
            "level": signal["level"],
            "knowledge_ids": source_ids,
        }
        for signal in signals[:4]
    ]


def _fallback_actions(
    level: str,
    signals: List[Dict[str, str]],
    context: Dict[str, Any],
    config: Optional[models.DeviceConfig],
) -> List[Dict[str, Any]]:
    current = context.get("current") or {}
    time_context = context.get("time_context") or {}
    memory = context.get("user_memory") or {}
    if (
        not current.get("occupied")
        or (context.get("data_quality") or {}).get("device_online") is False
        or not config
        or not config.buzzer_enabled
        or time_context.get("is_quiet_time")
        or memory.get("preferred_reminder") == "visual"
    ):
        return []
    if not any(signal["level"] in {"warn", "high"} for signal in signals):
        return []
    return [
        {
            "tool": "buzz",
            "reason": "当前有人且存在需要即时关注的环境信号",
            "params": {"pattern": "short", "duration_ms": 250},
        }
    ]


def _persist_ai_actions(
    db: Session,
    device_id: str,
    actions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    (
        db.query(models.Command)
        .filter(
            models.Command.device_id == device_id,
            models.Command.requested_by == "ai",
            models.Command.status == "pending",
        )
        .update({"status": "cancelled"}, synchronize_session=False)
    )
    persisted: List[Dict[str, Any]] = []
    for action in actions:
        command = models.Command(
            device_id=device_id,
            command_name=action["command_name"],
            params=action["params"],
            status="pending",
            request_id=uuid4().hex,
            requested_by="ai",
        )
        db.add(command)
        db.flush()
        persisted.append(
            {
                **action,
                "command_id": command.id,
                "status": command.status,
                "confirmation_required": True,
            }
        )
    return persisted


def generate_ai_report(
    db: Session, device_id: str, report_date: date
) -> Optional[models.Report]:
    report = generate_daily_report(db, device_id, report_date)
    if report is None:
        return None

    config = db.get(models.DeviceConfig, device_id)
    data = dict(report.data or {})
    memory = get_or_create_memory(db, device_id)
    context = build_ai_context(db, device_id, report_date, config, data)
    signals = _build_signals(data, config)
    knowledge = retrieve_knowledge(signals, context, limit=3)
    evidence = _build_evidence(signals, knowledge)
    score = _risk_score(data, config)
    level = _risk_level(score)
    insights = _build_insights(data, config, level)
    recommendations = _build_recommendations(data, config)
    level_label = {"high": "偏高", "medium": "中等", "low": "平稳"}[level]
    summary = (
        f"{report_date.isoformat()} 共记录 {data.get('sample_count', 0)} 条数据；"
        f"平均照度 {data.get('avg_lux', '--')} lux，"
        f"最长连续久坐 {data.get('max_sit_cont_min', 0)} 分钟；"
        f"综合风险{level_label}。"
        f"建议：{'；'.join(recommendations[:3])}。"
    )
    source = "rule+risk-model"

    llm_result = _maybe_llm(data, level, config, context, knowledge)
    model_name: Optional[str] = None
    engine: Optional[str] = None
    raw_actions: Any = []
    if llm_result:
        llm, model_name, engine = llm_result
        if isinstance(llm.get("summary"), str):
            summary = llm["summary"]
        if isinstance(llm.get("insights"), list):
            insights = llm["insights"]
        if isinstance(llm.get("recommendations"), list):
            recommendations = [str(item) for item in llm["recommendations"]]
        raw_actions = llm.get("proposed_actions", [])
        source = "llm"

    actions = normalize_actions(raw_actions, config, context, limit=1)
    if not actions:
        actions = normalize_actions(
            _fallback_actions(level, signals, context, config),
            config,
            context,
            limit=1,
        )

    data.update(
        {
            "risk": score,
            "risk_level": level,
            "insights": insights,
            "recommendations": recommendations,
            "source": source,
            "model": model_name,
            "engine": engine,
            "generated_at": models.utcnow().isoformat() + "Z",
            "signals": signals,
            "evidence": evidence,
            "knowledge_sources": knowledge,
            "ai_context": context,
            "user_memory": context.get("user_memory", {}),
            "tool_trace": [
                {
                    "tool": "get_light_curve",
                    "kind": "read",
                    "points": len(context.get("recent_light_curve") or []),
                },
                {
                    "tool": "get_sitting_summary",
                    "kind": "read",
                    "max_contiguous_min": (
                        context.get("sitting_summary") or {}
                    ).get("max_contiguous_min", 0),
                },
            ],
        }
    )
    report.summary = summary
    report.risk_level = level
    data["proposed_actions"] = _persist_ai_actions(db, device_id, actions)
    data["tool_trace"].extend(
        {
            "tool": action["tool"],
            "kind": "confirm",
            "command_id": action["command_id"],
        }
        for action in data["proposed_actions"]
    )
    report.data = dict(data)
    db.commit()
    db.refresh(report)
    return report
