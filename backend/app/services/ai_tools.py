from typing import Any, Dict, List, Optional

from .. import models


TOOL_DEFINITIONS = [
    {
        "name": "get_light_curve",
        "kind": "read",
        "description": "读取近期光照曲线",
    },
    {
        "name": "get_sitting_summary",
        "kind": "read",
        "description": "读取久坐统计",
    },
    {
        "name": "buzz",
        "kind": "confirm",
        "description": "执行蜂鸣提醒",
        "params": {"pattern": "short|long|double", "duration_ms": "50-5000"},
    },
    {
        "name": "set_thresholds",
        "kind": "confirm",
        "description": "调整光照或久坐阈值",
        "params": {
            "lux_min": "0-200000",
            "lux_max": "0-200000",
            "sit_warn_min": "1-240",
            "sit_strong_min": "1-240",
        },
    },
]


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_action(
    proposal: Dict[str, Any],
    config: Optional[models.DeviceConfig],
    context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    tool = str(proposal.get("tool") or proposal.get("name") or "").strip()
    reason = str(proposal.get("reason") or "").strip()[:200]
    params = proposal.get("params") if isinstance(proposal.get("params"), dict) else {}
    current = context.get("current") or {}
    quality = context.get("data_quality") or {}
    time_context = context.get("time_context") or {}

    if tool == "buzz":
        if not config or not config.buzzer_enabled or not quality.get("device_online"):
            return None
        if time_context.get("is_quiet_time"):
            return None
        pattern = str(params.get("pattern") or "short")
        duration = _as_int(params.get("duration_ms", 250))
        if pattern not in {"short", "long", "double"} or duration is None:
            return None
        if not 50 <= duration <= 5000:
            return None
        return {
            "tool": "buzz",
            "command_name": "buzz",
            "label": f"执行 {duration} 毫秒蜂鸣提醒",
            "reason": reason or "当前工位需要一次即时提醒",
            "params": {"pattern": pattern, "duration_ms": duration},
        }

    if tool == "set_thresholds":
        allowed = {"lux_min", "lux_max", "sit_warn_min", "sit_strong_min"}
        normalized = {
            key: _as_int(value)
            for key, value in params.items()
            if key in allowed
        }
        normalized = {key: value for key, value in normalized.items() if value is not None}
        if not normalized:
            return None
        lux_min = normalized.get("lux_min", config.lux_min if config else 150)
        lux_max = normalized.get("lux_max", config.lux_max if config else 1000)
        sit_warn = normalized.get(
            "sit_warn_min", config.sit_warn_min if config else 45
        )
        sit_strong = normalized.get(
            "sit_strong_min", config.sit_strong_min if config else 60
        )
        if not (0 <= lux_min < lux_max <= 200000):
            return None
        if not (1 <= sit_warn < sit_strong <= 240):
            return None
        return {
            "tool": "set_thresholds",
            "command_name": "set_threshold",
            "label": "应用 AI 建议的阈值",
            "reason": reason or "根据近期数据调整个性化阈值",
            "params": normalized,
        }
    return None


def normalize_actions(
    proposals: Any,
    config: Optional[models.DeviceConfig],
    context: Dict[str, Any],
    limit: int = 1,
) -> List[Dict[str, Any]]:
    if not isinstance(proposals, list):
        return []
    actions: List[Dict[str, Any]] = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        action = validate_action(proposal, config, context)
        if action:
            actions.append(action)
        if len(actions) >= limit:
            break
    return actions
