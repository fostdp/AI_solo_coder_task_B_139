from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rammed_earth_wall"
    TIMESCALEDB_URL: str = "postgresql://postgres:postgres@localhost:5432/rammed_earth_wall"
    
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "wall/alert"
    MQTT_CLIENT_ID: str = "backend_server"
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    WALL_SEGMENTS: int = 8
    SIMULATION_INTERVAL: int = 3600
    
    EROSION_THRESHOLD: float = 0.5
    CRACK_THRESHOLD: float = 0.1
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
