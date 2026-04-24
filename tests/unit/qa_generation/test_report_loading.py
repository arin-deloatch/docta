"""Unit tests for qa_generation.utils.report_loading module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_generation.utils.report_loading import validate_and_load_json_report


class _SentinelError(Exception):
    """Custom error class for testing error propagation."""


class TestValidateAndLoadJsonReport:
    """Tests for validate_and_load_json_report function."""

    def test_valid_json_dict(self, tmp_path: Path) -> None:
        """Test loading a valid JSON dict report."""
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps({"key": "value", "count": 42}))

        result = validate_and_load_json_report(report_file, _SentinelError, "test")
        assert result == {"key": "value", "count": 42}

    def test_invalid_json(self, tmp_path: Path) -> None:
        """Test invalid JSON content raises custom error."""
        report_file = tmp_path / "report.json"
        report_file.write_text("not valid json{{{")

        with pytest.raises(_SentinelError, match="Invalid JSON"):
            validate_and_load_json_report(report_file, _SentinelError, "test")

    def test_json_array_root_rejected(self, tmp_path: Path) -> None:
        """Test JSON array root type is rejected."""
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps([1, 2, 3]))

        with pytest.raises(_SentinelError, match="Invalid JSON root type"):
            validate_and_load_json_report(report_file, _SentinelError, "test")

    def test_nonexistent_file(self) -> None:
        """Test nonexistent file raises security validation error."""
        with pytest.raises(_SentinelError, match="Security validation failed"):
            validate_and_load_json_report(
                Path("/nonexistent/report.json"),
                _SentinelError,
                "test",
            )

    def test_wrong_extension(self, tmp_path: Path) -> None:
        """Test non-JSON file extension raises security validation error."""
        report_file = tmp_path / "report.txt"
        report_file.write_text(json.dumps({"key": "value"}))

        with pytest.raises(_SentinelError, match="Security validation failed"):
            validate_and_load_json_report(report_file, _SentinelError, "test")

    def test_large_valid_json(self, tmp_path: Path) -> None:
        """Test loading a large valid JSON file succeeds."""
        data = {f"key_{i}": f"value_{i}" for i in range(1000)}
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(data))

        result = validate_and_load_json_report(report_file, _SentinelError, "test")
        assert len(result) == 1000

    def test_nested_json(self, tmp_path: Path) -> None:
        """Test loading nested JSON structure preserves hierarchy."""
        data = {
            "results": [{"id": 1}, {"id": 2}],
            "metadata": {"version": "1.0"},
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(data))

        result = validate_and_load_json_report(report_file, _SentinelError, "test")
        assert result["metadata"]["version"] == "1.0"
        assert len(result["results"]) == 2

    def test_custom_error_class_used(self, tmp_path: Path) -> None:
        """Test custom error class is used for raised exceptions."""
        report_file = tmp_path / "report.json"
        report_file.write_text("bad")

        with pytest.raises(_SentinelError):
            validate_and_load_json_report(report_file, _SentinelError, "test")

    def test_empty_json_object(self, tmp_path: Path) -> None:
        """Test loading empty JSON object returns empty dict."""
        report_file = tmp_path / "report.json"
        report_file.write_text("{}")

        result = validate_and_load_json_report(report_file, _SentinelError, "test")
        assert result == {}

    def test_symlink_rejected(self, tmp_path: Path) -> None:
        """Test symlinked file raises security validation error."""
        real_file = tmp_path / "real.json"
        real_file.write_text(json.dumps({"key": "value"}))
        link_file = tmp_path / "link.json"
        link_file.symlink_to(real_file)

        with pytest.raises(_SentinelError, match="Security validation failed"):
            validate_and_load_json_report(link_file, _SentinelError, "test")
