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
from qa_generation.models import AddedDocumentStats, QAPair, QASourceDocument
from qa_generation.output import write_qa_pairs

logger = structlog.get_logger(__name__)


def generate_qa_from_report(
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

    # Step 2: Extract snippets
    logger.info("extracting_snippets")
    generator_config = settings.to_generator_config()
    snippets, stats = extract_snippets(report, generator_config.filtering)

    logger.info(
        "snippets_extracted",
        extracted=stats.extracted_snippets,
        total_filtered=stats.total_filtered,
        extraction_rate=f"{stats.extraction_rate:.1f}%",
    )

    if not snippets:
        raise ValueError(
            f"No snippets extracted from report. "
            f"Total changes: {stats.total_changes}, "
            f"Filtered: {stats.total_filtered}. "
            f"Try adjusting filter settings."
        )

    # Step 3: Snippets are already QASourceDocument objects
    source_documents = snippets

    # Limit documents if requested
    if num_documents is not None:
        if num_documents <= 0:
            raise ValueError(f"num_documents must be positive, got {num_documents}")
        original_count = len(source_documents)
        source_documents = source_documents[:num_documents]
        logger.info(
            "documents_limited",
            original_count=original_count,
            limited_count=len(source_documents),
        )

    logger.info(
        "source_documents_ready",
        num_documents=len(source_documents),
        total_chars=sum(doc.char_count for doc in source_documents),
    )

    # Step 4: Generate QA pairs
    logger.info("initializing_ragas_generator")
    generator = RAGASQAGenerator(settings)

    logger.info("generating_qa_pairs", testset_size=generator_config.testset_size)
    qa_pairs = generator.generate(source_documents, generator_config)


    logger.info(
        "qa_pairs_generated",
        num_pairs=len(qa_pairs),
        avg_question_length=sum(p.question_length for p in qa_pairs) / len(qa_pairs)
        if qa_pairs
        else 0,
    )

    # Step 5: Write output
    logger.info("writing_qa_pairs", format=output_format, path=str(output_path))
    write_qa_pairs(
        qa_pairs,
        output_path,
        format=output_format,
        allow_overwrite=allow_overwrite,
    )

    logger.info(
        "qa_generation_pipeline_complete",
        num_pairs=len(qa_pairs),
        output_path=str(output_path),
    )

    return qa_pairs


def generate_qa_from_delta_report(
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
        raise ValueError(
            f"No added documents found in delta report. "
            f"Modified: {len(delta_report.modified)}, "
            f"Renamed: {len(delta_report.renamed_candidates)}"
        )

    # Step 2: Extract added documents (parse HTML)
    logger.info("extracting_added_documents")
    generator_config = settings.to_generator_config()
    stats = AddedDocumentStats()
    extracted_docs = extract_added_documents(delta_report, generator_config.filtering, stats)

    logger.info(
        "added_documents_extracted",
        extracted=len(extracted_docs),
        filtered_invalid_html=stats.filtered_invalid_html,
    )

    if not extracted_docs:
        raise ValueError(
            f"No added documents could be extracted. "
            f"Total added: {len(delta_report.added)}, "
            f"Filtered invalid HTML: {stats.filtered_invalid_html}"
        )

    # Step 3: Convert sections to QASourceDocument
    logger.info("converting_sections_to_source_documents")
    source_documents = convert_added_documents(extracted_docs, delta_report, generator_config.filtering, stats)

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

    # Limit documents if requested
    if num_documents is not None:
        if num_documents <= 0:
            raise ValueError(f"num_documents must be positive, got {num_documents}")
        original_count = len(source_documents)
        source_documents = source_documents[:num_documents]
        logger.info(
            "documents_limited",
            original_count=original_count,
            limited_count=len(source_documents),
        )

    logger.info(
        "source_documents_ready",
        num_documents=len(source_documents),
        total_chars=sum(doc.char_count for doc in source_documents),
    )

    # Step 4: Generate QA pairs
    logger.info("initializing_ragas_generator")
    generator = RAGASQAGenerator(settings)

    logger.info("generating_qa_pairs", testset_size=generator_config.testset_size)
    qa_pairs = generator.generate(source_documents, generator_config)

    logger.info(
        "qa_pairs_generated",
        num_pairs=len(qa_pairs),
        avg_question_length=sum(p.question_length for p in qa_pairs) / len(qa_pairs)
        if qa_pairs
        else 0,
    )

    # Step 5: Write output
    logger.info("writing_qa_pairs", format=output_format, path=str(output_path))
    write_qa_pairs(
        qa_pairs,
        output_path,
        format=output_format,
        allow_overwrite=allow_overwrite,
    )

    logger.info(
        "qa_generation_from_added_documents_complete",
        num_pairs=len(qa_pairs),
        output_path=str(output_path),
    )

    return qa_pairs


def generate_qa_from_both_sources(
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

    logger.info("extracting_snippets_from_modified_documents")
    modified_sources, snippet_stats = extract_snippets(diff_report, generator_config.filtering)
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
        logger.info("extracting_added_documents")
        added_stats = AddedDocumentStats()
        extracted_docs = extract_added_documents(delta_report, generator_config.filtering, added_stats)

        logger.info("converting_added_document_sections")
        added_sources = convert_added_documents(extracted_docs, delta_report, generator_config.filtering, added_stats)

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
        raise ValueError(
            f"No source documents after merging. "
            f"Modified sources: {len(modified_sources)}, "
            f"Added sources: {len(added_sources)}"
        )

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

    logger.info(
        "source_documents_ready",
        num_documents=len(all_sources),
        total_chars=sum(doc.char_count for doc in all_sources),
    )

    # Step 4: Generate QA pairs
    logger.info("initializing_ragas_generator")
    generator = RAGASQAGenerator(settings)

    logger.info("generating_qa_pairs", testset_size=generator_config.testset_size)
    qa_pairs = generator.generate(all_sources, generator_config)

    logger.info(
        "qa_pairs_generated",
        num_pairs=len(qa_pairs),
        avg_question_length=sum(p.question_length for p in qa_pairs) / len(qa_pairs)
        if qa_pairs
        else 0,
    )

    # Step 5: Write output
    logger.info("writing_qa_pairs", format=output_format, path=str(output_path))
    write_qa_pairs(
        qa_pairs,
        output_path,
        format=output_format,
        allow_overwrite=allow_overwrite,
    )

    logger.info(
        "unified_qa_generation_complete",
        num_pairs=len(qa_pairs),
        output_path=str(output_path),
    )

    return qa_pairs
