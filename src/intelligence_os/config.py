from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RIOS_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./raeburn_intelligence.db"
    api_key: str | None = None
    companies_house_api_key: str | None = None
    companies_house_base_url: str = "https://api.company-information.service.gov.uk"
    contracts_finder_base_url: str = (
        "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"
    )
    find_a_tender_base_url: str = (
        "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
    )
    nomis_base_url: str = "https://www.nomisweb.co.uk/api/v01"
    nomis_uid: str | None = None
    request_timeout_seconds: float = 20.0
    user_agent: str = (
        "Raeburn-Intelligence-OS/0.5 (+https://github.com/Raebu/Raeburn-Intelligence-OS)"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
