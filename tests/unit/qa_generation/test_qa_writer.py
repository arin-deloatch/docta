# pylint: disable=redefined-outer-name
"""Unit tests for qa_generation.output.qa_writer module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from qa_generation.models import QAPair
from qa_generation.output.qa_writer import (
    QAWriteError,
    write_qa_pairs,
    write_qa_pairs_json,
    write_qa_pairs_yaml,
)


@pytest.fixture
def qa_pairs() -> list[QAPair]:
    """Provide a list of sample QA pairs for writer tests."""
    return [
        QAPair(
            question="What is foo?",
            ground_truth_answer="Foo is a bar.",
            source_topic_slug="guide",
            source_location="Section A",
            source_change_type="text_change",
        ),
        QAPair(
            question="How to install?",
            ground_truth_answer="Use pip install.",
            source_topic_slug="install",
        ),
    ]


class TestWriteQaPairsJson:
    """Tests for write_qa_pairs_json function."""

    def test_write_valid(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test writing valid QA pairs to JSON file."""
        output = tmp_path / "output.json"
        write_qa_pairs_json(qa_pairs, output)
        assert output.exists()

        data = json.loads(output.read_text())
        assert len(data) == 2
        assert data[0]["question"] == "What is foo?"

    def test_write_empty_list(self, tmp_path: Path) -> None:
        """Test writing empty list produces empty JSON array."""
        output = tmp_path / "output.json"
        write_qa_pairs_json([], output)
        data = json.loads(output.read_text())
        assert data == []

    def test_no_overwrite_by_default(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test existing file raises error without allow_overwrite."""
        output = tmp_path / "output.json"
        output.write_text("{}")

        with pytest.raises(QAWriteError, match="already exists"):
            write_qa_pairs_json(qa_pairs, output)

    def test_overwrite_allowed(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test allow_overwrite permits writing to existing file."""
        output = tmp_path / "output.json"
        output.write_text("{}")

        write_qa_pairs_json(qa_pairs, output, allow_overwrite=True)
        data = json.loads(output.read_text())
        assert len(data) == 2

    def test_creates_parent_dirs(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test parent directories are created automatically."""
        output = tmp_path / "subdir" / "deep" / "output.json"
        write_qa_pairs_json(qa_pairs, output)
        assert output.exists()

    def test_custom_indent(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test custom JSON indent is applied."""
        output = tmp_path / "output.json"
        write_qa_pairs_json(qa_pairs, output, indent=4)
        content = output.read_text()
        # With indent=4, dict keys nested inside a list are at 8 spaces (4+4).
        # The default indent=2 would only reach 4 spaces, so this distinguishes the two.
        assert "        " in content


class TestWriteQaPairsYaml:
    """Tests for write_qa_pairs_yaml function."""

    def test_write_valid(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test writing valid QA pairs to YAML file."""
        output = tmp_path / "output.yaml"
        write_qa_pairs_yaml(qa_pairs, output)
        assert output.exists()

        data = yaml.safe_load(output.read_text())
        assert len(data) == 2
        assert data[0]["question"] == "What is foo?"

    def test_write_empty_list(self, tmp_path: Path) -> None:
        """Test writing empty list produces empty YAML list."""
        output = tmp_path / "output.yaml"
        write_qa_pairs_yaml([], output)
        content = output.read_text()
        assert content.strip() == "[]" or yaml.safe_load(content) == []

    def test_no_overwrite_by_default(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test existing file raises error without allow_overwrite."""
        output = tmp_path / "output.yaml"
        output.write_text("---")

        with pytest.raises(QAWriteError, match="already exists"):
            write_qa_pairs_yaml(qa_pairs, output)

    def test_overwrite_allowed(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test allow_overwrite permits writing to existing YAML file."""
        output = tmp_path / "output.yaml"
        output.write_text("---")

        write_qa_pairs_yaml(qa_pairs, output, allow_overwrite=True)
        data = yaml.safe_load(output.read_text())
        assert len(data) == 2


class TestWriteQaPairs:
    """Tests for write_qa_pairs function."""

    def test_auto_detect_json(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test auto format detection for .json extension."""
        output = tmp_path / "output.json"
        write_qa_pairs(qa_pairs, output, output_format="auto")
        data = json.loads(output.read_text())
        assert len(data) == 2

    def test_auto_detect_yaml(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test auto format detection for .yaml extension."""
        output = tmp_path / "output.yaml"
        write_qa_pairs(qa_pairs, output, output_format="auto")
        data = yaml.safe_load(output.read_text())
        assert len(data) == 2

    def test_auto_detect_yml(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test auto format detection for .yml extension."""
        output = tmp_path / "output.yml"
        write_qa_pairs(qa_pairs, output, output_format="auto")
        data = yaml.safe_load(output.read_text())
        assert len(data) == 2

    def test_auto_detect_unknown_extension(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test unknown extension raises ValueError in auto mode."""
        output = tmp_path / "output.txt"
        with pytest.raises(ValueError, match="Cannot auto-detect"):
            write_qa_pairs(qa_pairs, output, output_format="auto")

    def test_explicit_json_format(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test explicit JSON format writes valid JSON."""
        output = tmp_path / "output.json"
        write_qa_pairs(qa_pairs, output, output_format="json")
        assert json.loads(output.read_text())

    def test_explicit_yaml_format(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test explicit YAML format writes valid YAML."""
        output = tmp_path / "output.yaml"
        write_qa_pairs(qa_pairs, output, output_format="yaml")
        assert yaml.safe_load(output.read_text())

    def test_invalid_format(self, tmp_path: Path, qa_pairs: list[QAPair]) -> None:
        """Test unsupported format raises ValueError."""
        output = tmp_path / "output.json"
        with pytest.raises(ValueError, match="Invalid format"):
            write_qa_pairs(qa_pairs, output, output_format="xml")

    def test_empty_list_warning(self, tmp_path: Path) -> None:
        """Test writing empty list still produces valid output."""
        output = tmp_path / "output.json"
        write_qa_pairs([], output, output_format="json")
        data = json.loads(output.read_text())
        assert data == []
