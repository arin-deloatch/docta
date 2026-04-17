"""Main orchestrator for QA generation pipeline.

Coordinates the full pipeline:
1. Load semantic diff report
2. Extract and filter snippets
3. Convert to QA source documents
4. Generate QA pairs via RAGAS
5. Write output files
"""

from __future__ import annotations

from pathlib import Path

import structlog

from qa_generation.config.settings import QAGenerationSettings
from qa_generation.generators import RAGASQAGenerator
from qa_generation.ingest.added_doc_converter import convert_added_documents
from qa_generation.ingest.added_doc_processor import (
    extract_added_documents,
    read_delta_report,
)
from qa_generation.ingest.diff_report_reader import read_diff_report
from qa_generation.ingest.snippet_extractor import extract_snippets
from qa_generation.models import (
    AddedDocumentStats,
    GeneratorConfig,
    QAPair,
    QASourceDocument,
)
from qa_generation.output import write_qa_pairs

logger = structlog.get_logger(__name__)


def _generate_stratified_by_topic(  # pylint: disable=too-many-locals
    source_documents: list[QASourceDocument],
    generator: RAGASQAGenerator,
    config: GeneratorConfig,
    total_testset_size: int,
) -> list[QAPair]:
    """Generate QA pairs with stratified sampling across topics.

    Ensures coverage across all topics by:
    1. Grouping source documents by topic_slug
    2. Allocating QA quota per topic (equal distribution)
    3. Generating separately for each topic (multiple RAGAS calls)
    4. Combining results

    This prevents large documents from dominating QA generation.

    Args:
        source_documents: All source documents to generate from
        generator: RAGASQAGenerator instance
        config: Generator configuration
        total_testset_size: Total number of QA pairs to generate

    Returns:
        Combined list of QA pairs from all topics
    """
    # Group documents by topic_slug
    topic_groups: dict[str, list[QASourceDocument]] = {}
    for doc in source_documents:
        topic_slug = doc.topic_slug or "unknown"
        if topic_slug not in topic_groups:
            topic_groups[topic_slug] = []
        topic_groups[topic_slug].append(doc)

    num_topics = len(topic_groups)
    logger.info(
        "stratified_generation_started",
        num_topics=num_topics,
        total_testset_size=total_testset_size,
        total_source_documents=len(source_documents),
    )

    # Calculate per-topic quota (equal distribution)
    base_quota = total_testset_size // num_topics
    remainder = total_testset_size % num_topics

    # Log topic distribution
    for topic_slug, docs in sorted(topic_groups.items()):
        logger.info(
            "topic_group",
            topic_slug=topic_slug,
            num_source_documents=len(docs),
            total_chars=sum(doc.char_count for doc in docs),
        )

    all_qa_pairs: list[QAPair] = []

    # Generate for each topic
    for idx, (topic_slug, topic_docs) in enumerate(sorted(topic_groups.items())):
        # Give first 'remainder' topics an extra QA pair
        topic_quota = base_quota + (1 if idx < remainder else 0)

        if topic_quota == 0:
            logger.warning(
                "topic_skipped_zero_quota",
                topic_slug=topic_slug,
                num_source_documents=len(topic_docs),
            )
            continue

        logger.info(
            "generating_for_topic",
            topic_slug=topic_slug,
            num_source_documents=len(topic_docs),
            topic_quota=topic_quota,
            progress=f"{idx + 1}/{num_topics}",
        )

        # Create topic-specific config with adjusted testset_size
        topic_config = GeneratorConfig(
            testset_size=topic_quota,
            query_distribution=config.query_distribution,
            filtering=config.filtering,
        )

        try:
            # Generate QA pairs for this topic
            topic_qa_pairs = generator.generate(topic_docs, topic_config)

            logger.info(
                "topic_generation_complete",
                topic_slug=topic_slug,
                requested=topic_quota,
                generated=len(topic_qa_pairs),
            )

            all_qa_pairs.extend(topic_qa_pairs)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "topic_generation_failed",
                topic_slug=topic_slug,
                error_type=type(e).__name__,
                error=str(e)[:200],
            )
            # Continue with other topics rather than failing completely
            continue

    logger.info(
        "stratified_generation_complete",
        total_topics=num_topics,
        total_qa_pairs=len(all_qa_pairs),
        requested=total_testset_size,
    )

    # Fail if we had source documents but generated nothing
    if not all_qa_pairs and source_documents:
        raise RuntimeError(f"Stratified generation failed: no QA pairs generated from " f"{len(source_documents)} source documents across {num_topics} topics")

    return all_qa_pairs


