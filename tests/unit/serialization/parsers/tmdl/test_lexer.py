"""Unit tests for the TMDL lexer."""

import pytest

from pybi.serialization.parsers.tmdl.exceptions import TMDLLexerError
from pybi.serialization.parsers.tmdl.grammar import KEYWORDS
from pybi.serialization.parsers.tmdl.lexer import TMDLLexer, Token, TokenType


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def tokens(text: str, file_path: str | None = None) -> list[Token]:
    return list(TMDLLexer(text, file_path=file_path).tokenize())


def types(text: str) -> list[TokenType]:
    return [t.type for t in tokens(text)]


def values(text: str) -> list[str]:
    return [t.value for t in tokens(text)]


def first_of(toks: list[Token], tt: TokenType) -> Token:
    return next(t for t in toks if t.type == tt)


def all_of(toks: list[Token], tt: TokenType) -> list[Token]:
    return [t for t in toks if t.type == tt]


# ---------------------------------------------------------------------------
# TestTokenDataclass
# ---------------------------------------------------------------------------


class TestTokenDataclass:
    def test_default_indent_level_is_zero(self):
        t = Token(TokenType.KEYWORD, "table", 1, 1)
        assert t.indent_level == 0

    def test_repr_contains_type_name_and_value(self):
        t = Token(TokenType.KEYWORD, "table", 1, 1)
        r = repr(t)
        assert "KEYWORD" in r
        assert "table" in r

    def test_all_fields_set_correctly(self):
        t = Token(TokenType.IDENTIFIER, "Sales", 3, 5, 2)
        assert t.type == TokenType.IDENTIFIER
        assert t.value == "Sales"
        assert t.line == 3
        assert t.column == 5
        assert t.indent_level == 2


# ---------------------------------------------------------------------------
# TestCRLFNormalization
# ---------------------------------------------------------------------------


class TestCRLFNormalization:
    def test_crlf_is_normalized_to_lf(self):
        toks = tokens("table Foo\r\n\tdataType: string")
        tt = types("table Foo\r\n\tdataType: string")
        assert TokenType.KEYWORD in tt
        assert TokenType.IDENTIFIER in tt

    def test_cr_only_is_normalized(self):
        toks = tokens("table Foo\r\tdataType: string")
        tt = [t.type for t in toks]
        assert TokenType.KEYWORD in tt
        assert TokenType.IDENTIFIER in tt


# ---------------------------------------------------------------------------
# TestEmptyInput
# ---------------------------------------------------------------------------


class TestEmptyInput:
    def test_empty_string_yields_only_eof(self):
        assert types("") == [TokenType.EOF]

    def test_whitespace_only_yields_only_eof(self):
        assert types("   \n\t\n  ") == [TokenType.EOF]

    def test_blank_lines_between_content_are_skipped(self):
        text = "table Foo\n\n\ntable Bar"
        tt = types(text)
        newline_count = tt.count(TokenType.NEWLINE)
        # Two tables each emit one NEWLINE; blank lines produce none
        assert newline_count == 2


# ---------------------------------------------------------------------------
# TestCommentSkipping
# ---------------------------------------------------------------------------


class TestCommentSkipping:
    def test_double_slash_line_is_skipped(self):
        assert types("// this is a comment") == [TokenType.EOF]

    def test_triple_slash_description_is_not_skipped(self):
        tt = types("/// description text")
        assert TokenType.DESCRIPTION in tt

    def test_description_strips_leading_whitespace(self):
        toks = tokens("///   trimmed")
        desc = first_of(toks, TokenType.DESCRIPTION)
        assert desc.value == "trimmed"

    def test_comment_after_indent_is_skipped(self):
        # Bug 7 regression: tab-indented comment inside an indent block
        text = "table Foo\n\t// indented comment\n\tisHidden"
        tt = types(text)
        assert TokenType.DESCRIPTION not in tt
        assert tt.count(TokenType.NEWLINE) == 2  # table Foo + isHidden

    def test_space_prefixed_comment_is_skipped(self):
        # Bug 7 regression: space-prefixed comment (M expression continuation)
        text = "table Foo\n    // space-prefixed comment"
        tt = types(text)
        assert TokenType.DESCRIPTION not in tt

    def test_four_slashes_is_treated_as_description(self):
        # The lexer checks for '///' prefix; '////' starts with '///' so it is
        # emitted as DESCRIPTION with value '/' (the fourth slash).
        toks = tokens("////")
        desc = first_of(toks, TokenType.DESCRIPTION)
        assert desc.value == "/"

    def test_empty_description(self):
        # '///' with nothing after produces DESCRIPTION with empty value
        toks = tokens("///")
        desc = first_of(toks, TokenType.DESCRIPTION)
        assert desc.value == ""

    def test_description_with_only_whitespace(self):
        # '///   ' (slash + spaces) strips to empty string
        toks = tokens("///   ")
        desc = first_of(toks, TokenType.DESCRIPTION)
        assert desc.value == ""


