from __future__ import annotations
from pydantic import BaseSettings, Field
from typing import Optional

class Settings(BaseSettings):
    # App
    APP_ENV: str = Field("dev")
    OBS_KEY: Optional[str] = None

    # DB
    DATABASE_URL: str = Field(..., description="postgresql+psycopg://appuser:<PASS>@db:5432/appdb")

    # eMAG accounts (placeholders)
    EMAG_MAIN_USERNAME: Optional[str] = None
    EMAG_MAIN_PASSWORD: Optional[str] = None
    EMAG_FBE_USERNAME: Optional[str] = None
    EMAG_FBE_PASSWORD: Optional[str] = None
    EMAG_PLATFORM_CODE_MAIN: str = "ro"
    EMAG_PLATFORM_CODE_FBE: str = "ro"

    # Offers toggles (aliniat cu contractul tău)
    EMAG_OFFERS_DEFAULT_LIMIT: int = 25
    EMAG_OFFERS_MAX_LIMIT: int = 50
    EMAG_OFFERS_DEFAULT_COMPACT: int = 1
    EMAG_OFFERS_DEFAULT_FIELDS: str = "id,sku,name,sale_price,stock_total"
    EMAG_OFFERS_RETURN_META: int = 0
    EMAG_OFFERS_STRICT_FILTER: int = 0
    EMAG_OFFERS_TOTAL_MODE: str = "upstream"  # upstream|filtered|both

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
