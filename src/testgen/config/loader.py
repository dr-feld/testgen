from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from dotenv import load_dotenv
from testgen.config.models import AppConfig

import yaml

class ConfigLoadError(RuntimeError):
    """Raised when app config cannot be loaded from yaml."""


def load_app_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise ConfigLoadError(f"Config file not found: {path}")
    if not path.is_file():
        raise ConfigLoadError(f"Config path is not a file: {path}")

    load_dotenv()

    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigLoadError(f"Failed to read config file `{path}`: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"YAML parse error in `{path}`: {exc}") from exc

    if raw_data is None:
        raise ConfigLoadError(f"Config file `{path}` is empty.")
    if not isinstance(raw_data, dict):
        raise ConfigLoadError(
            f"Config root must be a mapping/object, got `{type(raw_data).__name__}` in `{path}`."
        )

    try:
        return AppConfig.model_validate(raw_data)
    except ValidationError as exc:
        raise ConfigLoadError(f"Invalid config in `{path}`:\n{exc}") from exc