# ---------------------------------------------------------------------------
# TestIsCommentLine
# ---------------------------------------------------------------------------


class TestIsCommentLine:
    """Direct tests for the _is_comment_line static method."""

    def test_double_slash_is_comment(self):
        assert TMDLLexer._is_comment_line("// comment") is True

    def test_triple_slash_is_not_comment(self):
        assert TMDLLexer._is_comment_line("/// description") is False

    def test_space_prefixed_double_slash_is_comment(self):
        assert TMDLLexer._is_comment_line("    // indented comment") is True

    def test_space_prefixed_triple_slash_is_not_comment(self):
        assert TMDLLexer._is_comment_line("    /// indented description") is False

    def test_non_comment_content(self):
        assert TMDLLexer._is_comment_line("table Foo") is False

    def test_slash_alone_is_not_comment(self):
        assert TMDLLexer._is_comment_line("/") is False

    def test_bare_double_slash(self):
        assert TMDLLexer._is_comment_line("//") is True


# ---------------------------------------------------------------------------
# TestIndentation
# ---------------------------------------------------------------------------


class TestIndentation:
    def test_indent_emitted_on_deeper_line(self):
        text = "table Foo\n\tisHidden"
        tt = types(text)
        assert tt.count(TokenType.INDENT) == 1

    def test_dedent_emitted_on_return_to_root(self):
        text = "table Foo\n\tisHidden\ntable Bar"
        tt = types(text)
        assert tt.count(TokenType.DEDENT) == 1

    def test_indent_level_field_on_tokens(self):
        text = "table Foo\n\tisHidden"
        toks = tokens(text)
        # "Foo" is at indent_level=0; "isHidden" is the nested one at level=1
        nested = next(
            t for t in toks if t.type == TokenType.IDENTIFIER and t.value == "isHidden"
        )
        assert nested.indent_level == 1

    def test_multiple_dedents_emitted_correctly(self):
        text = "table Foo\n\tcolumn Bar\n\t\tdataType: string\ntable Baz"
        tt = types(text)
        assert tt.count(TokenType.INDENT) == tt.count(TokenType.DEDENT)
        assert tt.count(TokenType.INDENT) == 2

    def test_no_indent_on_same_level_lines(self):
        text = "table Foo\ntable Bar"
        tt = types(text)
        assert TokenType.INDENT not in tt
        assert TokenType.DEDENT not in tt

    def test_trailing_dedents_before_eof(self):
        text = "table Foo\n\tisHidden"
        tt = types(text)
        # Open indent block must be closed before EOF
        assert tt.count(TokenType.DEDENT) == 1
        assert tt[-1] == TokenType.EOF

    def test_flexible_intermediate_indent_level(self):
        # Exercises the "INDENT to intermediate" branch.
        # Dedent to a level not previously seen forces a re-indent.
        text = "table Foo\n\t\t\tdeep\n\tintermediate\nroot"
        tt = types(text)
        # Should not crash; INDENT/DEDENT counts are balanced
        assert tt.count(TokenType.INDENT) == tt.count(TokenType.DEDENT)

    def test_space_indentation_is_not_structural(self):
        # Spaces are not counted as indentation — only tabs are.
        # A line with leading spaces has indent_level=0.
        text = "table Foo\n    spaceIndented"
        toks = tokens(text)
        space_tok = next(
            t
            for t in toks
            if t.type == TokenType.IDENTIFIER and t.value == "spaceIndented"
        )
        assert space_tok.indent_level == 0


