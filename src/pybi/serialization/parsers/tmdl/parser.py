"""TMDL parser - converts token stream to AST nodes."""

from dataclasses import dataclass, field
from typing import Any

from .exceptions import TMDLParseError
from .grammar import FLAG_PROPERTIES
from .lexer import (
    TMDLLexer,
    Token,
    TokenType,
)


@dataclass
class PropertyNode:
    """Represents a property in TMDL (key: value or key = value)."""

    key: str
    value: Any
    line: int
    is_expression: bool = False  # True if using = instead of :


@dataclass
class ObjectDeclaration:
    """Represents an object declaration in TMDL."""

    object_type: str  # table, column, measure, etc.
    name: str | None  # Name of the object (optional for some types)
    expression: str | None  # Expression value (for measure/expression with =)
    properties: list[PropertyNode] = field(default_factory=list)
    children: list["ObjectDeclaration"] = field(default_factory=list)
    description: str | None = None
    line: int = 0


class TMDLParser:
    """Recursive-descent parser that converts a TMDL token stream into AST nodes.

    Produces two node types:

    * ``ObjectDeclaration`` : keyword-introduced objects (table, column,
      annotation, …).  Annotations are regular children with
      ``object_type="annotation"``.
    * ``PropertyNode`` : ``key: value`` or ``key = expression`` pairs

    Lexer contract
    --------------
    After a COLON or EQUALS token the lexer emits the entire remaining line
    text as a single STRING token (rest-of-line capture).  Methods such as
    ``_collect_property_value`` and ``_collect_expression_value`` rely on
    this: they read at most one token and perform type conversion locally.
    """

    def __init__(self, text: str, file_path: str | None = None):
        self.text = text
        self.file_path = file_path
        self.lexer = TMDLLexer(text, file_path)
        self.tokens: list[Token] = []
        self.pos = 0

    def _error(self, message: str, token: Token | None = None) -> TMDLParseError:
        line = token.line if token else None
        return TMDLParseError(message, line=line, file_path=self.file_path)

    def _current(self) -> Token:
        """Get the current token."""
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]

    def _peek(self, offset: int = 0) -> Token:
        """Peek at a token without consuming it."""
        pos = self.pos + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[pos]

    def _advance(self) -> Token:
        """Consume and return the current token."""
        token = self._current()
        if token.type != TokenType.EOF:
            self.pos += 1
        return token

    def _skip_newlines(self) -> None:
        """Skip NEWLINE tokens."""
        while self._current().type == TokenType.NEWLINE:
            self._advance()

    def _expect(self, token_type: TokenType) -> Token:
        """Expect a specific token type."""
        token = self._current()
        if token.type != token_type:
            raise self._error(
                f"Expected {token_type.name}, got {token.type.name}", token
            )
        return self._advance()

    def parse(self) -> list[ObjectDeclaration]:
        """Parse the TMDL text into a list of AST nodes."""
        # Tokenize
        self.tokens = list(self.lexer.tokenize())
        self.pos = 0

        nodes: list[ObjectDeclaration] = []
        self._skip_newlines()

        while self._current().type != TokenType.EOF:
            node = self._parse_object_or_property(indent_level=0)
            if node:
                nodes.append(node)
            self._skip_newlines()

        return nodes

    def _parse_object_or_property(self, indent_level: int) -> ObjectDeclaration | None:
        """Parse an object declaration or property at the current position."""
        self._skip_newlines()
        token = self._current()

        if token.type == TokenType.EOF:
            return None

        # Handle DEDENT - skip it
        if token.type == TokenType.DEDENT:
            self._advance()
            return None

        # Handle INDENT at top level - skip it (shouldn't happen but be safe)
        if token.type == TokenType.INDENT:
            self._advance()
            return None

        # Collect description if present
        description = None
        while self._current().type == TokenType.DESCRIPTION:
            desc_token = self._advance()
            if description:
                description += "\n" + desc_token.value
            else:
                description = desc_token.value
            self._skip_newlines()

        token = self._current()

        # Check for keyword (object declaration)
        if token.type == TokenType.KEYWORD:
            obj = self._parse_object_declaration()
            if obj and description:
                obj.description = description
            return obj

        # Skip unknown tokens to avoid infinite loop
        self._advance()
        return None

    def _parse_object_declaration(self) -> ObjectDeclaration:
        """Parse an object declaration (table, column, measure, etc.)."""
        keyword_token = self._expect(TokenType.KEYWORD)
        object_type = keyword_token.value
        line = keyword_token.line

        name: str | None = None
        expression: str | None = None
        has_expression_assignment = False  # Track if we saw =

        # Parse name (can be identifier, quoted name, number, or absent)
        token = self._current()
        if token.type == TokenType.IDENTIFIER:
            name = self._advance().value
        elif token.type == TokenType.QUOTED_NAME:
            name = self._advance().value
        elif token.type == TokenType.NUMBER:
            # Column/measure names that start with a digit (e.g. "column 3")
            name = str(self._advance().value)
        elif token.type == TokenType.KEYWORD and object_type == "ref":
            # 'ref table TableName' - the second keyword is the ref type
            ref_type = self._advance().value
            name = ref_type
            # Now get the actual name
            token = self._current()
            if token.type == TokenType.IDENTIFIER:
                name = f"{ref_type} {self._advance().value}"
            elif token.type == TokenType.QUOTED_NAME:
                name = f"{ref_type} {self._advance().value}"
        elif token.type == TokenType.STRING:
            # Fallback: collect consecutive STRING/IDENTIFIER/NUMBER tokens as the
            # name (handles non-standard names like ?Visualize? where ? lexes as
            # STRING).  Stop before structural tokens (=, :, NEWLINE, INDENT, EOF).
            _stop = {
                TokenType.EQUALS,
                TokenType.COLON,
                TokenType.NEWLINE,
                TokenType.INDENT,
                TokenType.DEDENT,
                TokenType.EOF,
            }
            parts: list[str] = []
            while self._current().type not in _stop:
                t = self._advance()
                if t.type == TokenType.QUOTED_NAME:
                    parts.append(f"'{t.value}'")
                else:
                    parts.append(str(t.value))
            if parts:
                name = "".join(parts)

        # Check for expression (=) or properties (:)
        token = self._current()
        if token.type == TokenType.EQUALS:
            self._advance()  # consume =
            has_expression_assignment = True
            # Collect expression value on same line
            token = self._current()
            if token.type == TokenType.STRING:
                expression = self._advance().value
            elif token.type in (
                TokenType.IDENTIFIER,
                TokenType.QUOTED_NAME,
                TokenType.NUMBER,
            ):
                expression = self._advance().value

        obj = ObjectDeclaration(
            object_type=object_type,
            name=name,
            expression=expression,
            line=line,
        )

        # Skip to end of line
        self._skip_to_newline()
        self._skip_newlines()

        # Check for INDENT (nested content)
        if self._current().type == TokenType.INDENT:
            self._advance()  # consume INDENT
            # If we had an = sign with NO expression on same line, the indented content is the expression body
            # If we already have an expression, the indented content is properties
            if has_expression_assignment and not expression:
                # Multi-line expression: body follows on indented lines
                expr_body = self._collect_indented_content()
                obj.expression = expr_body
                # After expression body, there may be properties/annotations at a shallower indent.
                # We may see DEDENT tokens followed by an INDENT token to reach property scope.
                # Only consume DEDENTs if they are followed by an INDENT (property scope).
                # Otherwise, leave them for the parent's _parse_nested_content to terminate on.
                count = 0
                while self._peek(count).type == TokenType.DEDENT:
                    count += 1
                if self._peek(count).type == TokenType.INDENT:
                    for _ in range(count):
                        self._advance()  # consume DEDENTs
                    self._advance()  # consume INDENT to enter property scope
                    self._parse_nested_content(obj)
            else:
                # Single-line expression or no expression: indented content is properties
                self._parse_nested_content(obj)

        return obj

    def _skip_to_newline(self) -> None:
        """Skip to the next NEWLINE token."""
        while self._current().type not in (TokenType.NEWLINE, TokenType.EOF):
            self._advance()

    def _parse_nested_content(self, parent: ObjectDeclaration) -> None:
        """Parse nested content (properties, annotations, children) of an object."""
        self._skip_newlines()

        while self._current().type not in (TokenType.DEDENT, TokenType.EOF):
            token = self._current()

            # Collect consecutive description lines (/// ...)
            if token.type == TokenType.DESCRIPTION:
                description = None
                while self._current().type == TokenType.DESCRIPTION:
                    desc_token = self._advance()
                    if description is not None:
                        description += "\n" + desc_token.value
                    else:
                        description = desc_token.value
                    self._skip_newlines()
                # Description applies to the next child object
                next_token = self._current()
                if next_token.type == TokenType.KEYWORD:
                    if self._peek(offset=1).type == TokenType.COLON:
                        prop = self._parse_property()
                        if prop:
                            parent.properties.append(prop)
                    else:
                        child = self._parse_object_declaration()
                        if child:
                            child.description = description
                            parent.children.append(child)
                elif next_token.type == TokenType.IDENTIFIER:
                    prop = self._parse_property()
                    if prop:
                        parent.properties.append(prop)
                continue

            # Keyword (child object or property with keyword name)
            if token.type == TokenType.KEYWORD:
                # Check if this is a property (keyword followed by colon)
                if self._peek(offset=1).type == TokenType.COLON:
                    # It's a property using a keyword as the name
                    prop = self._parse_property()
                    if prop:
                        parent.properties.append(prop)
                else:
                    # It's an object declaration (column, annotation, etc.)
                    child = self._parse_object_declaration()
                    if child:
                        parent.children.append(child)
                continue

            # Identifier (property or flag)
            if token.type == TokenType.IDENTIFIER:
                prop = self._parse_property()
                if prop:
                    parent.properties.append(prop)
                continue

            # Unexpected token - skip
            self._advance()
            self._skip_newlines()

        # Consume DEDENT if present
        if self._current().type == TokenType.DEDENT:
            self._advance()

    def _parse_property(self) -> PropertyNode | None:
        """Parse a property declaration."""
        name_token = self._current()
        # Properties can be identifiers, quoted names, or keywords used as property names
        if name_token.type not in (
            TokenType.IDENTIFIER,
            TokenType.QUOTED_NAME,
            TokenType.KEYWORD,
        ):
            self._advance()
            return None

        name = self._advance().value
        line = name_token.line
        is_expression = False
        value: Any = None

        token = self._current()

        # Check for : (property value)
        if token.type == TokenType.COLON:
            self._advance()
            value = self._collect_property_value()
        # Check for = (expression value)
        elif token.type == TokenType.EQUALS:
            self._advance()
            is_expression = True
            value = self._collect_expression_value()
        else:
            # Flag property (presence = true)
            if name in FLAG_PROPERTIES:
                value = True
            else:
                # Check if next token on same line is a value
                if token.type in (
                    TokenType.STRING,
                    TokenType.NUMBER,
                    TokenType.BOOLEAN,
                    TokenType.IDENTIFIER,
                ):
                    value = self._parse_property_value()

        self._skip_to_newline()
        self._skip_newlines()

        # Check for multi-line value (indented content)
        if self._current().type == TokenType.INDENT:
            self._advance()
            indented = self._collect_indented_content()
            if value:
                value = str(value) + "\n" + indented
            else:
                value = indented

        return PropertyNode(
            key=name, value=value, line=line, is_expression=is_expression
        )

    def _collect_property_value(self) -> Any:
        """Collect the property value after a colon.

        The lexer emits at most one STRING token after COLON (rest-of-line
        capture).  This method returns the raw string : type coercion is
        deferred to the transformer / Pydantic layer which has schema
        awareness.
        """
        token = self._current()
        if token.type in (TokenType.NEWLINE, TokenType.EOF):
            return None

        return self._advance().value

    def _parse_property_value(self) -> Any:
        """Parse a single property value token.

        Returns the raw string value : type coercion is deferred to the
        transformer / Pydantic layer.
        """
        token = self._current()

        if token.type in (
            TokenType.STRING,
            TokenType.QUOTED_NAME,
            TokenType.NUMBER,
            TokenType.BOOLEAN,
            TokenType.IDENTIFIER,
        ):
            return self._advance().value

        return None

    def _collect_expression_value(self) -> str:
        """Collect the expression value after an equals sign.

        The lexer emits at most one STRING token after EQUALS (rest-of-line
        capture).
        """
        token = self._current()
        if token.type in (TokenType.NEWLINE, TokenType.EOF):
            return ""
        return self._advance().value

    def _collect_indented_content(self) -> str:
        """Collect indented content as a multi-line string.

        Tracks INDENT/DEDENT nesting so that internal indent changes
        within the expression body (e.g. DAX with varying indentation)
        are correctly captured.
        """
        lines = []
        base_indent = 0
        nesting_depth = 0

        while True:
            current = self._current()
            if current.type == TokenType.EOF:
                break
            if current.type == TokenType.DEDENT:
                if nesting_depth <= 0:
                    # This DEDENT exits our scope : consume it and stop
                    self._advance()
                    break
                # Internal DEDENT (within the expression body)
                self._advance()
                nesting_depth -= 1
                continue
            if current.type == TokenType.INDENT:
                # Internal INDENT (within the expression body)
                self._advance()
                nesting_depth += 1
                continue

            line_parts = []
            current_indent = current.indent_level

            # Collect tokens on this line
            while self._current().type not in (
                TokenType.NEWLINE,
                TokenType.DEDENT,
                TokenType.INDENT,
                TokenType.EOF,
            ):
                token = self._advance()
                if token.type == TokenType.STRING:
                    line_parts.append(token.value)
                elif token.type == TokenType.QUOTED_NAME:
                    line_parts.append(f"'{token.value}'")
                elif token.type == TokenType.COLON:
                    line_parts.append(":")
                elif token.type == TokenType.EQUALS:
                    line_parts.append("=")
                else:
                    line_parts.append(str(token.value))

            if line_parts:
                indent_prefix = "\t" * max(0, current_indent - base_indent - 1)
                result = self._smart_join_expression(line_parts)
                lines.append(indent_prefix + result)

            if self._current().type == TokenType.NEWLINE:
                self._advance()

        return "\n".join(lines)

    def _smart_join_expression(self, parts: list[str]) -> str:
        """Join expression parts with smart spacing around punctuation."""
        if not parts:
            return ""

        result = []
        no_space_before = {"(", ")", "]", ",", ";", "["}
        no_space_after = {"(", "["}

        for i, part in enumerate(parts):
            if i == 0:
                result.append(part)
            else:
                prev_part = parts[i - 1]
                # Don't add space if current part is punctuation that shouldn't have space before
                # or if previous part is punctuation that shouldn't have space after
                if part in no_space_before or prev_part in no_space_after:
                    result.append(part)
                else:
                    result.append(" " + part)

        return "".join(result)


def parse_tmdl(text: str, file_path: str | None = None) -> list[ObjectDeclaration]:
    """Parse TMDL text into a list of AST nodes.

    Args:
        text: The TMDL text to parse.
        file_path: Optional file path for error messages.

    Returns:
        List of ObjectDeclaration nodes.
    """
    parser = TMDLParser(text, file_path)
    return parser.parse()