def generate_qa_from_report(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    report_path: str | Path,
    output_path: str | Path,
    settings: QAGenerationSettings,
    output_format: str = "json",
    allow_overwrite: bool = False,
    num_documents: int | None = None,
) -> list[QAPair]:
    """Generate QA pairs from a semantic diff report.

    This is the main entry point for the QA generation pipeline.

    Args:
        report_path: Path to semantic diff report JSON file
        output_path: Path to write QA pairs (JSON or YAML)
        settings: QA generation settings
        output_format: Output format ("json" or "yaml")
        allow_overwrite: Allow overwriting existing output file
        num_documents: Limit number of documents to process (None = all)

    Returns:
        List of generated QAPair objects

    Raises:
        FileNotFoundError: If report file not found
        ValueError: If report is invalid or no snippets extracted
        QAGenerationError: If generation fails
        QAWriteError: If writing output fails
    """
    report_path = Path(report_path)
    output_path = Path(output_path)

    logger.info(
        "starting_qa_generation_pipeline",
        report_path=str(report_path),
        output_path=str(output_path),
        testset_size=settings.testset_size,
    )

    # Step 0: Set up environment variables for LLM/embeddings
    logger.info("setting_up_environment")
    settings.setup_environment()

    # Step 1: Load semantic diff report
    logger.info("loading_diff_report", path=str(report_path))
    report = read_diff_report(report_path)
    logger.info(
        "diff_report_loaded",
        num_results=len(report.results),
        old_version=report.old_version,
        new_version=report.new_version,
    )

    # Step 2: Extract snippets with optional limit
    logger.info("extracting_snippets", max_documents=num_documents)
    generator_config = settings.to_generator_config()
    snippets, stats = extract_snippets(
        report,
        generator_config.filtering,
        max_documents=num_documents,
    )

    logger.info(
        "snippets_extracted",
        extracted=stats.extracted_snippets,
        total_filtered=stats.total_filtered,
        extraction_rate=f"{stats.extraction_rate:.1f}%",
    )

    if not snippets:
        raise ValueError(f"No snippets extracted from report. " f"Total changes: {stats.total_changes}, " f"Filtered: {stats.total_filtered}. " f"Try adjusting filter settings.")

    # Step 3: Snippets are already QASourceDocument objects
    source_documents = snippets

    # Count unique topics for stratification decision
    unique_topics = set(doc.topic_slug for doc in source_documents if doc.topic_slug)
    num_topics = len(unique_topics)

    logger.info(
        "source_documents_ready",
        num_documents=len(source_documents),
        num_topics=num_topics,
        total_chars=sum(doc.char_count for doc in source_documents),
    )

    # Step 4: Generate QA pairs with stratified sampling
    logger.info("initializing_ragas_generator")
    generator = RAGASQAGenerator(settings)

    if num_topics > 1:
        logger.info(
            "using_stratified_generation",
            num_topics=num_topics,
            testset_size=generator_config.testset_size,
        )
        qa_pairs = _generate_stratified_by_topic(
            source_documents,
            generator,
            generator_config,
            generator_config.testset_size,
        )
    else:
        logger.info(
            "using_single_pass_generation",
            num_topics=num_topics,
            testset_size=generator_config.testset_size,
        )
        qa_pairs = generator.generate(source_documents, generator_config)

    logger.info(
        "qa_pairs_generated",
        num_pairs=len(qa_pairs),
        avg_question_length=(sum(p.question_length for p in qa_pairs) / len(qa_pairs) if qa_pairs else 0),
    )

    # Step 5: Write output
    logger.info("writing_qa_pairs", format=output_format, path=str(output_path))
    write_qa_pairs(
        qa_pairs,
        output_path,
        output_format=output_format,
        allow_overwrite=allow_overwrite,
    )

    logger.info(
        "qa_generation_pipeline_complete",
        num_pairs=len(qa_pairs),
        output_path=str(output_path),
    )

    return qa_pairs


