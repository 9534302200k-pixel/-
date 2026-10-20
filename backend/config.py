from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
MODELS = [
    "Gemma 4 26B A4B",
    "GLM-5.3-Flash",
    "Qwen3.6 35B A3B",
    "DeepSeek-V4.1-Flash",
    "Qwen3-VL-30B-A3B-Instruct",
    "Kimi-K2.6",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    data_dir: Path = ROOT / "data"
    demo_mode: bool = True
    app_access_token: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_id: str = ""
    llm_model_family: str = ""
    llm_input_rub_per_million: float = 0
    llm_output_rub_per_million: float = 0
    daily_budget_rub: float = 500
    llm_context_limit: int = 48000
    llm_max_output: int = 1600
    news_poll_minutes: int = 30
    revenue_multiplier: float = 1
    revenue_unit_confirmed: bool = False
    tessdata_prefix: str = ""

    @property
    def model_ready(self):
        return bool(
            self.llm_base_url.startswith("https://")
            and self.llm_api_key
            and self.llm_model_id
            and self.llm_model_family in MODELS
            and self.llm_input_rub_per_million > 0
            and self.llm_output_rub_per_million > 0
        )


settings = Settings()
