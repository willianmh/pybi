"""Integration tests for the TMDL lexer against real sample files."""

import re
from pathlib import Path

import pytest

from pybi.serialization.parsers.tmdl.exceptions import TMDLLexerError
from pybi.serialization.parsers.tmdl.lexer import TMDLLexer, Token, TokenType

# ---------------------------------------------------------------------------
# Paths to sample semantic models (relative to project root)
# ---------------------------------------------------------------------------

_AI = Path(
    "samples/pbir/11.25/ai"
    "/Artificial Intelligence Sample.SemanticModel/definition"
)
_COVID_US = Path(
    "samples/pbir/11.25/covid-19-us"
    "/COVID-19 US Tracking Sample.SemanticModel/definition"
)
_COVID_BAKEOFF = Path(
    "samples/pbir/11.25/covid-bakeoff"
    "/COVID Bakeoff.SemanticModel/definition"
)
_HUMAN_RESOURCES = Path(
    "samples/pbir/11.25/human-resources"
    "/Human Resources Sample PBIX.SemanticModel/definition"
)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lex_file(path: Path) -> list[Token]:
    text = path.read_text(encoding="utf-8")
    return list(TMDLLexer(text, file_path=str(path)).tokenize())


def _consecutive_pairs(toks: list[Token]):
    return zip(toks, toks[1:])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    return Path("samples/pbir/11.25")


@pytest.fixture(scope="session")
def all_tmdl_files(samples_dir: Path) -> list[Path]:
    return sorted(samples_dir.glob("**/*.tmdl"))


# ---------------------------------------------------------------------------
# TestLexerOnAllSamples
#
# Each test is parametrized per file so failures are isolated — a crash in
# one file does not mask results for the remaining 112 files.
# ---------------------------------------------------------------------------


class TestLexerOnAllSamples:
    @pytest.fixture(params=sorted(Path("samples/pbir/11.25").glob("**/*.tmdl")),
                    ids=lambda p: p.name)
    def tmdl_file(self, request) -> Path:
        return request.param

    @pytest.fixture
    def token_list(self, tmdl_file: Path) -> list[Token]:
        """Pre-lexed tokens for a single file. Marks the test xfail if the
        lexer itself raises, so the crash is recorded but does not block the
        suite (the crash is covered by test_no_crash_on_all_samples)."""
        try:
            return _lex_file(tmdl_file)
        except TMDLLexerError as e:
            pytest.xfail(f"Lexer error in {tmdl_file.name}: {e}")

    def test_no_crash_on_all_samples(self, tmdl_file: Path):
        """Smoke test: every .tmdl file must tokenize without error.

        A failure here exposes a real lexer limitation — do NOT silence it.
        Known issue: multi-line double-quoted strings (not backtick blocks)
        cause TMDLLexerError because the lexer processes strings line-by-line.
        """
        _lex_file(tmdl_file)  # must not raise

    def test_eof_always_last_token(self, token_list: list[Token], tmdl_file: Path):
        assert token_list[-1].type == TokenType.EOF, \
            f"EOF not last in {tmdl_file.name}"

    def test_indent_dedent_balance(self, token_list: list[Token], tmdl_file: Path):
        indents = sum(1 for t in token_list if t.type == TokenType.INDENT)
        dedents = sum(1 for t in token_list if t.type == TokenType.DEDENT)
        assert indents == dedents, (
            f"INDENT/DEDENT imbalance in {tmdl_file.name}: "
            f"{indents} INDENT vs {dedents} DEDENT"
        )

    def test_no_consecutive_newlines(self, token_list: list[Token], tmdl_file: Path):
        for a, b in _consecutive_pairs(token_list):
            assert not (
                a.type == TokenType.NEWLINE and b.type == TokenType.NEWLINE
            ), f"Consecutive NEWLINEs in {tmdl_file.name} at line {b.line}"

    def test_no_token_has_line_zero(self, token_list: list[Token], tmdl_file: Path):
        for t in token_list:
            assert t.line >= 1, f"Token with line=0 in {tmdl_file.name}: {t!r}"


# ---------------------------------------------------------------------------
# TestSpecificSampleFiles
# ---------------------------------------------------------------------------


