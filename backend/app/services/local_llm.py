import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings


logger = logging.getLogger(__name__)

_DEFAULT_MODEL_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
_MIN_MODEL_BYTES = 500 * 1024 * 1024
_model: Optional[Any] = None
_model_lock = threading.Lock()
_REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "insights", "recommendations"],
    "properties": {
        "summary": {"type": "string"},
        "insights": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "detail", "level"],
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "level": {"type": "string", "enum": ["good", "warn", "high"]},
                },
            },
        },
        "recommendations": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {"type": "string"},
        },
    },
}


def get_model_path() -> Optional[Path]:
    configured = settings.local_llm_model_path.strip()
    path = Path(configured) if configured else (
        Path(__file__).resolve().parents[3] / "models" / _DEFAULT_MODEL_FILE
    )
    return (
        path
        if path.is_file() and path.stat().st_size >= _MIN_MODEL_BYTES
        else None
    )


def get_model_name() -> str:
    path = get_model_path()
    if path is None:
        return _DEFAULT_MODEL_FILE.removesuffix(".gguf")
    stem = path.stem
    if stem.lower().startswith("qwen2.5-1.5b"):
        return "Qwen2.5-1.5B"
    return stem


def is_available() -> bool:
    return get_model_path() is not None


def _load_model() -> Any:
    global _model
    if _model is not None:
        return _model

    model_path = get_model_path()
    if model_path is None:
        raise FileNotFoundError("local LLM model file not found")

    from llama_cpp import Llama

    cpu_count = os.cpu_count() or 4
    threads = settings.local_llm_threads or min(8, max(2, cpu_count - 2))
    logger.info(
        "Loading local LLM %s with %d threads and %d GPU layers",
        model_path,
        threads,
        settings.local_llm_gpu_layers,
    )
    _model = Llama(
        model_path=str(model_path),
        n_ctx=settings.local_llm_context,
        n_threads=threads,
        n_batch=128,
        n_gpu_layers=settings.local_llm_gpu_layers,
        verbose=False,
    )
    return _model


def generate_json(
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> Optional[str]:
    if not is_available():
        return None

    try:
        with _model_lock:
            model = _load_model()
            result = model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                repeat_penalty=1.05,
                response_format={"type": "json_object", "schema": _REPORT_SCHEMA},
            )
        content = result["choices"][0]["message"]["content"]
        return content if isinstance(content, str) else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Local LLM inference failed: %s", exc)
        return None
