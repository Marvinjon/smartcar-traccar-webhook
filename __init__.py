"""
Smartcar Webhooks Package

Real-time vehicle location updates using event-driven webhooks.
"""

__version__ = "1.0.0"
__author__ = "Traccar"

from .webhook_processor import WebhookProcessor
from .webhook_validator import validate_signature, extract_event_data
from .webhook_config import WebhookConfig

__all__ = [
    'WebhookProcessor',
    'validate_signature', 
    'extract_event_data',
    'WebhookConfig',
]
