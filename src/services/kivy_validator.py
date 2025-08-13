# filepath: /kivy-discord-bot/kivy-discord-bot/src/services/kivy_validator.py

def validate_kivy_code(code: str) -> bool:
    """
    Validates Kivy code snippets to ensure they are safe to execute.
    This function checks for potentially dangerous operations and ensures
    that the code adheres to Kivy's expected structure.
    """
    dangerous_patterns = [
        'import os',
        'import subprocess',
        'import sys',
        '__import__',
        'eval(',
        'exec(',
        'open(',
        'file(',
        'input(',
        'raw_input(',
    ]
    
    code_lower = code.lower()
    for pattern in dangerous_patterns:
        if pattern in code_lower:
            return False
    
    # Additional checks can be added here to ensure Kivy-specific imports
    if not any(keyword in code_lower for keyword in ['from kivy.', 'import kivy']):
        return False
    
    return True