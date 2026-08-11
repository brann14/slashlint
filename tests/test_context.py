# test_context.py

# imports

import ast
from pathlib import Path

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

def summary(src):
    # build_context > (has_defer, first_response_index, names before the response)
    ctx = build_context(Path("bot.py"), parse_func(src))
    if ctx is None:
        return None
    return (ctx.has_defer, ctx.first_response_index,
            [dotted_name(c.func) for c in ctx.calls_before_response])

def test_build_context_io_before_response():
    # the SL001 shape > no defer, two io calls before the response
    assert summary('''
@app_commands.command()
async def ban(self, interaction, member):
    case = await db.execute("insert ...")
    await member.add_roles(role)
    await interaction.response.send_message(f"done {case}")
''') == (False, 2, ["db.execute", "member.add_roles"])

def test_build_context_defers_first():
    assert summary('''
@app_commands.command()
async def ban(self, interaction, member):
    await interaction.response.defer()
    await db.execute("insert ...")
''') == (True, 0, [])

def test_build_context_late_defer():
    # defer after io > has_defer is still True, so sl001 stays quiet
    assert summary('''
@app_commands.command()
async def ban(self, interaction, member):
    await db.execute("x")
    await interaction.response.defer()
''') == (True, 1, ["db.execute"])

def test_build_context_never_responds():
    # no response at all > index None > empty slice, not everything
    assert summary('''
@app_commands.command()
async def ban(self, interaction, member):
    await db.execute("x")
''') == (False, None, [])

def test_build_context_first_response_wins():
    # break in the loop > first response, not last
    assert summary('''
@app_commands.command()
async def ban(self, interaction, member):
    await interaction.response.defer()
    await db.execute("x")
    await interaction.response.send_message("hi")
''') == (True, 0, [])

def test_build_context_custom_param_name():
    assert summary('''
@app_commands.command()
async def ban(self, itx, member):
    await db.execute("x")
    await itx.response.defer()
''') == (True, 1, ["db.execute"])

def test_build_context_rejects_ui_callback():
    assert summary('''
@discord.ui.button(label="Ban")
async def ban(self, interaction, button):
    await db.execute("x")
    await interaction.response.send_message("ok")
''') is None

def test_build_context_rejects_unknown_signature():
    assert summary('''
@app_commands.command()
async def ban(self):
    await db.execute("x")
''') is None

def test_build_context_fields():
    ctx = build_context(Path("bot.py"), parse_func('''
@app_commands.command()
async def ban(self, interaction, member):
    await interaction.response.defer()
'''))
    assert ctx.path == Path("bot.py")
    assert ctx.name == "ban"
    # lineno points at the def, not the decorator
    assert ctx.lineno == 3
    assert ctx.interaction_param == "interaction"

# a realistic module > cog commands, a module level one, a group one,
# a view whose button callback shares a name with a real command
MODULE = '''
import discord
from discord import app_commands
from discord.ext import commands

def helper(x):
    return db.execute(x)

@app_commands.command()
async def ping(interaction):
    await interaction.response.send_message("pong")

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ban")
    @app_commands.describe(member="who")
    async def ban(self, interaction, member):
        case = await self.db.execute("insert ...")
        await member.add_roles(self.muted)
        await interaction.response.send_message(f"#{case}")

    @app_commands.command()
    async def warn(self, itx, member):
        await itx.response.defer()
        await self.db.execute("insert ...")

class ConfirmView(discord.ui.View):
    @discord.ui.button(label="Confirm")
    async def ban(self, interaction, button):
        await self.db.execute("insert ...")
        await interaction.response.send_message("ok")

group = app_commands.Group(name="cfg", description="")

@group.command()
async def show(interaction):
    await api.fetch_settings()
    await interaction.response.send_message("x")
'''

def module_contexts():
    return contexts_from_module(Path("bot.py"), ast.parse(MODULE))

def test_contexts_from_module_finds_commands_in_cogs():
    # tree.body would only see the top level and miss the cog methods
    assert sorted(c.name for c in module_contexts()) == ["ban", "ping", "show", "warn"]

def test_contexts_from_module_skips_helpers_and_init():
    names = [c.name for c in module_contexts()]
    assert "helper" not in names
    assert "__init__" not in names

def test_contexts_from_module_excludes_ui_callback_sharing_a_name():
    # the view has a button callback also called ban, only the command survives
    ctxs = module_contexts()
    assert [c.name for c in ctxs].count("ban") == 1
    ban = next(c for c in ctxs if c.name == "ban")
    assert [dotted_name(x.func) for x in ban.calls_before_response] == [
        "self.db.execute",
        "member.add_roles",
    ]

def test_contexts_from_module_empty():
    assert contexts_from_module(Path("bot.py"), ast.parse("x = 1\n")) == []
