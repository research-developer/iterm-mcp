#!/usr/bin/env python3
"""
Fix function parameter ordering in the MCP server implementation.

This script ensures that all Context parameters appear before any parameters
with default values in all functions in the mcp_server.py file.
"""

import re
from pathlib import Path

def main():
    """Fix function parameter ordering."""
    # Path to the mcp_server.py file
    file_path = Path("iterm_mcp_python/server/mcp_server.py")
    
    # Read the file
    with open(file_path, "r") as f:
        content = f.read()
    
    # Find all function definitions with issues
    # Pattern to detect: optional parameter followed by ctx: Context
    # function_pattern = r"@self\.mcp\.tool\(\)[^{]*?def\s+([^(]+)\(([^)]+)\)"
    function_pattern = r"(async def [a-zA-Z0-9_]+\(\s*.*?=.*?,\s*ctx: Context)"
    
    # Find all matches
    matches = re.finditer(function_pattern, content, re.DOTALL)
    
    # Process each match
    modified_content = content
    for match in matches:
        full_match = match.group(0)
        
        # Split the parameters
        params_text = full_match.split('(', 1)[1]
        
        # Parse parameters
        params = []
        in_default = False
        current_param = ""
        level = 0
        
        for char in params_text:
            if char == '(':
                level += 1
                current_param += char
            elif char == ')':
                level -= 1
                current_param += char
            elif char == ',' and level == 0:
                params.append(current_param.strip())
                current_param = ""
            else:
                current_param += char
        
        if current_param:
            params.append(current_param.strip())
        
        # Split each parameter into name and type/default
        parsed_params = []
        for p in params:
            if ':' in p:
                name, type_info = p.split(':', 1)
                parsed_params.append((name.strip(), type_info.strip()))
            else:
                parsed_params.append((p.strip(), ""))
        
        # Find ctx parameter and non-default parameters
        ctx_param = None
        default_params = []
        non_default_params = []
        
        for name, type_info in parsed_params:
            if name == "ctx" and "Context" in type_info:
                ctx_param = (name, type_info)
            elif "=" in type_info:
                default_params.append((name, type_info))
            else:
                non_default_params.append((name, type_info))
        
        # Reorder: non-default params, ctx param, default params
        new_params = non_default_params.copy()
        if ctx_param:
            new_params.append(ctx_param)
        new_params.extend(default_params)
        
        # Rebuild the parameter string
        new_params_text = ", ".join([f"{name}: {type_info}" if type_info else name for name, type_info in new_params])
        
        # Replace in the original content
        func_def = full_match.split('(', 1)[0]
        new_func_def = f"{func_def}({new_params_text}"
        modified_content = modified_content.replace(full_match, new_func_def)
    
    # Write the modified content back to the file
    with open(file_path, "w") as f:
        f.write(modified_content)
    
    print(f"Fixed parameter ordering in {file_path}")

if __name__ == "__main__":
    main()