# slashlint

Static analyzer for [discord.py](https://github.com/Rapptz/discord.py) bots. Finds slash commands that will time out before they respond.

> **Status: early development.** The command-detection layer works; the SL001 rule and CLI are not built yet. Not usable as a linter today.

## The problem

Discord invalidates an interaction **3 seconds** after it is created. A command that runs a database query or a Discord REST call before calling `interaction.response.defer()` will blow that budget:

```python
@app_commands.command()
async def ban(self, interaction: discord.Interaction, member: discord.Member):
    case_id = await self.db.execute(...)      # 400ms
    await member.ban(reason=...)              # 700ms
    await interaction.response.send_message(  # too late, sometimes
        f"Banned. Case #{case_id}"
    )
```

The work succeeds. The user sees *"The application did not respond"*, assumes it failed, and runs the command again — producing a duplicate infraction, a double role assignment, a second payout.

The fix is one line (`await interaction.response.defer()` first). Every tutorial says to remember it. Nothing checks whether you did.

## Rules

| Code | Description |
| --- | --- |
| `SL001` | I/O performed before the first interaction response, with no `defer()` anywhere in the command. |

## Design notes

**Detection is name-based, not type-based.** Python types are not statically resolvable, so slashlint matches against dotted call names (`.execute`, `.add_roles`, `requests.*`, `.fetch_*`). Patterns live in `patterns.py` as plain data.

**Biased toward false negatives.** A false positive gets the tool uninstalled; a missed detection costs nothing. When a signature or call is unrecognized, slashlint stays silent rather than guessing. Generic verbs like `get`, `post`, and `edit` are deliberately excluded from the I/O table.

**UI callbacks are explicitly rejected.** `@discord.ui.button` and `@discord.ui.select` callbacks share the `(self, interaction, ...)` signature of a slash command and frequently share its name. They are not commands and are never reported.

**Source order is computed, not assumed.** `ast.walk` is breadth-first and does not yield calls in source order; slashlint uses its own pre-order traversal, which also lets it skip nested function bodies that do not execute before the response.

## Install

```bash
git clone https://github.com/brann14/slashlint
cd slashlint
pip install -e ".[dev]"
```

Python 3.11+. No runtime dependencies — the core is stdlib only (`ast`, `argparse`).

## Usage

```bash
slashlint path/to/bot
```

Exits `1` when findings are reported, `0` when clean.

## Development

```bash
pytest
```

Fixtures under `tests/fixtures/` are parsed as input and never imported. Each defective fixture carries exactly one known defect and is paired with a clean counterpart that must produce no findings.

## License

MIT
