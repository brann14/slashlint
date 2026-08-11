# test_context.py

# imports

import ast

import pytest

from slashlint.context import (
    dotted_name,
    decorator_names,
    is_slash_command,
    interaction_param,
    response_method,
    build_context,
    contexts_from_module,
)

def parse_func(src):
    # parse a source string and return its first function
    return ast.parse(src).body[0]

@pytest.mark.parametrize("expr, expected", [
    ("a", "a"),
    ("a.b", "a.b"),
    ("discord.ui.button", "discord.ui.button"),
    ("f().x", None),
])
def test_dotted_name (expr, expected):
    node = ast.parse(expr, mode="eval").body
    assert dotted_name(node) == expected
    
def test_decorator_names_handles_both_forms():
    fun = parse_func(
        '@app_commands.command(name="ban")\n'
        'app_commands.describe(user="x")\n'
        '@discord.ui.button\n'
        'async def ban(): pass\n'
    )
    assert decorator_names(func) == [
        # three strings in order
        "app_commands.command",
        "app_commands.describe",
        "@discord.ui.button",
    ]