# ---------------------------------------------------------------------------
# TestKeywordsAndIdentifiers
# ---------------------------------------------------------------------------


class TestKeywordsAndIdentifiers:
    @pytest.mark.parametrize("kw", sorted(KEYWORDS))
    def test_keyword_recognized(self, kw):
        toks = tokens(kw)
        assert toks[0].type == TokenType.KEYWORD
        assert toks[0].value == kw

    def test_identifier_not_in_keywords(self):
        toks = tokens("myIdentifier")
        assert toks[0].type == TokenType.IDENTIFIER
        assert toks[0].value == "myIdentifier"

    def test_underscore_leading_identifier(self):
        toks = tokens("_private")
        assert toks[0].type == TokenType.IDENTIFIER

    def test_camelcase_identifier(self):
        toks = tokens("camelCaseIdent")
        assert toks[0].type == TokenType.IDENTIFIER

    def test_identifier_with_dot(self):
        # '.' is in IDENTIFIER_CONTINUATION_CHARS
        toks = tokens("Table.Column")
        assert toks[0].type == TokenType.IDENTIFIER
        assert toks[0].value == "Table.Column"

    def test_identifier_followed_by_colon_stops_at_colon(self):
        tt = types("dataType: string")
        assert tt == [
            TokenType.IDENTIFIER,
            TokenType.COLON,
            TokenType.STRING,
            TokenType.NEWLINE,
            TokenType.EOF,
        ]


# ---------------------------------------------------------------------------
# TestBooleans
# ---------------------------------------------------------------------------


class TestBooleans:
    def test_true_lowercase(self):
        toks = tokens("true")
        assert toks[0].type == TokenType.BOOLEAN
        assert toks[0].value == "true"

    def test_false_lowercase(self):
        toks = tokens("false")
        assert toks[0].type == TokenType.BOOLEAN
        assert toks[0].value == "false"

    def test_true_uppercase(self):
        toks = tokens("True")
        assert toks[0].type == TokenType.BOOLEAN
        assert toks[0].value == "true"

    def test_false_mixed_case(self):
        toks = tokens("False")
        assert toks[0].type == TokenType.BOOLEAN
        assert toks[0].value == "false"

    def test_truthy_word_that_is_not_boolean(self):
        toks = tokens("truthy")
        assert toks[0].type == TokenType.IDENTIFIER


# ---------------------------------------------------------------------------
# TestColonBehavior
# ---------------------------------------------------------------------------


class TestColonBehavior:
    def test_colon_followed_by_string_value(self):
        tt = types("culture: en-US")
        assert tt == [
            TokenType.IDENTIFIER,
            TokenType.COLON,
            TokenType.STRING,
            TokenType.NEWLINE,
            TokenType.EOF,
        ]

    def test_colon_with_empty_value(self):
        tt = types("description:")
        assert TokenType.STRING not in tt

    def test_colon_value_is_rest_of_line(self):
        # Everything after ':' including '=' is captured as a single STRING
        toks = tokens("desc: mode = m_query")
        s = first_of(toks, TokenType.STRING)
        assert "=" in s.value

    def test_colon_strips_trailing_whitespace_from_value(self):
        toks = tokens("culture: en-US   ")
        s = first_of(toks, TokenType.STRING)
        assert not s.value.endswith(" ")

    def test_colon_absorbs_boolean_as_string(self):
        # "isActive: false" produces STRING("false"), not BOOLEAN.
        # This is the intended rest-of-line capture behaviour; the parser
        # handles type interpretation.
        toks = tokens("isActive: false")
        s = first_of(toks, TokenType.STRING)
        assert s.value == "false"
        assert TokenType.BOOLEAN not in [t.type for t in toks]

    def test_colon_absorbs_number_as_string(self):
        # "compatibilityLevel: 1567" produces STRING("1567"), not NUMBER.
        toks = tokens("compatibilityLevel: 1567")
        s = first_of(toks, TokenType.STRING)
        assert s.value == "1567"
        assert TokenType.NUMBER not in [t.type for t in toks]


