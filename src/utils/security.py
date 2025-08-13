# filepath: /kivy-discord-bot/kivy-discord-bot/src/utils/security.py
def validate_code(code: str) -> bool:
    """Basic validation to prevent malicious code execution"""
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
    return True

def sanitize_input(user_input: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    # Basic sanitization: remove potentially dangerous characters
    sanitized = user_input.replace(";", "").replace("&", "").replace("|", "")
    return sanitized.strip()