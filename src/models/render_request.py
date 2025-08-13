from dataclasses import dataclass
from typing import Any

@dataclass
class RenderRequest:
    """Data structure for rendering requests."""
    user_id: int
    channel_id: int
    code: str
    request_time: Any  # Can be a timestamp or datetime object
    status: str  # e.g., 'pending', 'in_progress', 'completed', 'failed'
    result: Any = None  # To store the result of the rendering, if applicable
    error_message: str = ""  # To store any error messages if rendering fails