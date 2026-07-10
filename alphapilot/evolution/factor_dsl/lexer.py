"""Small lexer that rejects every token outside the factor grammar."""

from __future__ import annotations

import re
from dataclasses import dataclass


class FactorLexError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


NUMBER_RE = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SINGLE_TOKENS = {
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    "(": "LPAREN",
    ")": "RPAREN",
    ",": "COMMA",
    "<": "LT",
    ">": "GT",
}
DOUBLE_TOKENS = {"<=": "LE", ">=": "GE", "==": "EQ", "!=": "NE"}


def tokenize(expression: str) -> list[Token]:
    if not isinstance(expression, str) or not expression.strip():
        raise FactorLexError("Factor expression must be a non-empty string")
    tokens: list[Token] = []
    index = 0
    while index < len(expression):
        character = expression[index]
        if character.isspace():
            index += 1
            continue
        double = expression[index : index + 2]
        if double in DOUBLE_TOKENS:
            tokens.append(Token(DOUBLE_TOKENS[double], double, index))
            index += 2
            continue
        number_match = NUMBER_RE.match(expression, index)
        if number_match:
            value = number_match.group(0)
            tokens.append(Token("NUMBER", value, index))
            index = number_match.end()
            continue
        ident_match = IDENT_RE.match(expression, index)
        if ident_match:
            value = ident_match.group(0)
            tokens.append(Token("IDENT", value, index))
            index = ident_match.end()
            continue
        if character in SINGLE_TOKENS:
            tokens.append(Token(SINGLE_TOKENS[character], character, index))
            index += 1
            continue
        raise FactorLexError(f"Forbidden token {character!r} at position {index}")
    tokens.append(Token("EOF", "", len(expression)))
    return tokens
