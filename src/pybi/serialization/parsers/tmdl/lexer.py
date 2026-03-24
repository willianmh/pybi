from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator

from .exceptions import TMDLLexerError
from .grammar import (
    BACKTICK_ASSIGN_RE,
    BACKTICK_EXPR,
    IDENTIFIER_CONTINUATION_CHARS,
    KEYWORDS,
)

# Pre-built set for O(1) identifier-character checks in hot loops.
_IDENT_CHARS = (
    frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    | IDENTIFIER_CONTINUATION_CHARS
)

_BOOLEANS = {"true": "true", "false": "false"}


class TokenType(Enum):
    """Token types for TMDL lexer."""

    # Keywords
    KEYWORD = auto()

    # Identifiers and names
    IDENTIFIER = auto()
    QUOTED_NAME = auto()

    # Operators
    COLON = auto()
    EQUALS = auto()

    # Indentation
    INDENT = auto()
    DEDENT = auto()
    NEWLINE = auto()

    # Literals
    STRING = auto()
    NUMBER = auto()
    BOOLEAN = auto()

    # Special
    DESCRIPTION = auto()  # /// prefix
    EOF = auto()


@dataclass
class Token:
    """Represents a token in TMDL."""

    type: TokenType
    value: str
    line: int
    column: int
    indent_level: int = 0

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, line={self.line})"


