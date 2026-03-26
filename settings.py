from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = Field(validation_alias="DATABASE_URL")

    openai_api_key: SecretStr = Field(validation_alias="OPENAI_API_KEY")

    jwt_secret: SecretStr = Field(validation_alias="JWT_SECRET")

    logfire_token: SecretStr = Field(validation_alias="LOGFIRE_TOKEN")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" 
    )

settings = Settings()