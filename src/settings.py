from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    debug_mode: bool = False

    bot_username: str
    bot_token: str
    gemini_api_key: str

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str
    db_password: str
    db_name: str

    @property
    def db_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def db_url_sync(self) -> str:
        return f"postgresql+psycopg2://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