class TMDLLexer:
    """Tokenizer for TMDL files.

    Design decisions
    ----------------
    * **Rest-of-line capture after ``:`` / ``=``**:  After a COLON or EQUALS
      token the entire remaining line text is emitted as a single STRING
      token.  This means ``isActive: false`` produces IDENTIFIER COLON
      STRING("false"), *not* IDENTIFIER COLON BOOLEAN.  The parser layer
      is responsible for type interpretation.  This is intentional because
      TMDL colon/equals values can contain arbitrary text (format strings,
      column references, expressions) that must not be sub-tokenized.

    * **Tab-only structural indentation**:  Indentation depth is measured
      exclusively by leading tab characters.  Spaces within line content
      (e.g. M expression continuation lines) are not structural.

    * **Flexible intermediate indent levels**:  When dedenting to a level
      not previously on the indent stack the lexer creates a new level.
      This supports TMDL patterns where multi-line expression bodies are
      indented deeper than the properties that follow them (e.g. body at
      level 3, next property at level 2).  The trade-off is that genuine
      indentation errors at intermediate levels are not caught here.
    """

    def __init__(self, text: str, file_path: str | None = None):
        self.text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.file_path = file_path
        self.line = 1
        self.indent_stack = [0]  # Stack of indentation levels

    def _error(self, message: str) -> TMDLLexerError:
        return TMDLLexerError(message, line=self.line, file_path=self.file_path)

    @staticmethod
    def _is_comment_line(content: str) -> bool:
        """Return True if content is a // comment (but not a /// description).

        Handles both lines starting with '/' and M expression continuation
        lines where spaces precede the '//' comment marker.
        """
        c0 = content[0]
        if c0 != "/" and c0 != " ":
            return False
        stripped = content if c0 == "/" else content.lstrip()
        return (
            len(stripped) >= 2
            and stripped[0] == "/"
            and stripped[1] == "/"
            and (len(stripped) < 3 or stripped[2] != "/")
        )

    def _handle_backtick_expression(
        self, content: str, lines: list[str], line_idx: int, indent_level: int
    ) -> tuple[list[Token], int]:
        """Handle a multi-line backtick-enclosed expression.

        TMDL uses triple backticks (```) to enclose verbatim expressions.
        Everything between opening and closing ``` is preserved as-is.

        The closing ``` must appear *alone* on a line (only surrounding
        whitespace is permitted).  A line that merely ends with ``` is
        expression content, not a closing marker.

        Args:
            content: The line content containing = ```
            lines: All lines of the file
            line_idx: Current line index (0-based)
            indent_level: Current indentation level

        Returns:
            A tuple of (tokens, next_line_index).
        """
        tokens: list[Token] = []
        opening_line = self.line  # STRING token always references the opening line

        # Use the regex so any amount of whitespace between '=' and '```'
        # is handled correctly (e.g. '=```' or '=   ```').
        bt_match = BACKTICK_ASSIGN_RE.search(content)
        assert bt_match is not None  # Caller already verified the match

        # Everything up to and including '='
        before_backtick = content[: bt_match.start() + 1].strip()
        # Tokenize the part before the backticks (object name + EQUALS).
        # Invariant: before_backtick ends with '=' so _tokenize_line will
        # never encounter another '= ```' inside it.
        tokens.extend(self._tokenize_line(before_backtick, indent_level))

        # Content on the same line after the opening ```
        after_backtick = content[bt_match.end() :].lstrip()

        expr_lines: list[str] = []
        current_line_idx = line_idx

        if after_backtick:
            # Single-line form: the expression opens and closes on the same line.
            # Strip trailing whitespace before checking for the closing ```.
            after_stripped = after_backtick.rstrip()
            if after_stripped.endswith(BACKTICK_EXPR):
                expr_value = after_stripped[: -len(BACKTICK_EXPR)]
                tokens.append(
                    Token(
                        TokenType.STRING,
                        expr_value,
                        opening_line,
                        len(before_backtick) + 2,
                        indent_level,
                    )
                )
                tokens.append(
                    Token(
                        TokenType.NEWLINE,
                        "\n",
                        opening_line,
                        len(content) + 1,
                        indent_level,
                    )
                )
                return tokens, line_idx + 1
            else:
                expr_lines.append(after_backtick)

        # Multi-line form: read lines until ``` appears alone on a line.
        # Only a line whose *entire* stripped content is ``` counts as the
        # closing marker.  A line that merely ends with ``` (e.g. a DAX
        # comment or string literal) is expression content.
        current_line_idx += 1
        found_closing = False
        closing_line_idx = current_line_idx
        while current_line_idx < len(lines):
            line = lines[current_line_idx]
            stripped = line.strip()

            if stripped == BACKTICK_EXPR:
                closing_line_idx = current_line_idx
                found_closing = True
                break

            expr_lines.append(line)
            current_line_idx += 1

        if not found_closing:
            raise self._error("Unterminated backtick expression")

        expr_value = "\n".join(expr_lines)
        # The NEWLINE token carries the line number of the *closing* ```,
        # not of the opening line, so error messages after a large
        # expression point to the right location.
        closing_line = closing_line_idx + 1  # convert to 1-based
        tokens.append(
            Token(
                TokenType.STRING,
                expr_value,
                opening_line,
                len(before_backtick) + 2,
                indent_level,
            )
        )
        tokens.append(
            Token(
                TokenType.NEWLINE,
                "\n",
                closing_line,
                len(content) + 1,
                indent_level,
            )
        )

        return tokens, closing_line_idx + 1

    def _find_unclosed_dq(self, content: str) -> int | None:
        """Return the start index of the first unclosed '"' in *content*, or None.

        Scans left-to-right, treating consecutive double-quotes ('""') as an
        escaped quote that does not close the string.  Returns the opening
        position of the first string that has no matching closing '"' on the
        same line, or None when every '"' is properly paired.
        """
        i = 0
        n = len(content)
        while i < n:
            if content[i] != '"':
                i += 1
                continue
            # Found a potential opening quote at i; scan for its closing quote.
            j = i + 1
            found_close = False
            while j < n:
                if content[j] == '"':
                    if j + 1 < n and content[j + 1] == '"':
                        j += 2  # escaped quote — skip both
                    else:
                        found_close = True
                        j += 1
                        break
                else:
                    j += 1
            if not found_close:
                return i  # string opened at i, never closed on this line
            i = j  # continue scanning after the closed string
        return None

    def _handle_multiline_dq_string(
        self,
        content: str,
        lines: list[str],
        line_idx: int,
        indent_level: int,
        dq_start: int,
    ) -> tuple[list[Token], int]:
        """Handle a double-quoted string that spans multiple lines.

        Called when *content* contains a '"' at *dq_start* that is not closed
        on the same line.  Reads subsequent raw lines until the closing '"' is
        found, then emits a STRING token (carrying the full verbatim value,
        quotes included) followed by a NEWLINE on the closing line — mirroring
        the behaviour of ``_handle_backtick_expression``.

        Args:
            content:     Tab-stripped content of the current line.
            lines:       All lines of the file (original, with tabs).
            line_idx:    Current line index (0-based).
            indent_level: Current indentation level.
            dq_start:    Index within *content* where the unclosed '"' starts.

        Returns:
            ``(tokens, next_line_index)``
        """
        toks: list[Token] = []
        opening_line = self.line

        # Emit any tokens that appear before the opening '"' on this line.
        # By construction (_find_unclosed_dq), every '"' before dq_start is
        # properly closed, so _tokenize_line on the prefix is safe.
        if dq_start > 0:
            before = content[:dq_start].rstrip()
            if before:
                toks.extend(self._tokenize_line(before, indent_level))

        # Collect the multi-line string.  The first fragment is the tail of
        # the current (tab-stripped) content line; subsequent fragments are
        # the original raw lines (tabs included) so the verbatim value is
        # preserved exactly as written.
        string_parts: list[str] = [content[dq_start:]]

        # Scan for the closing '"' in subsequent lines.
        current_line_idx = line_idx + 1
        found_close = False
        closing_line_idx = line_idx

        while current_line_idx < len(lines):
            self.line = current_line_idx + 1
            raw_line = lines[current_line_idx]
            string_parts.append(raw_line)

            # Look for the closing '"' (honouring '""' escapes).
            j = 0
            n = len(raw_line)
            while j < n:
                if raw_line[j] == '"':
                    if j + 1 < n and raw_line[j + 1] == '"':
                        j += 2  # escaped quote
                    else:
                        found_close = True
                        closing_line_idx = current_line_idx
                        break
                else:
                    j += 1

            current_line_idx += 1
            if found_close:
                break

        if not found_close:
            raise self._error("Unterminated multi-line string literal")

        string_value = "\n".join(string_parts)
        closing_line = closing_line_idx + 1  # convert to 1-based

        toks.append(
            Token(
                TokenType.STRING,
                string_value,
                opening_line,
                dq_start + indent_level + 1,
                indent_level,
            )
        )
        toks.append(
            Token(
                TokenType.NEWLINE,
                "\n",
                closing_line,
                len(lines[closing_line_idx]) + 1,
                indent_level,
            )
        )
        return toks, current_line_idx

    def tokenize(self) -> Iterator[Token]:
        """Tokenize the TMDL text into tokens."""
        lines = self.text.split("\n")
        line_idx = 0
        num_lines = len(lines)

        while line_idx < num_lines:
            line = lines[line_idx]
            self.line = line_idx + 1

            # Skip empty / whitespace-only lines (avoid full .strip())
            if not line or line.isspace():
                line_idx += 1
                continue

            # Handle indentation (inlined _count_leading_tabs for speed)
            _stripped = line.lstrip("\t")
            indent_level = len(line) - len(_stripped)
            content = _stripped  # tab-free line content

            # Skip // comment lines (but not /// descriptions).
            # M expression bodies use spaces for internal indentation, so
            # "    // comment" (tabs stripped, spaces remain) must also be
            # caught.
            if self._is_comment_line(content):
                line_idx += 1
                continue

            # Generate INDENT/DEDENT tokens
            current_indent = self.indent_stack[-1]
            if indent_level > current_indent:
                self.indent_stack.append(indent_level)
                yield Token(TokenType.INDENT, "", self.line, 1, indent_level)
            elif indent_level < current_indent:
                while self.indent_stack and self.indent_stack[-1] > indent_level:
                    self.indent_stack.pop()
                    yield Token(TokenType.DEDENT, "", self.line, 1, indent_level)
                # Allow dedenting to an intermediate level not previously seen.
                # TMDL permits flexible indentation (e.g., multi-line JSON
                # values indented at level 3, followed by properties at
                # level 2).  The trade-off is that genuine indentation
                # errors at intermediate levels are not caught here.
                if self.indent_stack[-1] < indent_level:
                    self.indent_stack.append(indent_level)
                    yield Token(TokenType.INDENT, "", self.line, 1, indent_level)

            # Check for description (///)
            if (
                len(content) >= 3
                and content[0] == "/"
                and content[1] == "/"
                and content[2] == "/"
            ):
                desc_content = content[3:].strip()
                yield Token(
                    TokenType.DESCRIPTION,
                    desc_content,
                    self.line,
                    indent_level + 1,
                    indent_level,
                )
                yield Token(
                    TokenType.NEWLINE, "\n", self.line, len(line) + 1, indent_level
                )
                line_idx += 1
                continue

            # Check for backtick expression (= ```).
            # Guard with a colon-prefix check so that a colon-value line
            # such as "desc: some = ``` text" is never mistaken for a
            # backtick assignment.  The regex handles flexible whitespace
            # between '=' and '```' (e.g. '=```' and '=   ```').
            if "=" in content and "```" in content:
                _bt_match = BACKTICK_ASSIGN_RE.search(content)
                if _bt_match and ":" not in content[: _bt_match.start()]:
                    backtick_tokens, line_idx = self._handle_backtick_expression(
                        content, lines, line_idx, indent_level
                    )
                    yield from backtick_tokens
                    continue

            # Check for multi-line double-quoted string.
            # TMDL measure bodies can use a double-quoted string that spans
            # multiple lines (e.g. "text\nacross lines").  The single-line
            # path in _tokenize_string_literal raises on an unclosed '"', so
            # we detect that case here and hand off to the multi-line handler.
            if '"' in content:
                _dq_start = self._find_unclosed_dq(content)
                if _dq_start is not None:
                    _dq_tokens, line_idx = self._handle_multiline_dq_string(
                        content, lines, line_idx, indent_level, _dq_start
                    )
                    yield from _dq_tokens
                    continue

            # Tokenize the line content
            yield from self._tokenize_line(content, indent_level)
            yield Token(TokenType.NEWLINE, "\n", self.line, len(line) + 1, indent_level)

            line_idx += 1

        # Emit remaining DEDENT tokens
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            yield Token(TokenType.DEDENT, "", self.line, 1, 0)

        yield Token(TokenType.EOF, "", self.line, 1, 0)

    def _tokenize_line(self, content: str, indent_level: int) -> list[Token]:
        """Tokenize a single line of content by dispatching to character handlers."""
        tokens: list[Token] = []
        pos = 0
        col = indent_level + 1
        content_len = len(content)
        line = self.line  # Local copy — constant within _tokenize_line

        while pos < content_len:
            char = content[pos]

            # Skip whitespace (not tabs - those are for indentation)
            if char in " \t":
                pos += 1
                col += 1
                continue

            if char == ":":
                tokens.append(Token(TokenType.COLON, ":", line, col, indent_level))
                pos += 1
                col += 1
                # Skip leading whitespace after colon
                while pos < content_len and content[pos] in " \t":
                    pos += 1
                    col += 1
                remaining = content[pos:].rstrip()
                if remaining:
                    tokens.append(Token(TokenType.STRING, remaining, line, col, indent_level))
                return tokens

            if char == "=":
                tokens.append(Token(TokenType.EQUALS, "=", line, col, indent_level))
                pos += 1
                col += 1
                # Skip leading whitespace after equals
                while pos < content_len and content[pos] in " \t":
                    pos += 1
                    col += 1
                remaining = content[pos:].rstrip()
                if remaining:
                    tokens.append(Token(TokenType.STRING, remaining, line, col, indent_level))
                return tokens

            if char == "'":
                token, pos, col = self._tokenize_quoted_name(
                    content, pos, col, indent_level
                )
                tokens.append(token)
                continue

            if char == '"':
                token, pos, col = self._tokenize_string_literal(
                    content, pos, col, indent_level
                )
                tokens.append(token)
                continue

            if char.isdigit() or (
                char == "-" and pos + 1 < content_len and content[pos + 1].isdigit()
            ):
                token, pos, col = self._tokenize_number_or_uuid(
                    content, pos, col, indent_level
                )
                tokens.append(token)
                continue

            if char.isalpha() or char == "_":
                token, pos, col = self._tokenize_identifier_or_keyword(
                    content, pos, col, indent_level
                )
                tokens.append(token)
                continue

            if char == "#" and pos + 1 < content_len and content[pos + 1] == '"':
                token, pos, col = self._tokenize_m_quoted_identifier(
                    content, pos, col, indent_level
                )
                tokens.append(token)
                continue

            # Unrecognized character — emit as STRING to preserve in expression
            # content.  In practice this handles M expression punctuation
            # such as (, ), [, ], {, }, ;, and comma that appear on
            # continuation lines.  The lexer cannot distinguish structural
            # lines from expression content, so validation of unexpected
            # characters is deferred to the parser layer.
            tokens.append(Token(TokenType.STRING, char, line, col, indent_level))
            pos += 1
            col += 1

        return tokens

    # ------------------------------------------------------------------
    # Character-class handlers (called from _tokenize_line)
    # ------------------------------------------------------------------

    def _tokenize_quoted_name(
        self, content: str, pos: int, col: int, indent_level: int
    ) -> tuple[Token, int, int]:
        """Handle single-quoted name: 'Name With Spaces'."""
        start_col = col
        end_pos = pos + 1
        found_closing = False
        content_len = len(content)
        while end_pos < content_len:
            if content[end_pos] == "'":
                if end_pos + 1 < content_len and content[end_pos + 1] == "'":
                    end_pos += 2  # Skip escaped quote
                else:
                    end_pos += 1
                    found_closing = True
                    break
            else:
                end_pos += 1
        if not found_closing:
            raise self._error("Unterminated quoted name")
        quoted = content[pos + 1 : end_pos - 1].replace("''", "'")
        token = Token(TokenType.QUOTED_NAME, quoted, self.line, start_col, indent_level)
        col += end_pos - pos
        pos = end_pos
        return token, pos, col

    def _tokenize_string_literal(
        self, content: str, pos: int, col: int, indent_level: int
    ) -> tuple[Token, int, int]:
        """Handle double-quoted string — preserves quotes for expression content."""
        start_col = col
        end_pos = pos + 1
        found_closing = False
        content_len = len(content)
        while end_pos < content_len:
            if content[end_pos] == '"':
                if end_pos + 1 < content_len and content[end_pos + 1] == '"':
                    end_pos += 2  # Skip escaped quote
                else:
                    end_pos += 1
                    found_closing = True
                    break
            else:
                end_pos += 1
        if not found_closing:
            raise self._error("Unterminated string literal")
        quoted = content[pos:end_pos]  # Keep quotes for expression preservation
        token = Token(TokenType.STRING, quoted, self.line, start_col, indent_level)
        col += end_pos - pos
        pos = end_pos
        return token, pos, col

    def _tokenize_number_or_uuid(
        self, content: str, pos: int, col: int, indent_level: int
    ) -> tuple[Token, int, int]:
        """Handle digits — number or UUID-like identifier starting with digits."""
        start_col = col
        start_pos = pos
        content_len = len(content)
        if content[pos] == "-":
            pos += 1
            col += 1
        # Consume digits and dots
        while pos < content_len and (content[pos].isdigit() or content[pos] == "."):
            pos += 1
            col += 1
        # Check if followed by identifier characters (UUID-like pattern)
        if pos < content_len and (content[pos].isalpha() or content[pos] in "_-"):
            ident_chars = _IDENT_CHARS
            while pos < content_len and content[pos] in ident_chars:
                pos += 1
                col += 1
            word = content[start_pos:pos]
            token = Token(
                TokenType.IDENTIFIER, word, self.line, start_col, indent_level
            )
        else:
            num_str = content[start_pos:pos]
            # Validate numeric form: reject multi-dot patterns like "1.2.3"
            if num_str.count(".") > 1 or num_str.endswith("."):
                raise self._error(f"Invalid numeric literal {num_str!r}")
            token = Token(TokenType.NUMBER, num_str, self.line, start_col, indent_level)
        return token, pos, col

    def _tokenize_identifier_or_keyword(
        self, content: str, pos: int, col: int, indent_level: int
    ) -> tuple[Token, int, int]:
        """Handle alpha/underscore — boolean, keyword, or plain identifier."""
        start_col = col
        start_pos = pos
        content_len = len(content)
        ident_chars = _IDENT_CHARS
        while pos < content_len and content[pos] in ident_chars:
            pos += 1
        col += pos - start_pos
        word = content[start_pos:pos]

        # Boolean matching is intentionally case-insensitive per TMDL spec.
        # Single .lower() + dict lookup instead of two comparisons.
        word_lower = word.lower()
        bool_val = _BOOLEANS.get(word_lower)
        if bool_val is not None:
            token = Token(
                TokenType.BOOLEAN, bool_val, self.line, start_col, indent_level
            )
        elif word in KEYWORDS:
            token = Token(TokenType.KEYWORD, word, self.line, start_col, indent_level)
        else:
            token = Token(
                TokenType.IDENTIFIER, word, self.line, start_col, indent_level
            )
        return token, pos, col

    def _tokenize_m_quoted_identifier(
        self, content: str, pos: int, col: int, indent_level: int
    ) -> tuple[Token, int, int]:
        """Handle M expression quoted identifier: #\"name\"."""
        start_col = col
        start_pos = pos
        pos += 2  # Skip #"
        found_closing = False
        col += 2
        content_len = len(content)
        while pos < content_len:
            if content[pos] == '"':
                if pos + 1 < content_len and content[pos + 1] == '"':
                    pos += 2  # Skip escaped quote
                    col += 2
                else:
                    pos += 1
                    col += 1
                    found_closing = True
                    break
            else:
                pos += 1
                col += 1
        if not found_closing:
            raise self._error("Unterminated M quoted identifier")
        m_quoted = content[start_pos:pos]  # Include #"..." with quotes
        token = Token(TokenType.STRING, m_quoted, self.line, start_col, indent_level)
        return token, pos, col
