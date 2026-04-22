"""Unit tests for docta.models.models module."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from docta.models.models import (
    RelationshipType,
    DocumentRecord,
    MatchRecord,
    ManifestComparison,
    DeltaReport,
)


class TestRelationshipType:
    """Tests for RelationshipType enum."""

    def test_enum_values(self) -> None:
        """Test that enum has expected values."""
        assert RelationshipType.UNCHANGED == "unchanged"
        assert RelationshipType.MODIFIED == "modified"
        assert RelationshipType.RENAMED_CANDIDATE == "renamed_candidate"

    @pytest.mark.parametrize(
        "value",
        ["unchanged", "modified", "renamed_candidate"],
    )
    def test_enum_membership(self, value: str) -> None:
        """Test enum membership checks."""
        assert value in [e.value for e in RelationshipType]

    def test_enum_count(self) -> None:
        """Test that enum has exactly three members."""
        assert len(list(RelationshipType)) == 3


class TestDocumentRecord:
    """Tests for DocumentRecord model."""

    @pytest.fixture
    def sample_doc_data(self) -> dict:
        """Fixture providing sample document record data."""
        return {
            "version": "1.0.0",
            "root": "/docs",
            "relative_path": "guides/intro.html",
            "topic_slug": "guides-intro",
            "html_filename": "intro.html",
            "raw_hash": "abc123",
        }

    def test_valid_document_record(self, sample_doc_data: dict) -> None:
        """Test creating valid DocumentRecord."""
        doc = DocumentRecord(**sample_doc_data)
        assert doc.version == "1.0.0"
        assert doc.root == "/docs"
        assert doc.relative_path == "guides/intro.html"
        assert doc.topic_slug == "guides-intro"
        assert doc.html_filename == "intro.html"
        assert doc.raw_hash == "abc123"

    def test_path_property(self, sample_doc_data: dict) -> None:
        """Test that path property returns correct absolute path."""
        doc = DocumentRecord(**sample_doc_data)
        expected = Path("/docs/guides/intro.html")
        assert doc.path == expected

    @pytest.mark.parametrize(
        ("root", "relative_path", "expected_path"),
        [
            ("/docs", "intro.html", "/docs/intro.html"),
            ("/var/www", "guides/tutorial.html", "/var/www/guides/tutorial.html"),
            (".", "test.html", "./test.html"),
            ("/opt/docs", "api/v1/methods.html", "/opt/docs/api/v1/methods.html"),
        ],
    )
    def test_path_property_variations(self, sample_doc_data: dict, root: str, relative_path: str, expected_path: str) -> None:
        """Test path property with various root and relative path combinations."""
        data = sample_doc_data.copy()
        data["root"] = root
        data["relative_path"] = relative_path
        doc = DocumentRecord(**data)
        assert doc.path == Path(expected_path)

    @pytest.mark.parametrize(
        "missing_field",
        ["version", "root", "relative_path", "topic_slug", "html_filename", "raw_hash"],
    )
    def test_missing_required_fields(self, sample_doc_data: dict, missing_field: str) -> None:
        """Test that missing required fields raise ValidationError."""
        data = sample_doc_data.copy()
        del data[missing_field]
        with pytest.raises(ValidationError) as exc_info:
            DocumentRecord(**data)
        assert missing_field in str(exc_info.value)

    def test_model_serialization(self, sample_doc_data: dict) -> None:
        """Test that DocumentRecord can be serialized and deserialized."""
        doc = DocumentRecord(**sample_doc_data)
        doc_dict = doc.model_dump()
        doc_restored = DocumentRecord(**doc_dict)
        assert doc == doc_restored


class TestMatchRecord:
    """Tests for MatchRecord model."""

    @pytest.fixture
    def sample_match_data(self) -> dict:
        """Fixture providing sample match record data."""
        return {
            "old_relative_path": "guides/intro.html",
            "new_relative_path": "guides/intro.html",
            "old_topic_slug": "guides-intro",
            "new_topic_slug": "guides-intro",
            "relationship": RelationshipType.UNCHANGED,
            "confidence": 1.0,
            "topic_slug_similarity": 100.0,
            "raw_hash_equal": True,
        }

    def test_valid_match_record(self, sample_match_data: dict) -> None:
        """Test creating valid MatchRecord."""
        match = MatchRecord(**sample_match_data)
        assert match.old_relative_path == "guides/intro.html"
        assert match.relationship == RelationshipType.UNCHANGED
        assert match.confidence == 1.0
        assert match.topic_slug_similarity == 100.0
        assert match.raw_hash_equal is True

    @pytest.mark.parametrize(
        "confidence",
        [0.0, 0.25, 0.5, 0.75, 1.0],
    )
    def test_valid_confidence_values(self, sample_match_data: dict, confidence: float) -> None:
        """Test that valid confidence values are accepted."""
        data = sample_match_data.copy()
        data["confidence"] = confidence
        match = MatchRecord(**data)
        assert match.confidence == confidence

    @pytest.mark.parametrize(
        "invalid_confidence",
        [-0.1, -1.0, 1.1, 2.0, 100.0],
    )
    def test_invalid_confidence_values(self, sample_match_data: dict, invalid_confidence: float) -> None:
        """Test that invalid confidence values raise ValidationError."""
        data = sample_match_data.copy()
        data["confidence"] = invalid_confidence
        with pytest.raises(ValidationError):
            MatchRecord(**data)

    @pytest.mark.parametrize(
        "similarity",
        [0.0, 25.0, 50.0, 75.0, 100.0],
    )
    def test_valid_topic_slug_similarity(self, sample_match_data: dict, similarity: float) -> None:
        """Test that valid topic_slug_similarity values are accepted."""
        data = sample_match_data.copy()
        data["topic_slug_similarity"] = similarity
        match = MatchRecord(**data)
        assert match.topic_slug_similarity == similarity

    @pytest.mark.parametrize(
        "invalid_similarity",
        [-0.1, -50.0, 100.1, 150.0, 200.0],
    )
    def test_invalid_topic_slug_similarity(self, sample_match_data: dict, invalid_similarity: float) -> None:
        """Test that invalid topic_slug_similarity values raise ValidationError."""
        data = sample_match_data.copy()
        data["topic_slug_similarity"] = invalid_similarity
        with pytest.raises(ValidationError):
            MatchRecord(**data)

    @pytest.mark.parametrize(
        ("relationship", "confidence", "raw_hash_equal"),
        [
            (RelationshipType.UNCHANGED, 1.0, True),
            (RelationshipType.MODIFIED, 0.9, False),
            (RelationshipType.RENAMED_CANDIDATE, 0.7, False),
        ],
    )
    def test_different_relationship_types(
        self,
        sample_match_data: dict,
        relationship: RelationshipType,
        confidence: float,
        raw_hash_equal: bool,
    ) -> None:
        """Test MatchRecord with different relationship types."""
        data = sample_match_data.copy()
        data["relationship"] = relationship
        data["confidence"] = confidence
        data["raw_hash_equal"] = raw_hash_equal
        match = MatchRecord(**data)
        assert match.relationship == relationship
        assert match.confidence == confidence
        assert match.raw_hash_equal == raw_hash_equal


class TestManifestComparison:
    """Tests for ManifestComparison model."""

    @pytest.fixture
    def sample_match(self) -> MatchRecord:
        """Fixture providing a sample MatchRecord."""
        return MatchRecord(
            old_relative_path="a.html",
            new_relative_path="a.html",
            old_topic_slug="a",
            new_topic_slug="a",
            relationship=RelationshipType.MODIFIED,
            confidence=0.9,
            topic_slug_similarity=100.0,
            raw_hash_equal=False,
        )

    @pytest.fixture
    def sample_doc(self) -> DocumentRecord:
        """Fixture providing a sample DocumentRecord."""
        return DocumentRecord(
            version="1.0.0",
            root="/docs",
            relative_path="test.html",
            topic_slug="test",
            html_filename="test.html",
            raw_hash="xyz789",
        )

    def test_empty_manifest_comparison(self) -> None:
        """Test creating empty ManifestComparison."""
        comparison = ManifestComparison(
            unchanged=[],
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=[],
        )
        assert len(comparison.unchanged) == 0
        assert len(comparison.modified) == 0
        assert comparison.total_changed == 0

    @pytest.mark.parametrize(
        ("num_modified", "num_renamed", "expected_total"),
        [
            (0, 0, 0),
            (1, 0, 1),
            (0, 1, 1),
            (2, 1, 3),
            (5, 3, 8),
            (10, 10, 20),
        ],
    )
    def test_total_changed_property(
        self,
        sample_match: MatchRecord,
        num_modified: int,
        num_renamed: int,
        expected_total: int,
    ) -> None:
        """Test that total_changed correctly sums modified and renamed."""
        modified_match = sample_match.model_copy()
        modified_match.relationship = RelationshipType.MODIFIED

        renamed_match = sample_match.model_copy()
        renamed_match.relationship = RelationshipType.RENAMED_CANDIDATE

        comparison = ManifestComparison(
            unchanged=[],
            modified=[modified_match] * num_modified,
            renamed_candidates=[renamed_match] * num_renamed,
            removed=[],
            added=[],
        )
        assert comparison.total_changed == expected_total

    def test_total_changed_excludes_unchanged(self, sample_match: MatchRecord) -> None:
        """Test that total_changed does not count unchanged documents."""
        unchanged_match = sample_match.model_copy()
        unchanged_match.relationship = RelationshipType.UNCHANGED

        comparison = ManifestComparison(
            unchanged=[unchanged_match] * 5,
            modified=[],
            renamed_candidates=[],
            removed=[],
            added=[],
        )
        assert comparison.total_changed == 0

    def test_manifest_with_all_categories(self, sample_match: MatchRecord, sample_doc: DocumentRecord) -> None:
        """Test ManifestComparison with documents in all categories."""
        comparison = ManifestComparison(
            unchanged=[sample_match],
            modified=[sample_match],
            renamed_candidates=[sample_match],
            removed=[sample_doc],
            added=[sample_doc],
        )
        assert len(comparison.unchanged) == 1
        assert len(comparison.modified) == 1
        assert len(comparison.renamed_candidates) == 1
        assert len(comparison.removed) == 1
        assert len(comparison.added) == 1
        assert comparison.total_changed == 2


class TestDeltaReport:
    """Tests for DeltaReport model."""

    @pytest.fixture
    def empty_delta_data(self) -> dict:
        """Fixture providing empty delta report data."""
        return {
            "old_version": "1.0.0",
            "new_version": "1.1.0",
            "unchanged": [],
            "modified": [],
            "renamed_candidates": [],
            "removed": [],
            "added": [],
        }

    def test_valid_delta_report(self, empty_delta_data: dict) -> None:
        """Test creating valid DeltaReport."""
        report = DeltaReport(**empty_delta_data)
        assert report.old_version == "1.0.0"
        assert report.new_version == "1.1.0"
        assert len(report.unchanged) == 0
        assert len(report.modified) == 0

    @pytest.mark.parametrize(
        ("old_version", "new_version"),
        [
            ("1.0.0", "1.1.0"),
            ("1.0.0", "2.0.0"),
            ("2.5.1", "2.5.2"),
            ("v1", "v2"),
            ("2024-01-01", "2024-01-02"),
        ],
    )
    def test_version_strings(self, empty_delta_data: dict, old_version: str, new_version: str) -> None:
        """Test DeltaReport with various version string formats."""
        data = empty_delta_data.copy()
        data["old_version"] = old_version
        data["new_version"] = new_version
        report = DeltaReport(**data)
        assert report.old_version == old_version
        assert report.new_version == new_version

    def test_delta_report_with_added_documents(self, empty_delta_data: dict) -> None:
        """Test DeltaReport with added documents."""
        doc = DocumentRecord(
            version="1.1.0",
            root="/docs",
            relative_path="new.html",
            topic_slug="new",
            html_filename="new.html",
            raw_hash="xyz789",
        )

        data = empty_delta_data.copy()
        data["added"] = [doc]
        report = DeltaReport(**data)
        assert len(report.added) == 1
        assert report.added[0].topic_slug == "new"

    def test_delta_report_serialization(self, empty_delta_data: dict) -> None:
        """Test that DeltaReport can be serialized and deserialized."""
        report = DeltaReport(**empty_delta_data)
        report_dict = report.model_dump()
        report_restored = DeltaReport(**report_dict)
        assert report == report_restored

    @pytest.mark.parametrize(
        "missing_field",
        ["old_version", "new_version", "unchanged", "modified", "renamed_candidates", "removed", "added"],
    )
    def test_missing_required_fields(self, empty_delta_data: dict, missing_field: str) -> None:
        """Test that missing required fields raise ValidationError."""
        data = empty_delta_data.copy()
        del data[missing_field]
        with pytest.raises(ValidationError) as exc_info:
            DeltaReport(**data)
        assert missing_field in str(exc_info.value)
