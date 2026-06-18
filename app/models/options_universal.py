from __future__ import annotations

from pydantic import BaseModel, Field


class ConversionOptions(BaseModel):
    """Universal Calibre ebook-convert options.

    All fields are optional. Pass only what you need to override.
    For format-specific flags not listed here, use extra_options.
    """

    # ── Look & Feel ──────────────────────────────────────────────────────────
    base_font_size: float | None = Field(default=None, description="Base font size in pts")
    font_size_mapping: str | None = Field(default=None, description="Comma-separated font size mapping")
    line_height: float | None = Field(default=None, description="Line height in pts (0 = auto)")
    minimum_line_height: float | None = Field(default=None, description="Minimum line height as %")
    margin_top: float | None = Field(default=None, description="Top margin in pts")
    margin_bottom: float | None = Field(default=None, description="Bottom margin in pts")
    margin_left: float | None = Field(default=None, description="Left margin in pts")
    margin_right: float | None = Field(default=None, description="Right margin in pts")
    extra_css: str | None = Field(default=None, description="Extra CSS applied after all other CSS")
    embed_all_fonts: bool | None = Field(default=None, description="Embed every font referenced in the document")
    embed_font_family: str | None = Field(default=None, description="Embed a specific font family")
    subset_embedded_fonts: bool | None = Field(default=None, description="Subset embedded fonts")
    unsmarten_punctuation: bool | None = Field(default=None, description="Convert smart quotes/dashes to ASCII")
    smarten_punctuation: bool | None = Field(default=None, description="Convert plain quotes/dashes to typographic")
    remove_paragraph_spacing: bool | None = Field(default=None, description="Remove spacing between paragraphs")
    remove_paragraph_spacing_indent_size: float | None = Field(default=None, description="Indent for paragraphs when spacing removed")
    insert_blank_line: bool | None = Field(default=None, description="Insert blank line between paragraphs")
    insert_blank_line_size: float | None = Field(default=None, description="Size of inserted blank line in em")
    input_encoding: str | None = Field(default=None, description="Input character encoding override")
    filter_css: str | None = Field(default=None, description="Comma-separated CSS properties to remove")
    transform_html_rules: str | None = Field(default=None, description="JSON rules for HTML tag transforms")

    # ── Heuristics ───────────────────────────────────────────────────────────
    enable_heuristics: bool | None = Field(default=None, description="Enable heuristic processing")
    dehyphenate: bool | None = Field(default=None, description="Remove soft hyphens")
    markup_chapter_headings: bool | None = Field(default=None, description="Auto-markup chapter headings")
    renumber_headings: bool | None = Field(default=None, description="Renumber H1/H2 tags")
    delete_blank_paragraphs: bool | None = Field(default=None, description="Delete blank paragraphs")
    format_scene_breaks: bool | None = Field(default=None, description="Replace asterism scene-break markers")
    replace_scene_breaks: str | None = Field(default=None, description="Replacement string for scene breaks")
    fix_indents: bool | None = Field(default=None, description="Convert nbsp-based indents to CSS indents")
    italicize_common_cases: bool | None = Field(default=None, description="Italicize common phrases")
    html_unwrap_factor: float | None = Field(default=None, description="Sentence-end unwrap factor (0.0–1.0)")
    unwrap_lines: bool | None = Field(default=None, description="Unwrap lines using punctuation heuristics")

    # ── Search & Replace ─────────────────────────────────────────────────────
    sr1_search: str | None = Field(default=None, description="Search regex #1")
    sr1_replace: str | None = Field(default=None, description="Replacement string for search #1")
    sr2_search: str | None = Field(default=None, description="Search regex #2")
    sr2_replace: str | None = Field(default=None, description="Replacement string for search #2")
    sr3_search: str | None = Field(default=None, description="Search regex #3")
    sr3_replace: str | None = Field(default=None, description="Replacement string for search #3")

    # ── Structure Detection ───────────────────────────────────────────────────
    chapter: str | None = Field(default=None, description="XPath expression for chapter detection")
    chapter_mark: str | None = Field(default=None, description="How to mark chapters: pagebreak/rule/both/none")
    prefer_metadata_cover: bool | None = Field(default=None, description="Use metadata cover over auto-detected")
    remove_first_image: bool | None = Field(default=None, description="Remove first image (if it duplicates cover)")
    insert_metadata: bool | None = Field(default=None, description="Insert metadata page at start of book")
    page_breaks_before: str | None = Field(default=None, description="XPath for page-break-before elements")
    remove_fake_margins: bool | None = Field(default=None, description="Remove fake margin-mimic styles")
    start_reading_at: str | None = Field(default=None, description="XPath for reading start position")

    # ── Table of Contents ─────────────────────────────────────────────────────
    level1_toc: str | None = Field(default=None, description="XPath for level-1 TOC entries")
    level2_toc: str | None = Field(default=None, description="XPath for level-2 TOC entries")
    level3_toc: str | None = Field(default=None, description="XPath for level-3 TOC entries")
    toc_title: str | None = Field(default=None, description="Title for auto-generated TOC")
    use_auto_toc: bool | None = Field(default=None, description="Force auto-generated TOC even if book has one")
    no_chapters_in_toc: bool | None = Field(default=None, description="Don't add auto-detected chapters to TOC")
    max_toc_links: int | None = Field(default=None, description="Max links to include in TOC (0 = disable)")
    toc_threshold: int | None = Field(default=None, description="Min chapters before auto-TOC is generated")
    duplicate_links_in_toc: bool | None = Field(default=None, description="Allow duplicate links in TOC")
    toc_filter: str | None = Field(default=None, description="Regex to remove TOC entries that match")
    flatten_toc: bool | None = Field(default=None, description="Flatten multi-level TOC to single level")

    # ── Metadata ──────────────────────────────────────────────────────────────
    title: str | None = Field(default=None, description="Book title override")
    authors: str | None = Field(default=None, description="Authors, comma-separated")
    publisher: str | None = Field(default=None, description="Publisher name")
    book_producer: str | None = Field(default=None, description="Book producer")
    isbn: str | None = Field(default=None, description="ISBN")
    tags: str | None = Field(default=None, description="Comma-separated tags/categories")
    series: str | None = Field(default=None, description="Series name")
    series_index: float | None = Field(default=None, description="Book position in series")
    rating: int | None = Field(default=None, ge=1, le=10, description="Rating 1–10")
    language: str | None = Field(default=None, description="Language code (e.g. en, fr)")
    pubdate: str | None = Field(default=None, description="Publication date (ISO 8601)")
    comments: str | None = Field(default=None, description="Book description / comments")

    # ── Input/Output Profiles ─────────────────────────────────────────────────
    input_profile: str | None = Field(default=None, description="Input device profile (e.g. default, kindle)")
    output_profile: str | None = Field(default=None, description="Output device profile (e.g. default, kindle, kobo)")

    # ── Debug ─────────────────────────────────────────────────────────────────
    verbose: int | None = Field(default=None, ge=0, le=2, description="Verbosity: 0=normal, 1=verbose, 2=debug")

    # ── Passthrough for format-specific / advanced flags ──────────────────────
    extra_options: dict[str, str | None] = Field(
        default_factory=dict,
        description=(
            "Format-specific or advanced flags not in the universal list. "
            "Keys are CLI flag names (with or without '--', hyphens or underscores). "
            "Use null value for boolean flags. Example: {'epub-version': '3', 'no-default-epub-cover': null}"
        ),
    )
