from pydantic_settings import BaseSettings
from pydantic import computed_field
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class DBSettings(BaseSettings):
    db_username: str = Field(...)
    db_password: str = Field(...)
    db_host: str = Field(...)
    db_port: int = Field(...)
    db_name: str = Field(...)

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


class LLMSettings(BaseSettings):
    deepseek_api_key: str = Field(...)
    deepseek_api_base: str = Field(...)
    openai_api_key: str = Field(...)
    openai_base_url: str = Field(...)
    langchain_api_key: str = Field(...)
    langchain_project: str = Field(...)
    langchain_tracing_v2: bool = Field(...)


class Settings(DBSettings, LLMSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
