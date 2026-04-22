"""Unit tests for docta.models.html_diff module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from docta.models.html_diff import (
    HTMLChange,
    HTMLDiffResult,
    FailedComparison,
    ProcessingResult,
    HTMLDiffReport,
)


class TestHTMLChange:
    """Tests for HTMLChange model."""

    @pytest.fixture
    def sample_html_change_data(self) -> dict:
        """Fixture providing sample HTML change data."""
        return {
            "change_type": "text_change",
            "description": "Paragraph content modified",
            "old_html_snippet": "<p>Old text</p>",
            "new_html_snippet": "<p>New text</p>",
            "old_text": "Old text",
            "new_text": "New text",
            "location": "Section: Introduction",
        }

    def test_valid_html_change(self, sample_html_change_data: dict) -> None:
        """Test creating valid HTMLChange."""
        change = HTMLChange(**sample_html_change_data)
        assert change.change_type == "text_change"
        assert change.description == "Paragraph content modified"
        assert change.old_text == "Old text"
        assert change.new_text == "New text"

    @pytest.mark.parametrize(
        "change_type",
        ["text_change", "structure_change", "metadata_change"],
    )
    def test_valid_change_types(self, sample_html_change_data: dict, change_type: str) -> None:
        """Test all valid change types."""
        data = sample_html_change_data.copy()
        data["change_type"] = change_type
        change = HTMLChange(**data)
        assert change.change_type == change_type

    def test_invalid_change_type(self, sample_html_change_data: dict) -> None:
        """Test that invalid change types raise ValidationError."""
        data = sample_html_change_data.copy()
        data["change_type"] = "invalid_type"
        with pytest.raises(ValidationError):
            HTMLChange(**data)

    def test_minimal_html_change(self) -> None:
        """Test HTMLChange with only required fields."""
        change = HTMLChange(
            change_type="text_change",
            description="Text changed",
        )
        assert change.old_html_snippet is None
        assert change.new_html_snippet is None
        assert change.old_text is None
        assert change.new_text is None
        assert change.location is None

    def test_change_with_location(self, sample_html_change_data: dict) -> None:
        """Test change with location information."""
        data = sample_html_change_data.copy()
        data["location"] = "Section: Installation > Step 1"
        change = HTMLChange(**data)
        assert change.location == "Section: Installation > Step 1"


class TestHTMLDiffResult:
    """Tests for HTMLDiffResult model."""

    @pytest.fixture
    def sample_html_change(self) -> HTMLChange:
        """Fixture providing a sample HTMLChange."""
        return HTMLChange(
            change_type="text_change",
            description="Text modified",
        )

    @pytest.fixture
    def sample_diff_result_data(self, sample_html_change: HTMLChange) -> dict:
        """Fixture providing sample diff result data."""
        return {
            "old_path": "/docs/v1/guide.html",
            "new_path": "/docs/v2/guide.html",
            "old_topic_slug": "guide",
            "new_topic_slug": "guide",
            "relationship": "modified",
            "changes": [sample_html_change],
            "text_similarity": 85.5,
            "has_structural_changes": False,
        }

    def test_valid_diff_result(self, sample_diff_result_data: dict) -> None:
        """Test creating valid HTMLDiffResult."""
        result = HTMLDiffResult(**sample_diff_result_data)
        assert result.old_path == "/docs/v1/guide.html"
        assert result.new_path == "/docs/v2/guide.html"
        assert result.relationship == "modified"
        assert result.text_similarity == 85.5
        assert result.has_structural_changes is False

    def test_diff_result_with_structural_changes(self, sample_diff_result_data: dict) -> None:
        """Test diff result with structural changes."""
        data = sample_diff_result_data.copy()
        data["has_structural_changes"] = True
        result = HTMLDiffResult(**data)
        assert result.has_structural_changes is True

    def test_diff_result_no_changes(self, sample_diff_result_data: dict) -> None:
        """Test diff result with no changes."""
        data = sample_diff_result_data.copy()
        data["changes"] = []
        result = HTMLDiffResult(**data)
        assert len(result.changes) == 0

    @pytest.mark.parametrize(
        "similarity",
        [0.0, 25.5, 50.0, 75.0, 100.0],
    )
    def test_valid_text_similarity(self, sample_diff_result_data: dict, similarity: float) -> None:
        """Test valid text similarity values."""
        data = sample_diff_result_data.copy()
        data["text_similarity"] = similarity
        result = HTMLDiffResult(**data)
        assert result.text_similarity == similarity

    @pytest.mark.parametrize(
        "invalid_similarity",
        [-0.1, -10.0, 100.1, 150.0],
    )
    def test_invalid_text_similarity(self, sample_diff_result_data: dict, invalid_similarity: float) -> None:
        """Test that invalid text similarity values raise ValidationError."""
        data = sample_diff_result_data.copy()
        data["text_similarity"] = invalid_similarity
        with pytest.raises(ValidationError):
            HTMLDiffResult(**data)

    def test_diff_result_with_multiple_changes(self, sample_diff_result_data: dict) -> None:
        """Test diff result with multiple changes."""
        change1 = HTMLChange(change_type="text_change", description="Change 1")
        change2 = HTMLChange(change_type="structure_change", description="Change 2")
        change3 = HTMLChange(change_type="metadata_change", description="Change 3")

        data = sample_diff_result_data.copy()
        data["changes"] = [change1, change2, change3]
        result = HTMLDiffResult(**data)
        assert len(result.changes) == 3


class TestFailedComparison:
    """Tests for FailedComparison model."""

    @pytest.fixture
    def sample_failed_comparison_data(self) -> dict:
        """Fixture providing sample failed comparison data."""
        return {
            "old_path": "/docs/v1/guide.html",
            "new_path": "/docs/v2/guide.html",
            "error_type": "FileNotFoundError",
            "error_message": "File not found: /docs/v2/guide.html",
        }

    def test_valid_failed_comparison(self, sample_failed_comparison_data: dict) -> None:
        """Test creating valid FailedComparison."""
        failure = FailedComparison(**sample_failed_comparison_data)
        assert failure.old_path == "/docs/v1/guide.html"
        assert failure.new_path == "/docs/v2/guide.html"
        assert failure.error_type == "FileNotFoundError"
        assert failure.error_message == "File not found: /docs/v2/guide.html"

    @pytest.mark.parametrize(
        ("error_type", "error_message"),
        [
            ("OSError", "Permission denied"),
            ("ValueError", "Invalid HTML"),
            ("RuntimeError", "Processing timeout"),
        ],
    )
    def test_various_error_types(
        self,
        sample_failed_comparison_data: dict,
        error_type: str,
        error_message: str,
    ) -> None:
        """Test failed comparison with various error types."""
        data = sample_failed_comparison_data.copy()
        data["error_type"] = error_type
        data["error_message"] = error_message
        failure = FailedComparison(**data)
        assert failure.error_type == error_type
        assert failure.error_message == error_message


class TestProcessingResult:
    """Tests for ProcessingResult model."""

    @pytest.fixture
    def sample_html_diff_result(self) -> HTMLDiffResult:
        """Fixture providing a sample HTMLDiffResult."""
        return HTMLDiffResult(
            old_path="/docs/v1/guide.html",
            new_path="/docs/v2/guide.html",
            old_topic_slug="guide",
            new_topic_slug="guide",
            relationship="modified",
            changes=[],
            text_similarity=90.0,
            has_structural_changes=False,
        )

    @pytest.fixture
    def sample_failed_comparison(self) -> FailedComparison:
        """Fixture providing a sample FailedComparison."""
        return FailedComparison(
            old_path="/docs/v1/guide.html",
            new_path="/docs/v2/guide.html",
            error_type="FileNotFoundError",
            error_message="File not found",
        )

    def test_successful_processing_result(self, sample_html_diff_result: HTMLDiffResult) -> None:
        """Test successful processing result."""
        result = ProcessingResult(
            success=True,
            result=sample_html_diff_result,
        )
        assert result.success is True
        assert result.result is not None
        assert result.failure is None

    def test_failed_processing_result(self, sample_failed_comparison: FailedComparison) -> None:
        """Test failed processing result."""
        result = ProcessingResult(
            success=False,
            failure=sample_failed_comparison,
        )
        assert result.success is False
        assert result.result is None
        assert result.failure is not None

    def test_processing_result_defaults(self) -> None:
        """Test processing result with defaults."""
        result = ProcessingResult(success=True)
        assert result.result is None
        assert result.failure is None


class TestHTMLDiffReport:
    """Tests for HTMLDiffReport model."""

    @pytest.fixture
    def sample_html_diff_result(self) -> HTMLDiffResult:
        """Fixture providing a sample HTMLDiffResult."""
        return HTMLDiffResult(
            old_path="/docs/v1/guide.html",
            new_path="/docs/v2/guide.html",
            old_topic_slug="guide",
            new_topic_slug="guide",
            relationship="modified",
            changes=[],
            text_similarity=90.0,
            has_structural_changes=False,
        )

    @pytest.fixture
    def sample_report_data(self, sample_html_diff_result: HTMLDiffResult) -> dict:
        """Fixture providing sample report data."""
        return {
            "old_version": "1.0.0",
            "new_version": "1.1.0",
            "old_root": "/docs/v1",
            "new_root": "/docs/v2",
            "results": [sample_html_diff_result],
            "total_compared": 1,
            "total_with_changes": 1,
        }

    def test_valid_html_diff_report(self, sample_report_data: dict) -> None:
        """Test creating valid HTMLDiffReport."""
        report = HTMLDiffReport(**sample_report_data)
        assert report.old_version == "1.0.0"
        assert report.new_version == "1.1.0"
        assert report.total_compared == 1
        assert report.total_with_changes == 1
        assert report.total_failed == 0

    def test_report_with_failed_comparisons(self, sample_report_data: dict) -> None:
        """Test report with failed comparisons."""
        failed = FailedComparison(
            old_path="/docs/v1/test.html",
            new_path="/docs/v2/test.html",
            error_type="OSError",
            error_message="Read error",
        )

        data = sample_report_data.copy()
        data["failed_comparisons"] = [failed]
        data["total_failed"] = 1
        report = HTMLDiffReport(**data)
        assert len(report.failed_comparisons) == 1
        assert report.total_failed == 1

    def test_empty_report(self) -> None:
        """Test report with no results."""
        report = HTMLDiffReport(
            old_version="1.0.0",
            new_version="1.1.0",
            old_root="/docs/v1",
            new_root="/docs/v2",
            results=[],
            total_compared=0,
            total_with_changes=0,
        )
        assert len(report.results) == 0
        assert report.total_compared == 0

    def test_report_with_multiple_results(self, sample_html_diff_result: HTMLDiffResult) -> None:
        """Test report with multiple results."""
        report = HTMLDiffReport(
            old_version="1.0.0",
            new_version="1.1.0",
            old_root="/docs/v1",
            new_root="/docs/v2",
            results=[sample_html_diff_result] * 5,
            total_compared=5,
            total_with_changes=3,
        )
        assert len(report.results) == 5
        assert report.total_compared == 5
        assert report.total_with_changes == 3

    def test_report_serialization(self, sample_report_data: dict) -> None:
        """Test that HTMLDiffReport can be serialized and deserialized."""
        report = HTMLDiffReport(**sample_report_data)
        report_dict = report.model_dump()
        report_restored = HTMLDiffReport(**report_dict)
        assert report == report_restored
