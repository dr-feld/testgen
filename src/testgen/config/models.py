from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str = Field(..., min_length=1)
    api_base_url: str = Field()
    api_key: str | None = Field(default=None, description="LLM API key, resolved from .env if omitted.")
    proxy: str | None = Field(default=None, description="network proxy, resolved from .env if omitted.")
    max_tokens: int = Field(..., gt=0)
    temperature: float = Field(..., ge=0.0, le=2.0)
    timeout_seconds: float = Field(..., gt=0)

    @model_validator(mode="after")
    def resolve_api_key(self) -> "LLMConfig":
        if self.api_key:
            return self

        env_api_key = os.getenv("LLM_API_KEY")
        if not env_api_key:
            raise ValueError(
                "LLM API key is not configured. Set `llm.api_key` in yaml or define LLM_API_KEY in .env"
            )
        self.api_key = env_api_key
        env_proxy = os.getenv("VEGA_PROXY")
        if env_proxy:
            self.proxy = env_proxy
        return self


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_path: Path
    tests_path: Path
    testing_framework: Literal["gtest", "catch2", "doctest", "other"] = "other"


class ValidationScriptsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    syntax_check_script: Path
    unit_test_script: Path
    static_analysis_script: Path | None = None


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: LLMConfig
    project: ProjectConfig
    validation: ValidationScriptsConfig