# ---------------------------------------------------------------------------
# TestEqualsBehavior
# ---------------------------------------------------------------------------


class TestEqualsBehavior:
    def test_equals_followed_by_string_value(self):
        tt = types("measure Total = SUM(Sales[Amount])")
        assert TokenType.KEYWORD in tt
        assert TokenType.IDENTIFIER in tt
        assert TokenType.EQUALS in tt
        assert TokenType.STRING in tt

    def test_equals_with_empty_value(self):
        tt = types("name =")
        assert TokenType.EQUALS in tt
        assert TokenType.STRING not in tt

    def test_equals_strips_trailing_whitespace(self):
        toks = tokens("name = value   ")
        s = first_of(toks, TokenType.STRING)
        assert not s.value.endswith(" ")


# ---------------------------------------------------------------------------
# TestQuotedNames
# ---------------------------------------------------------------------------


class TestQuotedNames:
    def test_simple_quoted_name(self):
        toks = tokens("'Account Name'")
        assert toks[0].type == TokenType.QUOTED_NAME
        assert toks[0].value == "Account Name"

    def test_quoted_name_with_escaped_quote(self):
        toks = tokens("'It''s Special'")
        assert toks[0].type == TokenType.QUOTED_NAME
        assert toks[0].value == "It's Special"

    def test_consecutive_quoted_names(self):
        toks = tokens("'Table A'.'Column B'")
        quoted = all_of(toks, TokenType.QUOTED_NAME)
        assert len(quoted) == 2
        assert quoted[0].value == "Table A"
        assert quoted[1].value == "Column B"

    def test_unterminated_quoted_name_raises(self):
        with pytest.raises(TMDLLexerError) as exc_info:
            tokens("'unclosed")
        assert exc_info.value.line == 1

    def test_unterminated_quoted_name_includes_file_path(self):
        with pytest.raises(TMDLLexerError) as exc_info:
            tokens("'unclosed", file_path="myfile.tmdl")
        assert exc_info.value.file_path == "myfile.tmdl"

    def test_empty_quoted_name_is_valid(self):
        # '' (two quotes) produces a QUOTED_NAME with an empty value
        toks = tokens("''")
        assert toks[0].type == TokenType.QUOTED_NAME
        assert toks[0].value == ""


# ---------------------------------------------------------------------------
# TestStringLiterals
# ---------------------------------------------------------------------------


class TestStringLiterals:
    def test_double_quoted_string_preserves_quotes(self):
        toks = tokens('"Hello"')
        s = first_of(toks, TokenType.STRING)
        assert s.value == '"Hello"'

    def test_double_quoted_string_with_escaped_quote(self):
        toks = tokens('"say ""hello"""')
        s = first_of(toks, TokenType.STRING)
        assert s.value == '"say ""hello"""'

    def test_unterminated_string_literal_raises(self):
        with pytest.raises(TMDLLexerError):
            tokens('"unterminated')


# ---------------------------------------------------------------------------
# TestMultiLineDoubleQuotedStrings
# ---------------------------------------------------------------------------


