from pydantic_settings import SettingsConfigDict, BaseSettings


class Setting(BaseSettings):
    Database_url: str = ""
    JWT_ALGORITHM: str = ""
    JWT_SECRET_KEY: str = ""
    JWT_DEFAULT_EXP_MINUTES: int = 30

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


setting = Setting()
