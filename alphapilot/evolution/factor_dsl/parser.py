"""Pratt parser for the data-only factor expression grammar."""

from __future__ import annotations

from .ast import BinaryOp, ComparisonOp, Expression, FieldReference, FunctionCall, NumberLiteral, UnaryOp
from .lexer import FactorLexError, Token, tokenize
from .operators import PARSER_FUNCTION_NAMES


class FactorSyntaxError(ValueError):
    pass


RESERVED_IDENTIFIERS = {
    "import",
    "from",
    "as",
    "lambda",
    "eval",
    "exec",
    "open",
    "compile",
    "input",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "__import__",
    "os",
    "sys",
    "subprocess",
    "pathlib",
    "builtins",
}

INFIX_PRECEDENCE = {
    "LT": 10,
    "LE": 10,
    "GT": 10,
    "GE": 10,
    "EQ": 10,
    "NE": 10,
    "PLUS": 20,
    "MINUS": 20,
    "STAR": 30,
    "SLASH": 30,
}
COMPARISON_KINDS = {"LT", "LE", "GT", "GE", "EQ", "NE"}


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def expect(self, kind: str) -> Token:
        if self.current.kind != kind:
            raise FactorSyntaxError(
                f"Expected {kind} at position {self.current.position}, got {self.current.kind}"
            )
        return self.advance()

    def parse(self) -> Expression:
        expression = self.parse_expression(0)
        if self.current.kind != "EOF":
            raise FactorSyntaxError(
                f"Unexpected token {self.current.value!r} at position {self.current.position}"
            )
        return expression

    def parse_expression(self, minimum_precedence: int) -> Expression:
        left = self.parse_prefix()
        while self.current.kind in INFIX_PRECEDENCE:
            precedence = INFIX_PRECEDENCE[self.current.kind]
            if precedence < minimum_precedence:
                break
            operator_token = self.advance()
            right = self.parse_expression(precedence + 1)
            if operator_token.kind in COMPARISON_KINDS:
                left = ComparisonOp(operator_token.value, left, right)
            else:
                left = BinaryOp(operator_token.value, left, right)
        return left

    def parse_prefix(self) -> Expression:
        token = self.current
        if token.kind == "NUMBER":
            self.advance()
            return NumberLiteral(token.value)
        if token.kind == "IDENT":
            self.advance()
            if token.value.lower() in RESERVED_IDENTIFIERS:
                raise FactorSyntaxError(f"Reserved identifier {token.value!r} is forbidden")
            if self.current.kind == "LPAREN":
                if token.value not in PARSER_FUNCTION_NAMES:
                    raise FactorSyntaxError(f"Unknown or forbidden function {token.value!r}")
                return self.parse_function(token.value)
            return FieldReference(token.value)
        if token.kind in {"PLUS", "MINUS"}:
            self.advance()
            return UnaryOp(token.value, self.parse_expression(40))
        if token.kind == "LPAREN":
            self.advance()
            expression = self.parse_expression(0)
            self.expect("RPAREN")
            return expression
        raise FactorSyntaxError(
            f"Unexpected token {token.value!r} at position {token.position}"
        )

    def parse_function(self, name: str) -> FunctionCall:
        self.expect("LPAREN")
        args: list[Expression] = []
        if self.current.kind != "RPAREN":
            while True:
                args.append(self.parse_expression(0))
                if self.current.kind != "COMMA":
                    break
                self.advance()
        self.expect("RPAREN")
        return FunctionCall(name, tuple(args))


def parse_expression(expression: str) -> Expression:
    try:
        return _Parser(tokenize(expression)).parse()
    except FactorLexError as exc:
        raise FactorSyntaxError(str(exc)) from exc