class TestSpecificSampleFiles:
    def test_database_tmdl_structure(self):
        """Exact token sequence for a minimal database.tmdl file."""
        toks = _lex_file(_AI / "database.tmdl")
        tt = [t.type for t in toks]
        expected = [
            TokenType.KEYWORD,    # database
            TokenType.NEWLINE,
            TokenType.INDENT,
            TokenType.IDENTIFIER, # compatibilityLevel
            TokenType.COLON,
            TokenType.STRING,     # 1567
            TokenType.NEWLINE,
            TokenType.DEDENT,
            TokenType.EOF,
        ]
        assert tt == expected

    def test_database_tmdl_keyword_value(self):
        toks = _lex_file(_AI / "database.tmdl")
        kw = next(t for t in toks if t.type == TokenType.KEYWORD)
        assert kw.value == "database"

    def test_relationships_uuid_identifiers(self):
        toks = _lex_file(_AI / "relationships.tmdl")
        identifiers = [t for t in toks if t.type == TokenType.IDENTIFIER]
        uuids = [t for t in identifiers if _UUID_RE.match(t.value)]
        assert len(uuids) > 0, "Expected at least one UUID identifier"

    def test_relationships_inactive_have_string_false(self):
        """isActive: false is tokenized as COLON → STRING('false'), not BOOLEAN.

        This is correct lexer behavior: colon-value lines capture the entire
        remaining text as a single STRING token, including 'true'/'false'.
        """
        toks = _lex_file(_AI / "relationships.tmdl")
        # Find COLON tokens followed by a STRING with value "false"
        for a, b in _consecutive_pairs(toks):
            if a.type == TokenType.COLON and b.type == TokenType.STRING and b.value == "false":
                return
        pytest.fail("Expected COLON → STRING('false') for isActive: false")

    def test_relationships_column_refs_are_strings(self):
        """Column references after 'fromColumn:' are captured as a single STRING.

        The lexer does not tokenize quoted names inside colon values — the
        entire right-hand side is a STRING.  'Account Owner' embedded in
        'Accounts.Account Owner' is part of the STRING value.
        """
        toks = _lex_file(_AI / "relationships.tmdl")
        strings = [t for t in toks if t.type == TokenType.STRING]
        # "Accounts.'Account Owner'" contains a quote but is one STRING token
        assert any("'" in t.value for t in strings), (
            "Expected at least one STRING containing a single-quote "
            "(column reference with quoted component)"
        )

    def test_accounts_annotation_json_value(self):
        toks = _lex_file(_AI / "tables" / "Accounts.tmdl")
        strings = [t for t in toks if t.type == TokenType.STRING]
        assert any("{" in t.value for t in strings), (
            "Expected at least one STRING containing '{' (JSON annotation value)"
        )

    def test_covid_measures_backtick_measure(self):
        toks = _lex_file(_COVID_US / "tables" / "COVID measures.tmdl")
        strings = [t for t in toks if t.type == TokenType.STRING]
        assert any("\n" in t.value for t in strings), (
            "Expected at least one multi-line STRING (backtick expression)"
        )

    def test_covid_measures_partition_has_quoted_name(self):
        """The partition 'COVID measures-<uuid>' declaration produces a QUOTED_NAME.

        Quoted names only appear as QUOTED_NAME tokens when they are part of
        object declarations (not inside colon or equals values).
        """
        toks = _lex_file(_COVID_US / "tables" / "COVID measures.tmdl")
        quoted = [t for t in toks if t.type == TokenType.QUOTED_NAME]
        # Partition name 'COVID measures-...' contains a space
        assert any(" " in t.value for t in quoted), (
            "Expected QUOTED_NAME with a space (partition 'COVID measures-...')"
        )

    def test_case_calendar_source_equals_backtick(self):
        """source = ``` block produces KEYWORD(source) → EQUALS → STRING sequence."""
        toks = _lex_file(_AI / "tables" / "Case Calendar.tmdl")
        for a, b, c in zip(toks, toks[1:], toks[2:]):
            if (
                a.type == TokenType.KEYWORD
                and a.value == "source"
                and b.type == TokenType.EQUALS
                and c.type == TokenType.STRING
            ):
                return
        pytest.fail("Expected KEYWORD(source) → EQUALS → STRING sequence")

    def test_covid_bakeoff_multiline_backtick_bug4(self):
        """Bug 4 verification on real data: NEWLINE.line > STRING.line + 5.

        For multi-line backtick expressions, the STRING token carries the
        opening line number and the trailing NEWLINE carries the closing ```
        line number, so the two must differ by at least the number of content
        lines (here > 5).
        """
        toks = _lex_file(
            _COVID_BAKEOFF / "tables" / "Days with restrictions.tmdl"
        )
        # Find the large STRING that is the source = ``` block
        for i, t in enumerate(toks):
            if (
                t.type == TokenType.STRING
                and "\n" in t.value
                and len(t.value) > 200
                and i + 1 < len(toks)
            ):
                nl = toks[i + 1]
                if nl.type == TokenType.NEWLINE:
                    assert nl.line > t.line + 5, (
                        f"Bug 4: NEWLINE.line ({nl.line}) should be > "
                        f"STRING.line ({t.line}) + 5 for multi-line backtick"
                    )
                    return
        pytest.fail("No multi-line STRING > 200 chars found in Days with restrictions.tmdl")

    def test_human_resources_flag_properties_are_identifiers(self):
        """legacyRedirects and returnErrorValuesAsNull are IDENTIFIER, not KEYWORD."""
        toks = _lex_file(_HUMAN_RESOURCES / "model.tmdl")
        idents = {t.value for t in toks if t.type == TokenType.IDENTIFIER}
        assert "legacyRedirects" in idents
        assert "returnErrorValuesAsNull" in idents

    def test_human_resources_ref_statements(self):
        toks = _lex_file(_HUMAN_RESOURCES / "model.tmdl")
        ref_tokens = [t for t in toks if t.type == TokenType.KEYWORD and t.value == "ref"]
        assert len(ref_tokens) >= 10, (
            f"Expected >= 10 'ref' keywords, got {len(ref_tokens)}"
        )

    def test_human_resources_cultureinfo_ref(self):
        """Sequence: KEYWORD(ref) → KEYWORD(cultureInfo) → IDENTIFIER(en-US)."""
        toks = _lex_file(_HUMAN_RESOURCES / "model.tmdl")
        for a, b, c in zip(toks, toks[1:], toks[2:]):
            if (
                a.type == TokenType.KEYWORD
                and a.value == "ref"
                and b.type == TokenType.KEYWORD
                and b.value == "cultureInfo"
                and c.type == TokenType.IDENTIFIER
                and c.value == "en-US"
            ):
                return
        pytest.fail("Expected ref → cultureInfo → en-US sequence")


