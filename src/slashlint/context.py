# context.py

# imports

from __future__ import annotations
import ast
from dataclasses import dataclass
from pathlib import Path

from slashlint.patterns import COMMAND_DECORATOR_SUFFIXES, UI_CALLBACK_SUFFIXES

# utility & config

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef

# main logic

def dotted_name(node):
    # case a: it's just a plain word.
    if isinstance(node, ast.Name):
        return node.id
    
    # case b: it's a dotted name
    if isinstance(node, ast.Attribute):
        left = dotted_name(node.value)
        if left is None:
            return None
        return f"{left}.{node.attr}"
        
    # case c: basically something we don't handle
    return None

def decorator_names(func):
    names = []
    for d in func.decorator_list:
        # if there were parentehes, step one level in
        if isinstance(d, ast.Call):
            d = d.func
            
        name = dotted_name(d) # just passed the name to the dotted_name function
            
        if name is not None:
            names.append(name) # if the name is not None, append it to the names list
                
    return names
        
def is_slash_command(func):
    # full names > last piece of each
    last_parts = [name.rsplit(".", 1)[-1] for name in decorator_names(func)]
    
    # reject if it's a ui callback command
    if any(p in UI_CALLBACK_SUFFIXES for p in last_parts):
        return False
    
    # accept any decorator that looks like a command decorator
    if any(p in COMMAND_DECORATOR_SUFFIXES for p in last_parts):
        return True

    return False

def interaction_param(func):
    args = func.args.args # box of args
    
    # no parameters > something we do not understand and do not handle
    if not args:
        return None
    
    # method: skip past self/cls and take the next one
    if args[0].arg in ("self", "cls"):
        if len(args) < 2:
            return None
        return args[1].arg
    
    # plain function, the first parametar in the interaction
    return args[0].arg

# rest to be made