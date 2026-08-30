from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./flight_recorder.db"
    app_title: str = "IncidentLens"

    model_config = {"env_file": ".env", "env_prefix": "FR_", "extra": "ignore"}


settings = Settings()
