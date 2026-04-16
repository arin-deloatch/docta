"""Configuration loading for GraphQL polling service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from docta.utils.constants import MAX_FILE_SIZE_BYTES
from docta.graphql.models import GraphQLPollingSettings


def load_graphql_settings(yaml_path: str | Path | None = None, **overrides) -> GraphQLPollingSettings:
    """Load GraphQL polling settings from YAML file and environment variables.

    Settings priority:
    1. Environment variables (highest)
    2. YAML configuration file
    3. Default values (lowest)

    Args:
        yaml_path: Path to YAML configuration file
        **overrides: Direct overrides for specific settings

    Returns:
        Validated GraphQLPollingSettings object

    Raises:
        ValidationError: If configuration is invalid
        FileNotFoundError: If YAML file doesn't exist
        ValueError: If YAML file is too large or malformed
    """
    config_data: dict[str, Any] = {}

    # Load from YAML if provided
    if yaml_path:
        yaml_file = Path(yaml_path)
        if not yaml_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

        # Check file size (prevent YAML bombs)
        file_size = yaml_file.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Configuration file too large: {file_size} bytes " f"(max {MAX_FILE_SIZE_BYTES} bytes)")

        # Parse YAML
        with open(yaml_file, encoding="utf-8") as f:
            try:
                config_data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {yaml_path}: {e}") from e

    # Apply overrides
    config_data.update(overrides)

    # Create settings (combines YAML + environment variables)
    try:
        settings = GraphQLPollingSettings(**config_data)
    except ValidationError as e:
        # Re-raise with more context
        raise ValueError(f"Configuration validation failed: {e}") from e

    return settings
