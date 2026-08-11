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
    func = parse_func(
        '@app_commands.command(name="ban")\n'
        '@app_commands.describe(user="x")\n'
        '@discord.ui.button\n'
        'async def ban(): pass\n'
    )
    assert decorator_names(func) == [
        # three strings in order
        "app_commands.command",
        "app_commands.describe",
        "discord.ui.button",
    ]

@pytest.mark.parametrize("decorator, expected", [
    ("@app_commands.command()", True),
    ("@app_commands.command", True),
    ("@mygroup.command()", True),
    ("@commands.hybrid_command()", True),
    ('@discord.ui.button(label="x")', False),
    ("@discord.ui.select()", False),
    ("@staticmethod", False),
    ("", False),
])
def test_is_slash_command(decorator, expected):
    func = parse_func(f"{decorator}\nasync def f(self, interaction): pass\n")
    # is, not > catches a None from falling off the end
    assert is_slash_command(func) is expected

def test_stacked_decorators_command_not_first():
    # command decorator is not always first > any(), not [0]
    func = parse_func(
        '@app_commands.describe(x="y")\n'
        '@commands.guild_only()\n'
        '@app_commands.command()\n'
        'async def f(self, interaction): pass\n'
    )
    assert is_slash_command(func) is True

def test_ui_reject_beats_command_accept():
    # reject list runs first and wins
    func = parse_func(
        '@app_commands.command()\n'
        '@discord.ui.button()\n'
        'async def f(self, interaction): pass\n'
    )
    assert is_slash_command(func) is False