def generate_qa_from_delta_report(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    delta_report_path: str | Path,
    output_path: str | Path,
    settings: QAGenerationSettings,
    output_format: str = "json",
    allow_overwrite: bool = False,
    num_documents: int | None = None,
) -> list[QAPair]:
    """Generate QA pairs from delta report (added documents only).

    This is a parallel entry point for processing net-new documents
    that don't have semantic diffs.

    Args:
        delta_report_path: Path to delta_report.json file
        output_path: Path to write QA pairs (JSON or YAML)
        settings: QA generation settings
        output_format: Output format ("json" or "yaml")
        allow_overwrite: Allow overwriting existing output file
        num_documents: Limit number of added documents to process (None = all)

    Returns:
        List of generated QAPair objects

    Raises:
        FileNotFoundError: If delta report not found
        ValueError: If no added documents or no source documents after filtering
        QAGenerationError: If generation fails
        QAWriteError: If writing output fails
    """
    delta_report_path = Path(delta_report_path)
    output_path = Path(output_path)

    logger.info(
        "starting_qa_generation_from_added_documents",
        delta_report_path=str(delta_report_path),
        output_path=str(output_path),
        testset_size=settings.testset_size,
    )

    # Step 0: Set up environment variables for LLM/embeddings
    logger.info("setting_up_environment")
    settings.setup_environment()

    # Step 1: Load delta report
    logger.info("loading_delta_report", path=str(delta_report_path))
    delta_report = read_delta_report(delta_report_path)
    logger.info(
        "delta_report_loaded",
        total_added=len(delta_report.added),
        old_version=delta_report.old_version,
        new_version=delta_report.new_version,
    )

    if not delta_report.added:
        raise ValueError(f"No added documents found in delta report. " f"Modified: {len(delta_report.modified)}, " f"Renamed: {len(delta_report.renamed_candidates)}")

    # Step 2: Extract added documents (parse HTML) with optional limit
    logger.info("extracting_added_documents", max_documents=num_documents)
    generator_config = settings.to_generator_config()
    stats = AddedDocumentStats()
    extracted_docs = extract_added_documents(
        delta_report,
        generator_config.filtering,
        stats,
        max_documents=num_documents,
    )

    logger.info(
        "added_documents_extracted",
        extracted=len(extracted_docs),
        filtered_invalid_html=stats.filtered_invalid_html,
    )

    if not extracted_docs:
        raise ValueError(f"No added documents could be extracted. " f"Total added: {len(delta_report.added)}, " f"Filtered invalid HTML: {stats.filtered_invalid_html}")

    # Step 3: Convert sections to QASourceDocument with optional limit
    logger.info("converting_sections_to_source_documents")
    source_documents = convert_added_documents(
        extracted_docs,
        delta_report,
        generator_config.filtering,
        stats,
        max_documents=num_documents,
    )

    logger.info(
        "source_documents_created",
        converted_sources=stats.converted_sources,
        total_sections_extracted=stats.total_sections_extracted,
        filtered_by_length=stats.filtered_by_length,
        conversion_rate=f"{stats.conversion_rate:.1f}%",
    )

    if not source_documents:
        raise ValueError(
            f"No source documents created from added documents. "
            f"Total sections extracted: {stats.total_sections_extracted}, "
            f"Filtered by length: {stats.filtered_by_length}. "
            f"Try adjusting min_text_length/max_text_length settings."
        )

    # Count unique topics for stratification decision
    unique_topics = set(doc.topic_slug for doc in source_documents if doc.topic_slug)
    num_topics = len(unique_topics)

    logger.info(
        "source_documents_ready",
        num_documents=len(source_documents),
        num_topics=num_topics,
        total_chars=sum(doc.char_count for doc in source_documents),
    )

    # Step 4: Generate QA pairs with stratified sampling
    logger.info("initializing_ragas_generator")
    generator = RAGASQAGenerator(settings)

    if num_topics > 1:
        logger.info(
            "using_stratified_generation",
            num_topics=num_topics,
            testset_size=generator_config.testset_size,
        )
        qa_pairs = _generate_stratified_by_topic(
            source_documents,
            generator,
            generator_config,
            generator_config.testset_size,
        )
    else:
        logger.info(
            "using_single_pass_generation",
            num_topics=num_topics,
            testset_size=generator_config.testset_size,
        )
        qa_pairs = generator.generate(source_documents, generator_config)

    logger.info(
        "qa_pairs_generated",
        num_pairs=len(qa_pairs),
        avg_question_length=(sum(p.question_length for p in qa_pairs) / len(qa_pairs) if qa_pairs else 0),
    )

    # Step 5: Write output
    logger.info("writing_qa_pairs", format=output_format, path=str(output_path))
    write_qa_pairs(
        qa_pairs,
        output_path,
        output_format=output_format,
        allow_overwrite=allow_overwrite,
    )

    logger.info(
        "qa_generation_from_added_documents_complete",
        num_pairs=len(qa_pairs),
        output_path=str(output_path),
    )

    return qa_pairs


