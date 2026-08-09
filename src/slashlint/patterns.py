# patterns.py 
# just pure data, no logic

# last segment of a decorator names
COMMAND_DECORATOR_SUFFIXES = (
    "command",
    "hybrid_command"
)

# last segment that means "this is a ui callback"
UI_CALLBACK_SUFFIXES = (
    "button",
    "select",
    "modal",
    "user_select",
    "role_select",
    "channel_select",
    "mentionable_select",
)

# methods on <interaction>.response that consume the initial interaction token
RESPONSE_METHODS = (
    "defer",
    "send_message",
    "send_modal",
    "edit_message",
    "pong",
)

DEFER_METHOD = "defer"