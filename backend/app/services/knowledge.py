import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _knowledge_dir() -> Path:
    configured = os.getenv("KNOWLEDGE_DIR", "").strip()
    if configured:
        return Path(configured).resolve()
    source = Path(__file__).resolve()
    for candidate in (source.parents[3], source.parents[2]):
        directory = candidate / "knowledge"
        if directory.is_dir():
            return directory
    return source.parents[3] / "knowledge"


KNOWLEDGE_DIR = _knowledge_dir()
FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def _parse_document(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER.match(text)
    metadata: Dict[str, str] = {}
    body = text
    if match:
        body = text[match.end() :]
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    tags = [
        item.strip().lower()
        for item in metadata.get("tags", "").split(",")
        if item.strip()
    ]
    return {
        "id": metadata.get("id") or path.stem,
        "title": metadata.get("title") or path.stem,
        "source": metadata.get("source") or "项目知识库",
        "url": metadata.get("url") or "",
        "excerpt": metadata.get("excerpt") or "",
        "tags": tags,
        "body": body.strip(),
    }


@lru_cache(maxsize=1)
def load_knowledge() -> Tuple[Dict[str, Any], ...]:
    if not KNOWLEDGE_DIR.is_dir():
        return ()
    documents = [
        _parse_document(path)
        for path in sorted(KNOWLEDGE_DIR.glob("*.md"))
        if path.name.lower() != "readme.md"
    ]
    return tuple(documents)


def clear_knowledge_cache() -> None:
    load_knowledge.cache_clear()


def _query_text(
    signals: Iterable[Dict[str, Any]], context: Dict[str, Any]
) -> str:
    signal_list = list(signals)
    signal_keys = {item.get("key") for item in signal_list}
    signal_text = " ".join(
        f"{item.get('key', '')} {item.get('fact', '')}" for item in signal_list
    )
    current = context.get("current") or {}
    time_context = context.get("time_context") or {}
    parts = [
        signal_text,
        f"工位 用眼 {time_context.get('period', '')}",
    ]
    if "light" in signal_keys:
        parts.append(f"光照 照度 低照光 {current.get('lux', '')}")
    if "sitting" in signal_keys:
        parts.append(f"久坐 连续 {current.get('sit_cont_min', '')}")
    if signal_keys & {"humidity", "temperature"}:
        parts.append(
            f"温湿度 {current.get('temperature', '')} {current.get('humidity', '')}"
        )
    if "data_quality" in signal_keys:
        parts.append("传感器 数据 可信度 覆盖")
    return " ".join(parts).lower()


def _score(document: Dict[str, Any], query: str) -> float:
    title = document["title"].lower()
    body = document["body"].lower()
    score = 0.0
    for tag in document["tags"]:
        if tag and tag in query:
            score += 8.0
        if tag and tag in title:
            score += 1.5
    for token in set(re.findall(r"[a-z0-9-]{2,}", query)):
        if token in title:
            score += 2.0
        if token in body:
            score += 0.8
    for phrase in (
        "低照光",
        "在座",
        "久坐",
        "温湿度",
        "可信度",
        "远眺",
        "休息",
        "传感器",
    ):
        if phrase in query and phrase in body:
            score += 3.0
    return score


def retrieve_knowledge(
    signals: List[Dict[str, Any]],
    context: Dict[str, Any],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    documents = load_knowledge()
    if not documents:
        return []
    query = _query_text(signals, context)
    ranked = sorted(
        ((_score(document, query), document) for document in documents),
        key=lambda item: item[0],
        reverse=True,
    )
    selected = [item for item in ranked if item[0] > 0][:limit]
    if len(selected) < min(2, len(ranked)):
        selected = ranked[: min(2, len(ranked))]
    results: List[Dict[str, Any]] = []
    for index, (score, document) in enumerate(selected, start=1):
        results.append(
            {
                "id": f"K{index}",
                "knowledge_id": document["id"],
                "title": document["title"],
                "source": document["source"],
                "url": document["url"],
                "excerpt": document["excerpt"] or document["body"][:140],
                "score": round(score, 2),
            }
        )
    return results
