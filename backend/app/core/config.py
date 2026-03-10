from pydantic_settings import BaseSettings
from typing import Optional
from urllib.parse import quote_plus
import os

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "CI/CD Pipeline Health Dashboard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database settings
    POSTGRES_DB: str = "cicd_dashboard"
    POSTGRES_USER: str = "cicd_user"
    POSTGRES_PASSWORD: str = "secure_password"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    
    # GitHub settings
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_OWNER: Optional[str] = None
    GITHUB_REPO: Optional[str] = None
    
    # API settings
    API_V1_STR: str = "/api"
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://frontend:3000"]
    
    # Sync settings
    SYNC_INTERVAL_SECONDS: int = 300  # 5 minutes
    MAX_SYNC_RETRIES: int = 3
    
    # Cache settings
    CACHE_TTL_SECONDS: int = 300  # 5 minutes
    
    @property
    def DATABASE_URL(self) -> str:
        """Generate database URL from components (password is URL-encoded to handle special chars)"""
        encoded_password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()