# ---------------------------------------------------------------------------
# TestEdgeCasesFromSamples
#
# Cross-cutting invariants scanned across all sample files.  Files that fail
# to lex are skipped (their crash is covered by test_no_crash_on_all_samples).
# ---------------------------------------------------------------------------


class TestEdgeCasesFromSamples:
    def test_m_quoted_identifiers_intact(self, all_tmdl_files):
        for path in all_tmdl_files:
            try:
                toks = _lex_file(path)
            except TMDLLexerError:
                continue  # crash is tested separately
            for t in toks:
                if t.type == TokenType.STRING and t.value.startswith('#"'):
                    assert t.value.endswith('"'), (
                        f"M-quoted identifier not properly closed in {path.name}: {t.value!r}"
                    )

    def test_description_values_are_stripped(self, all_tmdl_files):
        """DESCRIPTION values must have no leading/trailing whitespace.

        Note: empty values ('') are valid — '/// ' (slash + space) strips to ''
        and is used as a blank separator line in real TMDL files.
        """
        for path in all_tmdl_files:
            try:
                toks = _lex_file(path)
            except TMDLLexerError:
                continue
            for t in toks:
                if t.type == TokenType.DESCRIPTION:
                    assert t.value == t.value.strip(), (
                        f"DESCRIPTION value not stripped in {path.name} "
                        f"at line {t.line}: {t.value!r}"
                    )

    def test_all_boolean_values_lowercase(self, all_tmdl_files):
        for path in all_tmdl_files:
            try:
                toks = _lex_file(path)
            except TMDLLexerError:
                continue
            for t in toks:
                if t.type == TokenType.BOOLEAN:
                    assert t.value in {"true", "false"}, (
                        f"Non-lowercase BOOLEAN {t.value!r} in {path.name}"
                    )

    def test_string_after_colon_no_leading_whitespace(self, all_tmdl_files):
        for path in all_tmdl_files:
            try:
                toks = _lex_file(path)
            except TMDLLexerError:
                continue
            for a, b in _consecutive_pairs(toks):
                if a.type == TokenType.COLON and b.type == TokenType.STRING:
                    assert not b.value.startswith(" "), (
                        f"STRING after COLON has leading whitespace in "
                        f"{path.name} at line {b.line}: {b.value!r}"
                    )

    def test_string_after_equals_no_leading_whitespace(self, all_tmdl_files):
        for path in all_tmdl_files:
            try:
                toks = _lex_file(path)
            except TMDLLexerError:
                continue
            for a, b in _consecutive_pairs(toks):
                if (
                    a.type == TokenType.EQUALS
                    and b.type == TokenType.STRING
                    and not b.value.startswith("```")
                ):
                    assert not b.value.startswith(" "), (
                        f"STRING after EQUALS has leading whitespace in "
                        f"{path.name} at line {b.line}: {b.value!r}"
                    )
