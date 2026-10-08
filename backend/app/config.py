from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Game parameters, read from environment variables (case-insensitive) or .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    goal_radius_m: float = Field(500, gt=0)
    goal_min_distance_m: float = Field(100, gt=0)
    goal_threshold_m: float = Field(20, gt=0)
    reroute_threshold_m: float = Field(25, gt=0)
    frontend_port: int = Field(8080, gt=0)
    goal_max_attempts: int = Field(20, gt=0)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.upper() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _check_distances(self) -> "Settings":
        if self.goal_min_distance_m >= self.goal_radius_m:
            raise ValueError("GOAL_MIN_DISTANCE_M must be less than GOAL_RADIUS_M")
        if self.goal_threshold_m >= self.goal_min_distance_m:
            # Otherwise a goal could count as reached at spawn.
            raise ValueError("GOAL_THRESHOLD_M must be less than GOAL_MIN_DISTANCE_M")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [f"http://localhost:{self.frontend_port}", f"http://127.0.0.1:{self.frontend_port}"]


@lru_cache
def get_settings() -> Settings:
    # Raises pydantic.ValidationError on invalid config; call at startup to fail fast.
    return Settings()
