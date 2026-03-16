from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Browser
    browser_headless: bool = False

    # Provider credentials
    copel_username: str = ""
    copel_password: str = ""
    claro_username: str = ""
    claro_password: str = ""
    sanepar_username: str = ""
    sanepar_password: str = ""
    countfly_username: str = ""
    countfly_password: str = ""

    # App
    downloads_dir: Path = Path("./downloads")
    api_port: int = 8000

    # LLM
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Agent
    use_vision: bool = False

    # Concurrency & Timeouts
    max_concurrent_tasks: int = 2
    job_timeout_seconds: int = 300


settings = Settings()
