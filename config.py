from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"
    microsoft_user_email: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    app_secret_key: str = "changeme"
    database_url: str = "sqlite:///./personal_assistant.db"
    voice_enabled: bool = True
    web_host: str = "0.0.0.0"
    web_port: int = 8000

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
