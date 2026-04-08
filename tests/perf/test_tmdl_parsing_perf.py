"""Granular TMDL parsing benchmarks — one benchmark per pipeline stage.

Stages covered
--------------
lex          TMDLLexer.tokenize()                          per file / project
parse        lex + AST construction (parse_tmdl)           per file / project
transform    AST → Pydantic models (TMDLTransformer)       tables only
load         TMDLPartsLoader.load()                        full project
write        TMDLPartsWriter.write()                       full project
roundtrip    load + write combined                         full project

All benchmarks operate on in-memory dicts populated by ``conftest.py`` —
no disk I/O occurs during the benchmark runs themselves.  The per-file
parametrized benchmarks reveal which individual TMDL files dominate
parsing time.

Run with:
    pytest tests/perf/test_tmdl_parsing_perf.py -v
    pytest tests/perf/test_tmdl_parsing_perf.py -v --benchmark-sort=mean
"""

from pathlib import Path

import pytest

from pybi.semanticmodel.definition import SemanticModelDefinition
from pybi.serialization.parsers.tmdl.lexer import TMDLLexer
from pybi.serialization.parsers.tmdl.loader import TMDLPartsLoader
from pybi.serialization.parsers.tmdl.parser import parse_tmdl
from pybi.serialization.parsers.tmdl.transformer import TMDLTransformer
from pybi.serialization.parsers.tmdl.writer import TMDLPartsWriter

pytestmark = pytest.mark.skipif(
    not Path("../pbi-samples").exists(),
    reason="pbi-samples repository not available; clone https://github.com/willianmh/pbi-samples",
)

# ---------------------------------------------------------------------------
# LEX — tokenization only
# ---------------------------------------------------------------------------


def test_bench_lex_full_project(benchmark, tmdl_files: dict[str, str]) -> None:
    """Tokenize every TMDL file in the project."""

    def run() -> None:
        for text in tmdl_files.values():
            list(TMDLLexer(text).tokenize())

    benchmark(run)


def test_bench_lex_tables_only(benchmark, table_files: dict[str, str]) -> None:
    """Tokenize only the table TMDL files."""

    def run() -> None:
        for text in table_files.values():
            list(TMDLLexer(text).tokenize())

    benchmark(run)


# ---------------------------------------------------------------------------
# PARSE — lex + AST construction
# ---------------------------------------------------------------------------


def test_bench_parse_full_project(benchmark, tmdl_files: dict[str, str]) -> None:
    """Lex + build AST for every TMDL file in the project."""

    def run() -> None:
        for path, text in tmdl_files.items():
            parse_tmdl(text, path)

    benchmark(run)


def test_bench_parse_tables_only(benchmark, table_files: dict[str, str]) -> None:
    """Lex + build AST for table files only."""

    def run() -> None:
        for path, text in table_files.items():
            parse_tmdl(text, path)

    benchmark(run)


def test_bench_parse_per_file(benchmark, tmdl_file_item: tuple[str, str]) -> None:
    """Per-file lex+parse — reveals which files dominate parse time.

    ``tmdl_file_item`` is parametrized by ``conftest.pytest_generate_tests``
    over all entries in the in-memory ``_ALL_TMDL_FILES`` dict.
    """
    path, text = tmdl_file_item
    benchmark(parse_tmdl, text, path)


# ---------------------------------------------------------------------------
# TRANSFORM — AST → Pydantic models (isolated from parsing)
# ---------------------------------------------------------------------------


def test_bench_transform_tables(benchmark, table_asts: dict[str, list]) -> None:
    """Transform pre-parsed table ASTs to Pydantic Table models.

    Isolates Pydantic model-construction cost from lex/parse cost.
    """
    transformer = TMDLTransformer()

    def run() -> None:
        for nodes in table_asts.values():
            for node in nodes:
                if node.object_type == "table":
                    transformer.transform_table(node)

    benchmark(run)


# ---------------------------------------------------------------------------
# LOAD — full pipeline (lex + parse + transform)
# ---------------------------------------------------------------------------


def test_bench_load_full_project(benchmark, tmdl_files: dict[str, str]) -> None:
    """TMDLPartsLoader.load() — lex + parse + transform for the whole project."""
    benchmark(TMDLPartsLoader(tmdl_files).load)


# ---------------------------------------------------------------------------
# WRITE — serialization
# ---------------------------------------------------------------------------


def test_bench_write_full_project(
    benchmark, parsed_definition: SemanticModelDefinition
) -> None:
    """TMDLPartsWriter.write() — Pydantic models → TMDL text."""
    writer = TMDLPartsWriter()
    benchmark(writer.write, parsed_definition)


# ---------------------------------------------------------------------------
# ROUNDTRIP — load + write combined
# ---------------------------------------------------------------------------


def test_bench_roundtrip(benchmark, tmdl_files: dict[str, str]) -> None:
    """Full parse-then-serialize roundtrip."""

    def run() -> None:
        data = TMDLPartsLoader(tmdl_files).load()
        definition = SemanticModelDefinition(**data)
        TMDLPartsWriter().write(definition)

    benchmark(run)