class TestMultiLineDoubleQuotedStrings:
    def test_basic_multiline_string(self):
        text = 'name = "line one\nline two"'
        toks = tokens(text)
        s = first_of(toks, TokenType.STRING)
        assert "\n" in s.value
        assert s.value.startswith('"')
        assert s.value.endswith('"')

    def test_multiline_string_preserves_content(self):
        text = 'name = "hello\nworld"'
        toks = tokens(text)
        s = first_of(toks, TokenType.STRING)
        assert s.value == '"hello\nworld"'

    def test_multiline_string_with_escaped_quotes(self):
        text = 'name = "say ""hi""\nacross lines"'
        toks = tokens(text)
        s = first_of(toks, TokenType.STRING)
        assert '""hi""' in s.value
        assert "\n" in s.value

    def test_unterminated_multiline_string_raises(self):
        text = 'name = "never closed\nstill open'
        with pytest.raises(TMDLLexerError, match="Unterminated multi-line string"):
            tokens(text)

    def test_multiline_string_newline_on_closing_line(self):
        # NEWLINE token should carry the closing line number
        text = 'name = "line1\nline2\nline3"'
        toks = tokens(text)
        # Find the NEWLINE that follows the multi-line STRING
        found_string = False
        for t in toks:
            if found_string and t.type == TokenType.NEWLINE:
                assert t.line == 3
                return
            if t.type == TokenType.STRING and "\n" in t.value:
                found_string = True
        pytest.fail("Expected NEWLINE after multi-line STRING")

    def test_multiline_string_tokens_before_quote(self):
        # Tokens before the unclosed quote should still be emitted
        text = 'measure M = "line1\nline2"'
        toks = tokens(text)
        tt = [t.type for t in toks]
        assert TokenType.KEYWORD in tt
        assert TokenType.IDENTIFIER in tt
        assert TokenType.EQUALS in tt


# ---------------------------------------------------------------------------
# TestNumbers
# ---------------------------------------------------------------------------


class TestNumbers:
    @pytest.mark.parametrize("num", ["0", "42", "1567"])
    def test_integer(self, num):
        toks = tokens(num)
        assert toks[0].type == TokenType.NUMBER
        assert toks[0].value == num

    @pytest.mark.parametrize("num", ["1.5", "0.0", "3.14"])
    def test_decimal(self, num):
        toks = tokens(num)
        assert toks[0].type == TokenType.NUMBER
        assert toks[0].value == num

    def test_negative_integer(self):
        toks = tokens("-42")
        assert toks[0].type == TokenType.NUMBER
        assert toks[0].value == "-42"

    def test_negative_decimal(self):
        toks = tokens("-1.5")
        assert toks[0].type == TokenType.NUMBER
        assert toks[0].value == "-1.5"

    @pytest.mark.parametrize("num", ["1.2.3", "1.2.3.4"])
    def test_multi_dot_raises(self, num):
        with pytest.raises(TMDLLexerError):
            tokens(num)

    def test_trailing_dot_raises(self):
        with pytest.raises(TMDLLexerError):
            tokens("1.")

    def test_digits_followed_by_alpha_becomes_identifier(self):
        toks = tokens("123abc")
        assert toks[0].type == TokenType.IDENTIFIER
        assert toks[0].value == "123abc"

    def test_uuid_becomes_identifier(self):
        uuid = "6bf63ad9-2603-438b-a700-cb53cdeb7e5a"
        toks = tokens(uuid)
        assert toks[0].type == TokenType.IDENTIFIER
        assert toks[0].value == uuid


# ---------------------------------------------------------------------------
# TestMQuotedIdentifiers
# ---------------------------------------------------------------------------


class TestMQuotedIdentifiers:
    def test_simple_m_quoted_identifier(self):
        toks = tokens('#"Promoted Headers"')
        s = first_of(toks, TokenType.STRING)
        assert s.value == '#"Promoted Headers"'

    def test_m_quoted_with_escaped_inner_quote(self):
        toks = tokens('#"say ""hi"""')
        s = first_of(toks, TokenType.STRING)
        assert s.value.startswith('#"')

    def test_unterminated_m_quoted_raises(self):
        with pytest.raises(TMDLLexerError):
            tokens('#"unterminated')

    def test_hash_without_quote_is_string_char(self):
        # '#' not followed by '"' falls through to STRING (unrecognized char)
        toks = tokens("#notquoted")
        assert toks[0].type == TokenType.STRING
        assert toks[0].value == "#"


# ---------------------------------------------------------------------------
# TestBacktickExpressions
# ---------------------------------------------------------------------------


