"""
Webhook signature validation for Smartcar webhooks.

Validates SC-Signature header using HMAC-SHA256.
"""

import hmac
import hashlib
import json
import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def validate_signature(payload: str, signature: str, secret: str) -> bool:
    """
    Validate Smartcar webhook signature.
    
    Args:
        payload: Raw request body as string
        signature: SC-Signature header value
        secret: Webhook secret from Smartcar Dashboard
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not payload or not signature or not secret:
        return False
    
    try:
        # HMAC-SHA256 of payload using webhook secret
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        debug_signatures = os.getenv('SMARTCAR_DEBUG_SIGNATURE', '').lower() == 'true'
        if debug_signatures:
            logger.warning(
                "Signature debug: expected=%s received=%s payload_bytes=%s",
                expected_signature,
                signature,
                len(payload)
            )
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        print(f"❌ Signature validation error: {e}")
        return False


def extract_event_data(payload: dict) -> Tuple[str, str, dict]:
    """
    Extract event ID, vehicle ID, and signals from webhook payload.
    
    Args:
        payload: Parsed JSON webhook payload
        
    Returns:
        Tuple of (eventId, vehicleId, signals_dict)
    """
    try:
        event_id = payload.get('eventId')
        vehicle_id = payload['data']['vehicle']['id']
        signals = payload.get('data', {}).get('signals', {})
        
        return event_id, vehicle_id, signals
    except (KeyError, TypeError) as e:
        print(f"❌ Error extracting event data: {e}")
        return None, None, {}
