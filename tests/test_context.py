# test_context.py

# imports

import ast

import pytest

from slashlint.context import (
    dotted_name,
    decorator_names,
    is_slash_command,
    interaction_param,
    ordered_calls,
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

@pytest.mark.parametrize("signature, expected", [
    ("self, interaction, member", "interaction"),
    ("itx", "itx"),
    ("cls, inter", "inter"),
    # unrecognised signature > None > caller drops the function
    ("self", None),
    ("", None),
])
def test_interaction_param(signature, expected):
    func = parse_func(f"async def f({signature}): pass\n")
    assert interaction_param(func) == expected

def call_names(func):
    # calls > their dotted names, easier to assert on
    return [dotted_name(c.func) for c in ordered_calls(func)]

def test_ordered_calls_source_order():
    # the case ast.walk gets wrong > it puts defer before db.execute
    func = parse_func('''
async def cmd(self, interaction, member):
    if is_admin(member):
        await db.execute("x")
    await interaction.response.defer()
''')
    assert call_names(func) == ["is_admin", "db.execute", "interaction.response.defer"]

def test_ordered_calls_skips_nested_def():
    # nested body does not run before the response
    func = parse_func('''
async def cmd(self, interaction):
    a()
    async def helper():
        never_seen()
    b()
''')
    assert call_names(func) == ["a", "b"]

def test_ordered_calls_skips_lambda():
    func = parse_func('''
async def cmd(self, interaction):
    a()
    f = lambda: hidden()
    b()
''')
    assert call_names(func) == ["a", "b"]

def test_ordered_calls_outer_before_args():
    # a call is recorded then we keep descending into its args
    func = parse_func('''
async def cmd(self, interaction):
    await db.execute(build_query(table_name()))
''')
    assert call_names(func) == ["db.execute", "build_query", "table_name"]

def test_ordered_calls_ignores_decorators():
    # we start at func.body, not func
    func = parse_func('''
@app_commands.command(name="ban")
@app_commands.describe(x="y")
async def cmd(self, interaction):
    only_this()
''')
    assert call_names(func) == ["only_this"]

@pytest.mark.parametrize("expr, param, expected", [
    ("interaction.response.defer()", "interaction", "defer"),
    ('interaction.response.send_message("h")', "interaction", "send_message"),
    ("interaction.response.send_modal(m)", "interaction", "send_modal"),
    # the name comes off the signature, nothing is hardcoded
    ("itx.response.defer()", "itx", "defer"),
    ("interaction.response.defer()", "itx", None),
    # followup only works after you already responded
    ('interaction.followup.send("h")', "interaction", None),
    ("interaction.response.pretend()", "interaction", None),
    ('db.execute("x")', "interaction", None),
    # left side is a call > dotted_name gives None > we stay quiet
    ("get_thing().response.defer()", "interaction", None),
])
def test_response_method(expr, param, expected):
    call = ast.parse(expr, mode="eval").body
    assert response_method(call, param) == expected
