import os
from dataclasses import dataclass
from typing import Optional, Tuple

from dotenv import load_dotenv


load_dotenv()


def _bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _origins(value: str) -> Tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///./eye_care.db")
    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str = _database_url()
    api_token: str = os.getenv("API_TOKEN", "dev-token-change-me")
    demo_username: str = os.getenv("DEMO_USERNAME", "demo")
    demo_password: str = os.getenv("DEMO_PASSWORD", "demo123")
    cors_origins: Tuple[str, ...] = _origins(os.getenv("CORS_ORIGINS", "*"))
    iotda_mock: bool = _bool(os.getenv("IOTDA_MOCK"), True)
    iotda_base_url: str = os.getenv("IOTDA_BASE_URL", "")
    iotda_project_id: str = os.getenv("IOTDA_PROJECT_ID", "")
    iotda_token: str = os.getenv("IOTDA_TOKEN", "")
    iotda_access_key: str = os.getenv("IOTDA_ACCESS_KEY", "")
    iotda_secret_key: str = os.getenv("IOTDA_SECRET_KEY", "")
    iotda_instance_id: str = os.getenv("IOTDA_INSTANCE_ID", "")
    iotda_cloud_device_id: str = os.getenv("IOTDA_CLOUD_DEVICE_ID", "")
    iotda_internal_device_id: str = os.getenv(
        "IOTDA_INTERNAL_DEVICE_ID", "hi3861_001"
    )
    iotda_poll_enabled: bool = _bool(
        os.getenv("IOTDA_POLL_ENABLED"), True
    )
    iotda_poll_interval_s: float = float(
        os.getenv("IOTDA_POLL_INTERVAL_S", "5")
    )
    iotda_app_mqtt_enabled: bool = _bool(
        os.getenv("IOTDA_APP_MQTT_ENABLED"), True
    )
    iotda_app_mqtt_host: str = os.getenv("IOTDA_APP_MQTT_HOST", "")
    iotda_app_mqtt_port: int = int(
        os.getenv("IOTDA_APP_MQTT_PORT", "8883")
    )
    iotda_app_mqtt_topic: str = os.getenv(
        "IOTDA_APP_MQTT_TOPIC", "eye_care/telemetry"
    )
    iotda_app_access_key: str = os.getenv("IOTDA_APP_ACCESS_KEY", "")
    iotda_app_access_code: str = os.getenv("IOTDA_APP_ACCESS_CODE", "")
    llm_api_url: str = os.getenv("LLM_API_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    llm_timeout_s: float = float(os.getenv("LLM_TIMEOUT_S", "120"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "420"))
    local_llm_model_path: str = os.getenv("LOCAL_LLM_MODEL_PATH", "")
    local_llm_context: int = int(os.getenv("LOCAL_LLM_CONTEXT", "3072"))
    local_llm_threads: int = int(os.getenv("LOCAL_LLM_THREADS", "0"))
    local_llm_gpu_layers: int = int(os.getenv("LOCAL_LLM_GPU_LAYERS", "0"))

    @property
    def iotda_configured(self) -> bool:
        return bool(
            self.iotda_base_url
            and self.iotda_project_id
            and self.iotda_access_key
            and self.iotda_secret_key
        )

    @property
    def iotda_app_mqtt_configured(self) -> bool:
        return bool(
            self.iotda_app_mqtt_host
            and self.iotda_instance_id
            and self.iotda_app_access_key
            and self.iotda_app_access_code
            and self.iotda_app_mqtt_topic
        )


settings = Settings()
