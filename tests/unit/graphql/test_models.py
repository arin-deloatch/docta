"""Unit tests for docta.graphql.models module."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import HttpUrl, ValidationError

from docta.graphql.models import (
    SinglePage,
    DocumentationTitleNode,
    DocumentVersion,
    DocumentState,
    QuerySetStats,
    QuerySetState,
    PollingState,
    SSLConfig,
    PollingConfig,
    PipelineConfig,
    QuerySetConfig,
    StateConfig,
    ContentConfig,
    FileLoggingConfig,
    ConsoleLoggingConfig,
    LoggingConfig,
)


class TestSinglePage:
    """Tests for SinglePage model."""

    @pytest.fixture
    def sample_single_page_data(self) -> dict:
        """Fixture providing sample single page data."""
        return {
            "contentUrl": "https://docs.example.com/content/page1.html",
            "modified": "2024-01-15T12:00:00Z",
            "name": "Getting Started",
            "url": "https://docs.example.com/guides/getting-started",
        }

    def test_valid_single_page(self, sample_single_page_data: dict) -> None:
        """Test creating valid SinglePage."""
        page = SinglePage(**sample_single_page_data)
        assert page.name == "Getting Started"
        assert isinstance(page.contentUrl, HttpUrl)
        assert isinstance(page.modified, datetime)

    def test_missing_required_fields(self, sample_single_page_data: dict) -> None:
        """Test that missing required fields raise ValidationError."""
        for field in ["contentUrl", "modified", "name", "url"]:
            data = sample_single_page_data.copy()
            del data[field]
            with pytest.raises(ValidationError):
                SinglePage(**data)


class TestDocumentationTitleNode:
    """Tests for DocumentationTitleNode model."""

    def test_minimal_node(self) -> None:
        """Test node with only required field."""
        node = DocumentationTitleNode(name="Test Doc")
        assert node.name == "Test Doc"
        assert node.singlePage is None
        assert node.revisionId is None
        assert node.modified is None

    def test_full_node(self) -> None:
        """Test node with all fields."""
        page = SinglePage(
            contentUrl="https://docs.example.com/test.html",  # type: ignore[arg-type]
            modified=datetime(2024, 1, 15, 12, 0, 0, tzinfo=None),
            name="Test",
            url="https://docs.example.com/test",  # type: ignore[arg-type]
        )
        node = DocumentationTitleNode(
            name="Test Doc",
            singlePage=page,
            revisionId="rev123",
            modified=datetime(2024, 1, 15, 12, 0, 0, tzinfo=None),
        )
        assert node.singlePage is not None
        assert node.revisionId == "rev123"


class TestDocumentVersion:
    """Tests for DocumentVersion model."""

    @pytest.fixture
    def sample_doc_version_data(self, sample_timestamp: datetime) -> dict:
        """Fixture providing sample document version data."""
        return {
            "modified": sample_timestamp,
            "fetched_at": sample_timestamp,
            "content_hash": "abc123def456",
            "local_path": "/data/docs/test.html",
        }

    def test_valid_document_version(self, sample_doc_version_data: dict) -> None:
        """Test creating valid DocumentVersion."""
        version = DocumentVersion(**sample_doc_version_data)
        assert version.content_hash == "abc123def456"
        assert version.local_path == "/data/docs/test.html"
        assert isinstance(version.modified, datetime)
        assert isinstance(version.fetched_at, datetime)


class TestDocumentState:
    """Tests for DocumentState model."""

    def test_minimal_document_state(self) -> None:
        """Test document state with only required field."""
        state = DocumentState(content_url="https://docs.example.com/test.html")  # type: ignore[arg-type]
        assert state.current_version is None
        assert state.previous_version is None
        assert state.pipeline_status == "pending"
        assert state.pipeline_last_run is None

    def test_document_state_with_versions(self, sample_timestamp: datetime) -> None:
        """Test document state with versions."""
        current = DocumentVersion(
            modified=sample_timestamp,
            fetched_at=sample_timestamp,
            content_hash="new_hash",
            local_path="/data/new.html",
        )
        previous = DocumentVersion(
            modified=sample_timestamp,
            fetched_at=sample_timestamp,
            content_hash="old_hash",
            local_path="/data/old.html",
        )

        state = DocumentState(
            content_url="https://docs.example.com/test.html",  # type: ignore[arg-type]
            current_version=current,
            previous_version=previous,
            pipeline_status="completed",
            pipeline_last_run=sample_timestamp,
        )

        assert state.current_version is not None
        assert state.current_version.content_hash == "new_hash"
        assert state.previous_version is not None
        assert state.previous_version.content_hash == "old_hash"
        assert state.pipeline_status == "completed"


class TestQuerySetStats:
    """Tests for QuerySetStats model."""

    def test_default_stats(self) -> None:
        """Test default statistics values."""
        stats = QuerySetStats()
        assert stats.total_documents == 0
        assert stats.total_polls == 0
        assert stats.documents_with_changes == 0
        assert stats.total_pipeline_runs == 0

    def test_custom_stats(self) -> None:
        """Test custom statistics values."""
        stats = QuerySetStats(
            total_documents=100,
            total_polls=50,
            documents_with_changes=10,
            total_pipeline_runs=5,
        )
        assert stats.total_documents == 100
        assert stats.total_polls == 50
        assert stats.documents_with_changes == 10
        assert stats.total_pipeline_runs == 5


class TestQuerySetState:
    """Tests for QuerySetState model."""

    def test_empty_query_set_state(self) -> None:
        """Test empty query set state."""
        state = QuerySetState()
        assert state.last_poll is None
        assert state.last_success is None
        assert len(state.documents) == 0
        assert state.stats.total_documents == 0  # pylint: disable=no-member  # Pydantic model field

    def test_query_set_state_with_documents(self, sample_timestamp: datetime) -> None:
        """Test query set state with documents."""
        doc_state = DocumentState(content_url="https://docs.example.com/test.html")  # type: ignore[arg-type]

        state = QuerySetState(
            last_poll=sample_timestamp,
            last_success=sample_timestamp,
            documents={"doc1": doc_state},
            stats=QuerySetStats(total_documents=1),
        )

        assert state.last_poll == sample_timestamp
        assert len(state.documents) == 1
        assert "doc1" in state.documents


class TestPollingState:
    """Tests for PollingState model."""

    def test_default_polling_state(self) -> None:
        """Test default polling state."""
        state = PollingState()
        assert state.version == "1.0"
        assert isinstance(state.last_updated, datetime)
        assert len(state.query_sets) == 0

    def test_polling_state_with_query_sets(self) -> None:
        """Test polling state with query sets."""
        qs1 = QuerySetState()
        qs2 = QuerySetState()

        state = PollingState(
            query_sets={"set1": qs1, "set2": qs2},
        )

        assert len(state.query_sets) == 2
        assert "set1" in state.query_sets
        assert "set2" in state.query_sets


class TestSSLConfig:
    """Tests for SSLConfig model."""

    def test_default_ssl_config(self) -> None:
        """Test default SSL configuration."""
        ssl = SSLConfig()
        assert ssl.verify is True
        assert ssl.cert_path is None

    def test_custom_ssl_config(self) -> None:
        """Test custom SSL configuration."""
        ssl = SSLConfig(verify=False, cert_path="/path/to/cert.pem")
        assert ssl.verify is False
        assert ssl.cert_path == "/path/to/cert.pem"


class TestPollingConfig:
    """Tests for PollingConfig model."""

    def test_default_polling_config(self) -> None:
        """Test default polling configuration."""
        config = PollingConfig()
        assert config.interval_minutes == 60
        assert config.initial_delay_seconds == 10
        assert config.retry_attempts == 3
        assert config.retry_backoff_seconds == 30
        assert config.timeout_seconds == 30

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("interval_minutes", 0),  # Too low
            ("interval_minutes", 1500),  # Too high
            ("retry_attempts", -1),  # Negative
            ("retry_attempts", 15),  # Too high
            ("timeout_seconds", 2),  # Too low
            ("timeout_seconds", 500),  # Too high
        ],
    )
    def test_invalid_polling_config_values(self, field: str, value: int) -> None:
        """Test that invalid values raise ValidationError."""
        with pytest.raises(ValidationError):
            PollingConfig(**{field: value})

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("interval_minutes", 1),
            ("interval_minutes", 1440),
            ("retry_attempts", 0),
            ("retry_attempts", 10),
            ("timeout_seconds", 5),
            ("timeout_seconds", 300),
        ],
    )
    def test_valid_polling_config_boundaries(self, field: str, value: int) -> None:
        """Test boundary values for polling config."""
        config = PollingConfig(**{field: value})
        assert getattr(config, field) == value


class TestPipelineConfig:
    """Tests for PipelineConfig model."""

    @pytest.fixture
    def sample_pipeline_config_data(self) -> dict:
        """Fixture providing sample pipeline config data."""
        return {
            "version_label": "v1.0.0",
            "output_dir": "output/test",
            "run_qa_generation": True,
            "qa_config": "config/qa.yaml",
            "max_concurrent_fetches": 10,
        }

    def test_valid_pipeline_config(self, sample_pipeline_config_data: dict) -> None:
        """Test creating valid PipelineConfig."""
        config = PipelineConfig(**sample_pipeline_config_data)
        assert config.version_label == "v1.0.0"
        assert config.output_dir == "output/test"
        assert config.run_qa_generation is True
        assert config.max_concurrent_fetches == 10

    def test_pipeline_config_defaults(self) -> None:
        """Test pipeline config default values."""
        config = PipelineConfig(version_label="v1", output_dir="output")
        assert config.run_qa_generation is True
        assert config.qa_config == "config/system.yaml"
        assert config.max_concurrent_fetches == 10

    @pytest.mark.parametrize(
        "invalid_value",
        [0, -1, 51, 100],
    )
    def test_invalid_max_concurrent_fetches(self, invalid_value: int) -> None:
        """Test that invalid max_concurrent_fetches raises ValidationError."""
        with pytest.raises(ValidationError):
            PipelineConfig(
                version_label="v1",
                output_dir="output",
                max_concurrent_fetches=invalid_value,
            )


class TestQuerySetConfig:
    """Tests for QuerySetConfig model."""

    @pytest.fixture
    def sample_query_set_config_data(self) -> dict:
        """Fixture providing sample query set config data."""
        return {
            "name": "test_query",
            "enabled": True,
            "query": "query { test }",
            "variables": {},
            "pipeline": {
                "version_label": "v1.0.0",
                "output_dir": "output/test",
            },
        }

    def test_valid_query_set_config(self, sample_query_set_config_data: dict) -> None:
        """Test creating valid QuerySetConfig."""
        config = QuerySetConfig(**sample_query_set_config_data)
        assert config.name == "test_query"
        assert config.enabled is True
        assert config.query == "query { test }"

    def test_query_set_config_with_variables(self) -> None:
        """Test query set config with variables."""
        config = QuerySetConfig(
            name="test",
            query="query($id: ID!) { test(id: $id) }",
            variables={"id": "123"},
            pipeline=PipelineConfig(version_label="v1", output_dir="output"),
        )
        assert config.variables == {"id": "123"}


class TestStateConfig:
    """Tests for StateConfig model."""

    def test_default_state_config(self) -> None:
        """Test default state configuration."""
        config = StateConfig()
        assert config.file_path == "config/state/polling_state.json"
        assert config.backup_enabled is True
        assert config.backup_count == 5
        assert config.prune_removed_documents is True
        assert config.cleanup_old_files is True

    def test_custom_state_config(self) -> None:
        """Test custom state configuration."""
        config = StateConfig(
            file_path="/custom/state.json",
            backup_enabled=False,
            backup_count=10,
        )
        assert config.file_path == "/custom/state.json"
        assert config.backup_enabled is False
        assert config.backup_count == 10


class TestContentConfig:
    """Tests for ContentConfig model."""

    def test_default_content_config(self) -> None:
        """Test default content configuration."""
        config = ContentConfig()
        assert config.download_dir == "data/fetched_content"
        assert config.max_file_size_mb == 100
        assert config.timeout_seconds == 60
        assert config.verify_ssl is True

    @pytest.mark.parametrize(
        ("field", "invalid_value"),
        [
            ("max_file_size_mb", 0),
            ("max_file_size_mb", 1500),
            ("timeout_seconds", 5),
            ("timeout_seconds", 500),
        ],
    )
    def test_invalid_content_config_values(self, field: str, invalid_value: int) -> None:
        """Test that invalid values raise ValidationError."""
        with pytest.raises(ValidationError):
            ContentConfig(**{field: invalid_value})  # type: ignore[arg-type]


class TestLoggingConfigs:
    """Tests for logging configuration models."""

    def test_default_file_logging_config(self) -> None:
        """Test default file logging configuration."""
        config = FileLoggingConfig()
        assert config.enabled is False
        assert config.path == "logs/graphql_poller.log"
        assert config.max_size_mb == 50
        assert config.backup_count == 3

    def test_default_console_logging_config(self) -> None:
        """Test default console logging configuration."""
        config = ConsoleLoggingConfig()
        assert config.enabled is True
        assert config.format == "json"

    def test_default_logging_config(self) -> None:
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert isinstance(config.file, FileLoggingConfig)
        assert isinstance(config.console, ConsoleLoggingConfig)

    def test_custom_logging_config(self) -> None:
        """Test custom logging configuration."""
        config = LoggingConfig(
            level="DEBUG",
            file=FileLoggingConfig(enabled=True, max_size_mb=100),
            console=ConsoleLoggingConfig(format="human"),
        )
        assert config.level == "DEBUG"
        assert config.file.enabled is True  # pylint: disable=no-member  # Pydantic model field
        assert config.console.format == "human"  # pylint: disable=no-member  # Pydantic model field
