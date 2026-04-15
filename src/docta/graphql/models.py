"""Pydantic models for GraphQL polling service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# GraphQL Response Models (Relay-style)


class SinglePage(BaseModel):
    """Single page data from GraphQL response."""

    contentUrl: HttpUrl
    modified: datetime
    name: str
    url: HttpUrl


class DocumentationTitleNode(BaseModel):
    """Documentation title node from GraphQL response."""

    name: str
    singlePage: Optional[SinglePage] = None
    revisionId: Optional[str] = None
    modified: Optional[datetime] = None


class DocumentationTitleEdge(BaseModel):
    """Relay-style edge wrapper."""

    node: DocumentationTitleNode


class DocumentationTitlesData(BaseModel):
    """Documentation titles query result."""

    edges: list[DocumentationTitleEdge]


class DocumentationTitlesResponse(BaseModel):
    """Full GraphQL response wrapper."""

    documentation_titles: DocumentationTitlesData


# State Tracking Models


class DocumentVersion(BaseModel):
    """Tracks a single version of a document."""

    modified: datetime
    fetched_at: datetime
    content_hash: str
    local_path: str


class DocumentState(BaseModel):
    """Tracks current and previous versions of a document."""

    content_url: HttpUrl
    current_version: Optional[DocumentVersion] = None
    previous_version: Optional[DocumentVersion] = None
    pipeline_status: str = "pending"  # pending, running, completed, failed
    pipeline_last_run: Optional[datetime] = None


class QuerySetStats(BaseModel):
    """Statistics for a query set."""

    total_documents: int = 0
    total_polls: int = 0
    documents_with_changes: int = 0
    total_pipeline_runs: int = 0


class QuerySetState(BaseModel):
    """State tracking for a single query set."""

    last_poll: Optional[datetime] = None
    last_success: Optional[datetime] = None
    documents: dict[str, DocumentState] = Field(default_factory=dict)
    stats: QuerySetStats = Field(default_factory=QuerySetStats)


class PollingState(BaseModel):
    """Complete polling state for all query sets."""

    version: str = "1.0"
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
    query_sets: dict[str, QuerySetState] = Field(default_factory=dict)


# Configuration Models


class SSLConfig(BaseModel):
    """SSL/TLS configuration."""

    verify: bool = True
    cert_path: Optional[str] = None


class PollingConfig(BaseModel):
    """Polling behavior configuration."""

    interval_minutes: int = Field(default=60, ge=1, le=1440)
    initial_delay_seconds: int = Field(default=10, ge=0)
    retry_attempts: int = Field(default=3, ge=0, le=10)
    retry_backoff_seconds: int = Field(default=30, ge=1)
    timeout_seconds: int = Field(default=30, ge=5, le=300)


class PipelineConfig(BaseModel):
    """Pipeline execution configuration for a query set."""

    version_label: str
    output_dir: str
    run_qa_generation: bool = True
    qa_config: str = "config/system.yaml"
    max_concurrent_fetches: int = Field(default=10, ge=1, le=50)


class QuerySetConfig(BaseModel):
    """Configuration for a single query set."""

    name: str
    enabled: bool = True
    query: str
    variables: dict
    pipeline: PipelineConfig


class GraphQLAPIConfig(BaseModel):
    """GraphQL API configuration."""

    endpoint: HttpUrl
    api_scope: str = "api.graphql"
    apollographql_client_version: str = "latest"
    ssl: SSLConfig = Field(default_factory=SSLConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    query_sets: list[QuerySetConfig]


class StateConfig(BaseModel):
    """State file configuration."""

    file_path: str = "config/state/polling_state.json"
    backup_enabled: bool = True
    backup_count: int = Field(default=5, ge=0, le=20)
    prune_removed_documents: bool = True
    cleanup_old_files: bool = True


class ContentConfig(BaseModel):
    """Content fetching configuration."""

    download_dir: str = "data/fetched_content"
    max_file_size_mb: int = Field(default=100, ge=1, le=1000)
    timeout_seconds: int = Field(default=60, ge=10, le=300)
    verify_ssl: bool = True


class FileLoggingConfig(BaseModel):
    """File logging configuration."""

    enabled: bool = False
    path: str = "logs/graphql_poller.log"
    max_size_mb: int = Field(default=50, ge=1, le=500)
    backup_count: int = Field(default=3, ge=0, le=10)


class ConsoleLoggingConfig(BaseModel):
    """Console logging configuration."""

    enabled: bool = True
    format: str = "json"  # json or human


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    file: FileLoggingConfig = Field(default_factory=FileLoggingConfig)
    console: ConsoleLoggingConfig = Field(default_factory=ConsoleLoggingConfig)


class GraphQLPollingSettings(BaseSettings):
    """Main settings loaded from YAML + environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # OAuth 2.0 credentials (from environment only)
    graphql_client_id: SecretStr
    graphql_client_secret: SecretStr
    graphql_token_url: HttpUrl

    # Apollo GraphQL headers (from environment)
    apollographql_client_name: SecretStr

    # Optional custom CA cert (from environment)
    graphql_cert_path: Optional[str] = None

    # Configuration from YAML
    graphql: GraphQLAPIConfig
    state: StateConfig = Field(default_factory=StateConfig)
    content: ContentConfig = Field(default_factory=ContentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
