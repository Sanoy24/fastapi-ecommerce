from pydantic_settings import SettingsConfigDict, BaseSettings


class Setting(BaseSettings):
    Database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


setting = Setting()
