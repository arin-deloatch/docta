"""RAGAS-based QA pair generator implementation."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.exceptions import OutputParserException
from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers.multi_hop.abstract import (
    MultiHopAbstractQuerySynthesizer,
)
from ragas.testset.synthesizers.multi_hop.specific import (
    MultiHopSpecificQuerySynthesizer,
)
from ragas.testset.synthesizers.single_hop.specific import (
    SingleHopSpecificQuerySynthesizer,
)

from docta.utils.constants import (
    DOC_ID_MARKER_TEMPLATE,
    DOC_ID_PATTERN_STR,
    MIN_CONTENT_LENGTH_FOR_MATCHING,
    QA_CONTENT_PREVIEW_LENGTH,
)
from qa_generation.config.settings import QAGenerationSettings
from qa_generation.generators.base import (
    ConfigurationError,
    LLMError,
    QAGenerationError,
)
from qa_generation.llm.provider import create_testset_generator
from qa_generation.models import (
    GeneratorConfig,
    QAPair,
    QASourceDocument,
    SourceDocumentInfo,
)

logger = structlog.get_logger(__name__)


class RAGASQAGenerator:  # pylint: disable=too-few-public-methods
    """QA pair generator using RAGAS framework.

    Implements the QAGenerator protocol using RAGAS's TestsetGenerator
    for synthetic question-answer pair generation.

    This class structurally implements the QAGenerator protocol (base.py:11-40).
    Protocol compliance is verified via runtime isinstance() checks and tests.
    """

    def __init__(self, settings: QAGenerationSettings) -> None:
        """Initialize RAGAS generator.

        IMPORTANT: Call settings.setup_environment() before creating this generator
        to ensure API keys are configured.

        Args:
            settings: Complete QA generation settings

        Raises:
            ConfigurationError: If settings are invalid
            ImportError: If RAGAS dependencies are not installed
        """
        self.settings = settings
        self._generator: TestsetGenerator | None = None
        logger.info("ragas_generator_initialized", llm_provider=settings.llm_provider)

    def _ensure_generator(self) -> TestsetGenerator:
        """Lazy-load the RAGAS generator.

        Returns:
            Configured TestsetGenerator

        Raises:
            ConfigurationError: If generator creation fails
        """
        if self._generator is None:
            try:
                self._generator = create_testset_generator(self.settings)
            except ValueError as e:
                raise ConfigurationError(f"Invalid configuration: {e}") from e
            except ImportError as e:
                raise ConfigurationError(f"Missing dependencies: {e}. " "Install with: uv sync --extra qa") from e
        return self._generator

    @staticmethod
    def _extract_versions(metadata: dict[str, Any]) -> tuple[str, str] | None:
        """Extract (old_version, new_version) from metadata if available.

        Args:
            metadata: Document metadata dictionary

        Returns:
            Tuple of (old_version, new_version) if both present, else None
        """
        if "versions" not in metadata:
            return None
        vers = metadata["versions"]
        if not isinstance(vers, dict):
            return None
        old_ver = vers.get("old")
        new_ver = vers.get("new")
        return (old_ver, new_ver) if old_ver and new_ver else None

    def generate(  # pylint: disable=too-many-locals
        self,
        documents: list[QASourceDocument],
        config: GeneratorConfig,
    ) -> list[QAPair]:
        """Generate QA pairs from source documents using RAGAS.

        Args:
            documents: List of QASourceDocument to generate from
            config: GeneratorConfig with generation parameters

        Returns:
            List of generated QAPair objects with traceability

        Raises:
            ValueError: If documents list is empty or invalid
            ConfigurationError: If configuration is invalid
            LLMError: If LLM API calls fail
            QAGenerationError: If generation fails for other reasons
        """
        if not documents:
            raise ValueError("Documents list cannot be empty")

        logger.info(
            "starting_qa_generation",
            num_documents=len(documents),
            testset_size=config.testset_size,
        )

        # Convert to RAGAS Document format
        try:
            ragas_docs = self._convert_to_ragas_documents(documents)
        except Exception as e:
            raise QAGenerationError(f"Failed to convert documents: {e}") from e

        # Create RAGAS query distribution as list of (Synthesizer, weight) tuples
        # Maps our config distribution to RAGAS synthesizer classes
        try:
            ragas_dist = self._build_query_distribution(config)
        except Exception as e:
            raise ConfigurationError(f"Failed to build query distribution: {e}") from e

        # Generate test set with robust error handling
        testset, failed_doc_indices = self._generate_with_retry(ragas_docs, config, ragas_dist)

        # Log failures if any
        if failed_doc_indices:
            failed_topics = [documents[idx].topic_slug for idx in failed_doc_indices if idx < len(documents)]
            logger.warning(
                "generation_skipped_problematic_documents",
                failed_count=len(failed_doc_indices),
                failed_topics=failed_topics[:10],  # Log first 10
                total_documents=len(documents),
            )

        # Convert RAGAS output to QAPair objects
        try:
            qa_pairs = self._convert_from_ragas_testset(testset, documents)
        except Exception as e:
            raise QAGenerationError(f"Failed to convert RAGAS output: {e}") from e

        logger.info("qa_generation_complete", num_pairs=len(qa_pairs))
        return qa_pairs

    def _generate_with_retry(
        self,
        ragas_docs: list[Document],
        config: GeneratorConfig,
        ragas_dist: list[tuple[Any, float]],
    ) -> tuple[Any, list[int]]:
        """Generate QA pairs with robust error handling and retry logic.

        Strategy:
        1. Try generating from all documents
        2. If OutputParserException occurs, fall back to batch processing
        3. Track and skip problematic documents
        4. Return successful results + list of failed document indices

        Args:
            ragas_docs: RAGAS Document objects
            config: Generator configuration
            ragas_dist: RAGAS query distribution

        Returns:
            Tuple of (testset, list of failed document indices)

        Raises:
            ConfigurationError: If configuration is invalid
            LLMError: If LLM API calls fail
            QAGenerationError: If generation fails completely
        """
        generator = self._ensure_generator()
        failed_indices: list[int] = []

        # Try 1: Generate from all documents at once (most efficient)
        try:
            logger.info(
                "calling_ragas_generate",
                testset_size=config.testset_size,
                num_documents=len(ragas_docs),
            )

            testset = generator.generate_with_langchain_docs(
                documents=ragas_docs,
                testset_size=config.testset_size,
                query_distribution=ragas_dist,
                raise_exceptions=True,
            )

            logger.info("ragas_generation_complete")
            return testset, failed_indices

        except ImportError as e:
            raise ConfigurationError(f"Missing RAGAS dependencies: {e}") from e

        except OutputParserException as e:
            # OutputParserException means LLM returned invalid JSON - try batch fallback
            logger.warning(
                "output_parser_error_falling_back_to_batch_processing",
                error=str(e)[:200],
                num_documents=len(ragas_docs),
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            # Check if it's an API error
            error_msg = str(e).lower()
            error_type = type(e).__name__

            if any(
                keyword in error_msg
                for keyword in [
                    "api",
                    "rate limit",
                    "quota",
                    "authentication",
                    "401",
                    "429",
                ]
            ):
                raise LLMError(f"LLM API error ({error_type}). " "Check API key, rate limits, and quota.") from e

            # For other errors, try batch fallback
            logger.warning(
                "generation_error_falling_back_to_batch_processing",
                error_type=error_type,
                error=str(e)[:200],
            )

        # Try 2: Process in batches (slower but more robust)
        return self._generate_in_batches(ragas_docs, config, ragas_dist, generator)

    def _generate_in_batches(
        self,
        ragas_docs: list[Document],
        config: GeneratorConfig,
        ragas_dist: list[tuple[Any, float]],
        generator: TestsetGenerator,
    ) -> tuple[Any, list[int]]:
        """Process documents in batches, skipping problematic ones.

        Args:
            ragas_docs: RAGAS Document objects
            config: Generator configuration
            ragas_dist: RAGAS query distribution
            generator: RAGAS TestsetGenerator instance

        Returns:
            Tuple of (combined testset, list of failed document indices)
        """
        batch_size = max(1, len(ragas_docs) // 10)  # 10% batches
        failed_indices: list[int] = []
        all_samples = []

        logger.info(
            "batch_processing_documents",
            total_documents=len(ragas_docs),
            batch_size=batch_size,
        )

        for batch_start in range(0, len(ragas_docs), batch_size):
            batch_end = min(batch_start + batch_size, len(ragas_docs))
            batch_docs = ragas_docs[batch_start:batch_end]
            batch_testset_size = max(1, int(config.testset_size * len(batch_docs) / len(ragas_docs)))

            try:
                logger.debug(
                    "processing_batch",
                    batch_start=batch_start,
                    batch_end=batch_end,
                    batch_size=len(batch_docs),
                    batch_testset_size=batch_testset_size,
                )

                testset = generator.generate_with_langchain_docs(
                    documents=batch_docs,
                    testset_size=batch_testset_size,
                    query_distribution=ragas_dist,
                    raise_exceptions=False,  # Don't raise on errors in batch mode
                )

                # Collect samples from this batch
                try:
                    to_pandas_method = getattr(testset, "to_pandas", None)
                    if to_pandas_method is not None:
                        df = to_pandas_method()
                        if not df.empty:
                            all_samples.extend(df.to_dict("records"))
                            logger.debug(
                                "batch_completed",
                                batch_start=batch_start,
                                samples_generated=len(df),
                            )
                except (AttributeError, TypeError) as e:
                    logger.warning(
                        "testset_conversion_failed",
                        batch_start=batch_start,
                        testset_type=type(testset).__name__,
                        error=str(e)[:100],
                    )

            except OutputParserException as e:
                # This batch has problematic content - skip it
                logger.warning(
                    "batch_skipped_output_parser_error",
                    batch_start=batch_start,
                    batch_end=batch_end,
                    error=str(e)[:200],
                )
                failed_indices.extend(range(batch_start, batch_end))

            except Exception as e:  # pylint: disable=broad-exception-caught
                # Check for API errors that should be escalated
                error_msg = str(e).lower()
                if any(
                    keyword in error_msg
                    for keyword in [
                        "api",
                        "rate limit",
                        "quota",
                        "authentication",
                        "401",
                        "429",
                    ]
                ):
                    raise LLMError(f"LLM API error during batch processing ({type(e).__name__}). " "Check API key, rate limits, and quota.") from e
                # Skip this batch for other errors
                logger.warning(
                    "batch_skipped_error",
                    batch_start=batch_start,
                    batch_end=batch_end,
                    error_type=type(e).__name__,
                    error=str(e)[:200],
                )
                failed_indices.extend(range(batch_start, batch_end))

        # Combine all successful samples into a testset-like object
        if all_samples:
            logger.info(
                "batch_processing_complete",
                total_samples=len(all_samples),
                failed_documents=len(failed_indices),
            )

            # Convert back to testset format
            # RAGAS testset has a to_pandas() method, so we need to simulate that
            # We'll create a mock object that has the samples
            class MockTestset:  # pylint: disable=missing-class-docstring,too-few-public-methods
                def __init__(self, samples: list) -> None:
                    self.samples = samples

                def to_pandas(self):  # type: ignore[no-untyped-def]  # Pandas DataFrame return type  # pylint: disable=missing-function-docstring
                    import pandas as pd  # type: ignore[import-untyped]  # pylint: disable=import-outside-toplevel

                    return pd.DataFrame(self.samples)

            return MockTestset(all_samples), failed_indices

        # If we got no samples at all, raise an error
        raise QAGenerationError(f"Failed to generate any QA pairs. " f"All {len(ragas_docs)} documents failed processing. " f"Try with fewer documents or simpler content.")

    def _convert_to_ragas_documents(self, documents: list[QASourceDocument]) -> list[Document]:
        """Convert QASourceDocument to RAGAS Document format.

        Embeds a unique document ID marker in the content for traceability matching,
        since RAGAS doesn't preserve document metadata in output.

        Args:
            documents: List of QASourceDocument

        Returns:
            List of langchain Document objects with embedded doc IDs
        """
        ragas_docs = []
        for idx, doc in enumerate(documents):
            # Embed doc ID marker that we can extract later from contexts
            # Using HTML-style comment that's unlikely to interfere with QA generation
            marked_content = DOC_ID_MARKER_TEMPLATE.format(idx, doc.content)

            metadata = {
                **doc.metadata,
                "topic_slug": doc.topic_slug,
                "location": doc.location,
                "change_type": doc.change_type,
            }
            ragas_docs.append(Document(page_content=marked_content, metadata=metadata))

        logger.debug(
            "converted_to_ragas_documents",
            num_documents=len(ragas_docs),
            total_chars=sum(len(d.page_content) for d in ragas_docs),
        )
        return ragas_docs

    def _build_query_distribution(self, config: GeneratorConfig) -> list[tuple[Any, float]]:
        """Build RAGAS query distribution from config.

        RAGAS expects a list of (Synthesizer, weight) tuples where weights
        represent the proportion of questions of each type.

        Maps our QueryDistribution to RAGAS synthesizers:
        - specific → SingleHopSpecificQuerySynthesizer (simple factual, single context)
        - abstract → MultiHopAbstractQuerySynthesizer (reasoning, multiple contexts)
        - comparative → MultiHopSpecificQuerySynthesizer (comparisons, multiple contexts)

        Args:
            config: Generator configuration with query distribution

        Returns:
            List of (Synthesizer instance, weight) tuples for RAGAS

        Raises:
            ImportError: If RAGAS synthesizers are not available
        """
        # Get or create the generator to access LLM
        generator = self._ensure_generator()

        # Build distribution list with synthesizers and weights
        distribution: list[tuple] = []  # type: ignore[type-arg]

        if config.query_distribution.specific > 0:
            specific_synth = SingleHopSpecificQuerySynthesizer(llm=generator.llm)
            distribution.append((specific_synth, config.query_distribution.specific))  # type: ignore[arg-type]

        if config.query_distribution.abstract > 0:
            abstract_synth = MultiHopAbstractQuerySynthesizer(llm=generator.llm)  # type: ignore[assignment]
            distribution.append((abstract_synth, config.query_distribution.abstract))  # type: ignore[arg-type]

        if config.query_distribution.comparative > 0:
            comparative_synth = MultiHopSpecificQuerySynthesizer(llm=generator.llm)  # type: ignore[assignment]
            distribution.append((comparative_synth, config.query_distribution.comparative))  # type: ignore[arg-type]

        if not distribution:
            raise ValueError("Query distribution must have at least one non-zero weight")

        logger.debug(
            "query_distribution_built",
            num_synthesizers=len(distribution),
            weights=[w for _, w in distribution],
        )

        return distribution

    def _extract_from_doc_id_markers(
        self,
        row: Any,
        doc_id_pattern: re.Pattern[str],
        id_to_doc: dict[int, QASourceDocument],
    ) -> SourceDocumentInfo | None:
        """Extract source document info from embedded doc ID markers.

        Args:
            row: DataFrame row from RAGAS testset
            doc_id_pattern: Compiled regex to match <!--DOC_ID:N-->
            id_to_doc: Mapping from document index to QASourceDocument

        Returns:
            SourceDocumentInfo if marker found and matched, else None
        """
        # RAGAS field names vary by version and generation mode
        possible_context_fields = [
            "retrieved_contexts",
            "contexts",
            "reference_contexts",
            "reference",
        ]

        for field in possible_context_fields:
            if field not in row or not row[field]:
                continue

            # Handle both list and string values
            contexts_data = row[field]
            if isinstance(contexts_data, str):
                contexts_data = [contexts_data]
            elif not isinstance(contexts_data, list):
                continue

            # Search for doc ID marker in all contexts
            for context in contexts_data:
                context_str = str(context)
                match = doc_id_pattern.search(context_str)

                if match:
                    source_id = int(match.group(1))
                    matched_doc = id_to_doc.get(source_id)

                    if matched_doc:
                        versions = self._extract_versions(matched_doc.metadata)

                        logger.debug(
                            "traceability_matched",
                            field=field,
                            source_id=source_id,
                            topic_slug=matched_doc.topic_slug,
                        )
                        return SourceDocumentInfo(
                            topic_slug=matched_doc.topic_slug,
                            location=matched_doc.location,
                            change_type=matched_doc.change_type,
                            versions=versions,
                            metadata=matched_doc.metadata,
                        )

                    logger.warning(
                        "traceability_id_not_found",
                        source_id=source_id,
                        num_source_docs=len(id_to_doc),
                    )
        return None

    def _match_by_content(
        self,
        ground_truth: str,
        doc_id_pattern: re.Pattern[str],
        source_documents: list[QASourceDocument],
    ) -> SourceDocumentInfo | None:
        """Try to match QA pair to source document by content similarity.

        Args:
            ground_truth: The ground truth answer text
            doc_id_pattern: Compiled regex to strip markers
            source_documents: List of source documents to match against

        Returns:
            SourceDocumentInfo if matched, else None
        """
        # Remove doc ID markers from ground truth for matching
        clean_ground_truth = doc_id_pattern.sub("", ground_truth).strip()

        # Try to find which source document this answer came from
        for idx, doc in enumerate(source_documents):
            # Check if ground truth contains substantial content from this doc
            if len(clean_ground_truth) > MIN_CONTENT_LENGTH_FOR_MATCHING and clean_ground_truth[:QA_CONTENT_PREVIEW_LENGTH] in doc.content:
                versions = self._extract_versions(doc.metadata)

                logger.debug(
                    "traceability_matched_by_content",
                    source_idx=idx,
                    topic_slug=doc.topic_slug,
                )
                return SourceDocumentInfo(
                    topic_slug=doc.topic_slug,
                    location=doc.location,
                    change_type=doc.change_type,
                    versions=versions,
                    metadata=doc.metadata,
                )
        return None

    def _find_source_document(
        self,
        row: Any,
        ground_truth: str,
        *,
        doc_id_pattern: re.Pattern[str],
        id_to_doc: dict[int, QASourceDocument],
        source_documents: list[QASourceDocument],
    ) -> SourceDocumentInfo:
        """Find source document for a QA pair using multiple strategies.

        Tries in order:
        1. Embedded doc ID markers in context fields
        2. Content similarity matching

        Args:
            row: DataFrame row from RAGAS testset
            ground_truth: Ground truth answer text
            doc_id_pattern: Compiled regex for doc ID markers
            id_to_doc: Mapping from index to QASourceDocument
            source_documents: List of all source documents

        Returns:
            SourceDocumentInfo with traceability data, or default "unknown" if not found
        """
        # Strategy 1: Try embedded doc ID markers
        source_info = self._extract_from_doc_id_markers(row, doc_id_pattern, id_to_doc)
        if source_info:
            return source_info

        # Strategy 2: Try content similarity matching
        if ground_truth:
            source_info = self._match_by_content(ground_truth, doc_id_pattern, source_documents)
            if source_info:
                return source_info

        # No match found - log warning and return default
        logger.warning(
            "no_traceability_found",
            available_fields=list(row.keys()),
            question_preview=(row.get("user_input", "")[:QA_CONTENT_PREVIEW_LENGTH] if row.get("user_input") else None),
            reference_preview=(ground_truth[:QA_CONTENT_PREVIEW_LENGTH] if ground_truth else None),
        )
        return SourceDocumentInfo(
            topic_slug="unknown",
            location=None,
            change_type=None,
            versions=None,
            metadata={},
        )

    def _build_qa_pair(self, row: Any, source_info: SourceDocumentInfo) -> QAPair:
        """Build QAPair from RAGAS row and source document info.

        Args:
            row: DataFrame row from RAGAS testset
            source_info: Traceability information from source matching

        Returns:
            QAPair with all fields populated
        """
        question = row.get("user_input", "")
        ground_truth = row.get("reference", "")
        question_type = row.get("synthesizer_name")

        # Extract metadata, filtering out None values
        metadata = {
            "query_style": row.get("query_style"),
            "query_length": row.get("query_length"),
            "persona_name": row.get("persona_name"),
        }
        filtered_metadata = {k: v for k, v in metadata.items() if v is not None}

        # Add timestamp
        filtered_metadata["generated_at"] = datetime.now(timezone.utc).isoformat()

        # Add content metadata from source
        # For modified content: change_description, old_content, new_content
        # For added content: document_content
        if source_info.metadata:
            for key in [
                "change_description",
                "old_content",
                "new_content",
                "document_content",
            ]:
                if key in source_info.metadata:
                    value = source_info.metadata[key]
                    filtered_metadata[key] = value

                    # Warn on large content fields (>5KB)
                    if isinstance(value, str) and len(value) > 5000:
                        logger.warning(
                            "large_metadata_field",
                            field=key,
                            size_bytes=len(value.encode("utf-8")),
                            qa_pair_preview=question[:50],
                        )

        return QAPair(
            question=question,
            ground_truth_answer=ground_truth,
            source_topic_slug=source_info.topic_slug,
            source_location=source_info.location,
            source_change_type=source_info.change_type,
            source_versions=source_info.versions,
            question_type=question_type,
            metadata=filtered_metadata,
        )

    def _convert_from_ragas_testset(self, testset: Any, source_documents: list[QASourceDocument]) -> list[QAPair]:
        """Convert RAGAS testset to QAPair objects.

        Extracts embedded document ID markers from contexts to restore traceability.

        Args:
            testset: RAGAS testset object
            source_documents: Original source documents for traceability

        Returns:
            List of QAPair objects with traceability information

        Raises:
            QAGenerationError: If testset cannot be converted to DataFrame
        """
        # Convert to pandas DataFrame for easier processing
        try:
            df = testset.to_pandas()
        except AttributeError as e:
            raise QAGenerationError(f"RAGAS testset missing to_pandas() method: {e}") from e

        logger.debug(
            "ragas_testset_columns",
            columns=list(df.columns),
            num_rows=len(df),
        )

        # Build lookup by index for fast traceability matching
        id_to_doc = dict(enumerate(source_documents))

        # Pattern to extract embedded doc ID: <!--DOC_ID:123-->
        doc_id_pattern = re.compile(DOC_ID_PATTERN_STR)

        qa_pairs = []
        for _, row in df.iterrows():
            ground_truth = row.get("reference", "")

            # Find source document using multiple strategies
            source_info = self._find_source_document(
                row=row,
                ground_truth=ground_truth,
                doc_id_pattern=doc_id_pattern,
                id_to_doc=id_to_doc,
                source_documents=source_documents,
            )

            # Build QA pair from row and matched source
            qa_pair = self._build_qa_pair(row, source_info)
            qa_pairs.append(qa_pair)

        logger.debug("converted_from_ragas_testset", num_pairs=len(qa_pairs))
        return qa_pairs
