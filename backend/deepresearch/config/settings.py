from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Model ────────────────────────────────────────────────────────────────
    use_mock_model: bool = Field(default=False)
    model_api_key: str = Field(default="")
    model_base_url: str = Field(default="https://api.openai.com/v1")
    model_name: str = Field(default="gpt-4o")

    # ── Database ─────────────────────────────────────────────────────────────
    mysql_host: str = Field(default="127.0.0.1")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="deepresearch")
    mysql_password: str = Field(default="")
    mysql_db: str = Field(default="deepresearch")

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://127.0.0.1:6379/0")

    # ── Chroma ───────────────────────────────────────────────────────────────
    chroma_path: str = Field(default="./data/chroma_data")

    # ── Search ───────────────────────────────────────────────────────────────
    use_mock_search: bool = Field(default=True)
    search_api_key: str = Field(default="")
    search_api_url: str = Field(default="https://api.tavily.com")

    # ── Trace ────────────────────────────────────────────────────────────────
    trace_dir: str = Field(default="./data/traces")
    trace_stdout: bool = Field(default=True)

    # ── Virtual FS ───────────────────────────────────────────────────────────
    virtual_fs_root: str = Field(default="./data/virtual_fs")

    # ── Checkpoints (P5) ─────────────────────────────────────────────────────
    checkpoint_dir: str = Field(default="./data/checkpoints")

    # ── Citation policy: "flag" | "delete" | "keep_as_is" (P5) ──────────────
    citation_policy: str = Field(default="flag")

    # ── Research hard limits (override profile defaults if set) ──────────────
    max_depth: int | None = Field(default=None)
    max_breadth: int | None = Field(default=None)
    max_total_workers: int | None = Field(default=None)
    max_tokens_budget: int | None = Field(default=None)

    # ── Profiles config path ──────────────────────────────────────────────────
    profiles_path: str = Field(
        default=str(Path(__file__).parent / "research_profiles.yaml")
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
