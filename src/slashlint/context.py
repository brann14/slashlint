# context.py

# imports

from __future__ import annotations
import ast
from dataclasses import dataclass
from pathlib import Path

from slashlint.patterns import COMMAND_DECORATOR_SUFFIXES, UI_CALLBACK_SUFFIXES, RESPONSE_METHODS, DEFER_METHOD

# utility & config

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef

# commandcontext dataclass
@dataclass(frozen=True)
class CommandContext:
    path: Path
    name: str
    lineno: int
    interaction_param: str
    calls: tuple[ast.Call, ...]
    first_response_index: int | None
    has_defer: bool
    
    # property to get calls before the first response
    @property
    def calls_before_response(self):
        if self.first_response_index is None:
            return ()
        return self.calls[:self.first_response_index]

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

def ordered_calls(func):
    found = []
    
    def visit (node):
        # nested functiion or lambda
        if isinstance(node, (FunctionNode, ast.Lambda)):
            return
        
        if isinstance(node, ast.Call):
            # append node to the founds list
            found.append(node)
            
        for child in ast.iter_child_nodes(node):
            visit(child)
            
    for stmt in func.body:
        visit(stmt)
        
    return found
            
def response_method(call, param):
    name = dotted_name(call.func)
    if name is None:
        return None
    
    # get the prefix of the command
    prefix = f"{param}.response."
    
    # check if the name starts with the prefix, if not return None
    if not name.startswith(prefix):
        return None
    
    # method
    method = name.rsplit(".", 1)[-1]
    
    if method in RESPONSE_METHODS:
        return method
    
    return None