class TestBacktickExpressions:
    def test_single_line_backtick(self):
        toks = tokens("measure Total = ```content```")
        tt = [t.type for t in toks]
        assert TokenType.KEYWORD in tt
        assert TokenType.IDENTIFIER in tt
        assert TokenType.EQUALS in tt
        s = first_of(toks, TokenType.STRING)
        assert s.value == "content"

    def test_single_line_backtick_no_space(self):
        # Bug 3: no space between = and ```
        toks = tokens("measure Total =```content```")
        s = first_of(toks, TokenType.STRING)
        assert s.value == "content"

    def test_single_line_backtick_extra_spaces(self):
        # Bug 3: extra spaces between = and ```
        toks = tokens("measure Total =   ```content```")
        s = first_of(toks, TokenType.STRING)
        assert s.value == "content"

    def test_multi_line_backtick_basic(self):
        text = "measure Total = ```\nDIVIDE(A, B)\n```"
        toks = tokens(text)
        s = first_of(toks, TokenType.STRING)
        assert s.value == "DIVIDE(A, B)"

    def test_multi_line_backtick_preserves_internal_newlines(self):
        text = "measure Total = ```\nline1\nline2\n```"
        toks = tokens(text)
        s = first_of(toks, TokenType.STRING)
        assert "\n" in s.value

    def test_closing_line_number_on_newline_token(self):
        # Bug 4: NEWLINE token carries the closing ``` line number.
        # Opening on line 1, 3 content lines, closing ``` on line 5.
        text = "measure Total = ```\nline1\nline2\nline3\n```"
        toks = tokens(text)
        nl_after_string = None
        found_string = False
        for t in toks:
            if found_string and t.type == TokenType.NEWLINE:
                nl_after_string = t
                break
            if t.type == TokenType.STRING and "\n" in t.value:
                found_string = True
        assert nl_after_string is not None
        assert nl_after_string.line == 5

    def test_line_ending_with_backtick_is_content_not_closing(self):
        # Bug 1: a line ending with ``` that is NOT alone is content.
        text = "measure M = ```\nresult = x ```\n```"
        toks = tokens(text)
        s = first_of(toks, TokenType.STRING)
        assert "```" in s.value

    def test_colon_before_equals_backtick_not_backtick(self):
        # Bug 2: colon before = prevents backtick assignment detection.
        text = "desc: some = ``` text"
        tt = types(text)
        assert TokenType.COLON in tt
        # Should NOT be treated as a backtick block
        strings = all_of(tokens(text), TokenType.STRING)
        assert any("some = ```" in s.value for s in strings)

    def test_unterminated_backtick_raises(self):
        with pytest.raises(TMDLLexerError):
            tokens("measure Total = ```\nno closing")

    def test_string_token_references_opening_line(self):
        text = "measure Total = ```\nline1\nline2\n```"
        toks = tokens(text)
        s = first_of(toks, TokenType.STRING)
        assert s.line == 1  # STRING references the opening line

    def test_single_line_empty_backtick(self):
        toks = tokens("measure M = ``````")
        s = first_of(toks, TokenType.STRING)
        assert s.value == ""


# ---------------------------------------------------------------------------
# TestLineAndColumnNumbers
# ---------------------------------------------------------------------------


class TestLineAndColumnNumbers:
    def test_keyword_at_line_one_column_one(self):
        toks = tokens("table Foo")
        kw = first_of(toks, TokenType.KEYWORD)
        assert kw.line == 1
        assert kw.column == 1

    def test_identifier_column_after_keyword(self):
        # "table " is 6 chars, so "Foo" starts at col 7
        toks = tokens("table Foo")
        ident = first_of(toks, TokenType.IDENTIFIER)
        assert ident.column == 7

    def test_token_on_second_line(self):
        toks = tokens("table Foo\n\tdataType: string")
        # "dataType" is on line 2; "Foo" is on line 1
        ident = next(
            t for t in toks if t.type == TokenType.IDENTIFIER and t.value == "dataType"
        )
        assert ident.line == 2

    def test_column_reset_on_new_line(self):
        # indent_level=1 → col starts at 2 for nested tokens
        toks = tokens("table Foo\n\tdataType: string")
        ident = next(
            t for t in toks if t.type == TokenType.IDENTIFIER and t.value == "dataType"
        )
        assert ident.column == 2

    def test_eof_line_matches_last_content_line(self):
        toks = tokens("table Foo\ntable Bar")
        eof = toks[-1]
        assert eof.type == TokenType.EOF
        assert eof.line == 2