def generate_qa_from_both_sources(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-statements
    delta_report_path: str | Path,
    semantic_diff_report_path: str | Path,
    output_path: str | Path,
    settings: QAGenerationSettings,
    output_format: str = "json",
    allow_overwrite: bool = False,
    num_documents: int | None = None,
) -> list[QAPair]:
    """Generate QA pairs from both modified and added documents.

    This unified entry point processes:
    - Modified/renamed documents from semantic_diff_report.json
    - Added documents from delta_report.json

    The two streams are merged before QA generation.

    Args:
        delta_report_path: Path to delta_report.json file
        semantic_diff_report_path: Path to semantic_diff_report.json file
        output_path: Path to write QA pairs (JSON or YAML)
        settings: QA generation settings
        output_format: Output format ("json" or "yaml")
        allow_overwrite: Allow overwriting existing output file
        num_documents: Limit total number of source documents (None = all)

    Returns:
        List of generated QAPair objects

    Raises:
        FileNotFoundError: If either report file not found
        ValueError: If no source documents after filtering
        QAGenerationError: If generation fails
        QAWriteError: If writing output fails
    """
    delta_report_path = Path(delta_report_path)
    semantic_diff_report_path = Path(semantic_diff_report_path)
    output_path = Path(output_path)

    logger.info(
        "starting_unified_qa_generation",
        delta_report_path=str(delta_report_path),
        semantic_diff_report_path=str(semantic_diff_report_path),
        output_path=str(output_path),
        testset_size=settings.testset_size,
    )

    # Step 0: Set up environment variables
    logger.info("setting_up_environment")
    settings.setup_environment()

    generator_config = settings.to_generator_config()

    # Step 1: Process modified documents from semantic diff report
    logger.info("loading_semantic_diff_report", path=str(semantic_diff_report_path))
    diff_report = read_diff_report(semantic_diff_report_path)
    logger.info(
        "semantic_diff_report_loaded",
        num_results=len(diff_report.results),
        old_version=diff_report.old_version,
        new_version=diff_report.new_version,
    )

    logger.info("extracting_snippets_from_modified_documents", max_documents=num_documents)
    modified_sources, snippet_stats = extract_snippets(
        diff_report,
        generator_config.filtering,
        max_documents=num_documents,
    )
    logger.info(
        "modified_snippets_extracted",
        extracted=snippet_stats.extracted_snippets,
        extraction_rate=f"{snippet_stats.extraction_rate:.1f}%",
    )

    # Step 2: Process added documents from delta report
    logger.info("loading_delta_report", path=str(delta_report_path))
    delta_report = read_delta_report(delta_report_path)
    logger.info(
        "delta_report_loaded",
        total_added=len(delta_report.added),
    )

    added_sources = []
    if delta_report.added:
        logger.info("extracting_added_documents", max_documents=num_documents)
        added_stats = AddedDocumentStats()
        extracted_docs = extract_added_documents(
            delta_report,
            generator_config.filtering,
            added_stats,
            max_documents=num_documents,
        )

        logger.info("converting_added_document_sections")
        added_sources = convert_added_documents(
            extracted_docs,
            delta_report,
            generator_config.filtering,
            added_stats,
            max_documents=num_documents,
        )

        logger.info(
            "added_documents_processed",
            converted_sources=added_stats.converted_sources,
            conversion_rate=f"{added_stats.conversion_rate:.1f}%",
        )
    else:
        logger.info("no_added_documents_to_process")

    # Step 3: Merge sources
    all_sources = modified_sources + added_sources
    logger.info(
        "sources_merged",
        modified_sources=len(modified_sources),
        added_sources=len(added_sources),
        total_sources=len(all_sources),
    )

    if not all_sources:
        raise ValueError(f"No source documents after merging. " f"Modified sources: {len(modified_sources)}, " f"Added sources: {len(added_sources)}")

    # Limit documents if requested
    if num_documents is not None:
        if num_documents <= 0:
            raise ValueError(f"num_documents must be positive, got {num_documents}")
        original_count = len(all_sources)
        all_sources = all_sources[:num_documents]
        logger.info(
            "documents_limited",
            original_count=original_count,
            limited_count=len(all_sources),
        )

    # Count unique topics for stratification decision
    unique_topics = set(doc.topic_slug for doc in all_sources if doc.topic_slug)
    num_topics = len(unique_topics)

    logger.info(
        "source_documents_ready",
        num_documents=len(all_sources),
        num_topics=num_topics,
        total_chars=sum(doc.char_count for doc in all_sources),
    )

    # Step 4: Generate QA pairs with stratified sampling
    logger.info("initializing_ragas_generator")
    generator = RAGASQAGenerator(settings)

    if num_topics > 1:
        logger.info(
            "using_stratified_generation",
            num_topics=num_topics,
            testset_size=generator_config.testset_size,
        )
        qa_pairs = _generate_stratified_by_topic(
            all_sources,
            generator,
            generator_config,
            generator_config.testset_size,
        )
    else:
        logger.info(
            "using_single_pass_generation",
            num_topics=num_topics,
            testset_size=generator_config.testset_size,
        )
        qa_pairs = generator.generate(all_sources, generator_config)

    logger.info(
        "qa_pairs_generated",
        num_pairs=len(qa_pairs),
        avg_question_length=(sum(p.question_length for p in qa_pairs) / len(qa_pairs) if qa_pairs else 0),
    )

    # Step 5: Write output
    logger.info("writing_qa_pairs", format=output_format, path=str(output_path))
    write_qa_pairs(
        qa_pairs,
        output_path,
        output_format=output_format,
        allow_overwrite=allow_overwrite,
    )

    logger.info(
        "unified_qa_generation_complete",
        num_pairs=len(qa_pairs),
        output_path=str(output_path),
    )

    return qa_pairs