# ---------------------------------------------------------------------------
# TestTMDLLexerError
# ---------------------------------------------------------------------------


class TestTMDLLexerError:
    def test_error_has_line_number(self):
        # Unterminated quoted name on line 3
        text = "table Foo\n\tcolumn Bar\n\t\t'unterminated"
        with pytest.raises(TMDLLexerError) as exc_info:
            tokens(text)
        assert exc_info.value.line == 3

    def test_error_has_file_path(self):
        with pytest.raises(TMDLLexerError) as exc_info:
            tokens("'bad", file_path="myfile.tmdl")
        assert exc_info.value.file_path == "myfile.tmdl"

    def test_error_without_file_path(self):
        with pytest.raises(TMDLLexerError) as exc_info:
            tokens("'bad")
        assert exc_info.value.file_path is None

    def test_error_str_contains_location(self):
        with pytest.raises(TMDLLexerError) as exc_info:
            tokens("'bad", file_path="myfile.tmdl")
        assert "myfile.tmdl" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestSequenceInvariants
# ---------------------------------------------------------------------------


class TestSequenceInvariants:
    @pytest.mark.parametrize(
        "text",
        [
            "table Foo",
            "table Foo\n\tisHidden",
            "relationship r1\n\tfromColumn: 'Table'.'Col'",
            "model Model\n\tculture: en-US",
            "",
        ],
    )
    def test_eof_is_always_last(self, text):
        toks = tokens(text)
        assert toks[-1].type == TokenType.EOF

    def test_no_token_after_eof(self):
        gen = TMDLLexer("table Foo").tokenize()
        list(gen)  # exhaust
        with pytest.raises(StopIteration):
            next(gen)

    def test_indent_dedent_balance(self):
        text = "table Foo\n\tcolumn Bar\n\t\tdataType: string\ntable Baz\n\tisHidden\n"
        toks = tokens(text)
        indent_count = sum(1 for t in toks if t.type == TokenType.INDENT)
        dedent_count = sum(1 for t in toks if t.type == TokenType.DEDENT)
        assert indent_count == dedent_count

    def test_no_consecutive_newlines(self):
        text = "table Foo\n\n\n\tcolumn Bar\n\n\t\tdataType: string"
        toks = tokens(text)
        for a, b in zip(toks, toks[1:]):
            assert not (a.type == TokenType.NEWLINE and b.type == TokenType.NEWLINE), (
                f"Consecutive NEWLINEs at line {b.line}"
            )

    def test_no_token_has_line_zero(self):
        toks = tokens("table Foo\n\tisHidden\ntable Bar")
        for t in toks:
            assert t.line >= 1, f"Token with line=0: {t!r}"


# ---------------------------------------------------------------------------
# TestUnrecognizedCharacters
# ---------------------------------------------------------------------------


class TestUnrecognizedCharacters:
    """Unrecognized characters are emitted as STRING tokens.

    This is intentional: M expression continuation lines contain punctuation
    like (, ), [, ], {, } that the lexer passes through.  Validation of
    unexpected characters is deferred to the parser.
    """

    @pytest.mark.parametrize("char", ["(", ")", "[", "]", "{", "}", ";", ",", "@", "$"])
    def test_single_unrecognized_char_becomes_string(self, char):
        toks = tokens(char)
        assert toks[0].type == TokenType.STRING
        assert toks[0].value == char

    def test_multiple_unrecognized_chars_are_individual_tokens(self):
        toks = tokens("()")
        strings = all_of(toks, TokenType.STRING)
        assert len(strings) == 2
        assert strings[0].value == "("
        assert strings[1].value == ")"

    def test_unrecognized_mixed_with_identifiers(self):
        # Simulates M expression content: SUM(x)
        toks = tokens("SUM(x)")
        tt = [
            t.type
            for t in toks
            if t.type != TokenType.NEWLINE and t.type != TokenType.EOF
        ]
        assert tt == [
            TokenType.IDENTIFIER,
            TokenType.STRING,
            TokenType.IDENTIFIER,
            TokenType.STRING,
        ]
