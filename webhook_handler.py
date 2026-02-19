"""
Flask webhook server for receiving Smartcar real-time vehicle data.

Usage:
    python webhook_handler.py
    
Then register this endpoint in Smartcar Dashboard:
    https://your-domain.com/webhooks/smartcar
"""

import sys
import json
import os
from pathlib import Path
from dotenv import load_dotenv
import logging

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("❌ Flask is required. Install with: pip install flask")
    sys.exit(1)

try:
    import smartcar
except ImportError:
    print("❌ smartcar SDK is required. Install with: pip install smartcar")
    sys.exit(1)

from webhook_validator import validate_signature, extract_event_data
from webhook_processor import WebhookProcessor


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

# Initialize Flask app
app = Flask(__name__)

# Initialize webhook processor
processor = WebhookProcessor()


def get_management_token(integration_name: str = None) -> str:
    """
    Get the management token for a given integration.
    
    Args:
        integration_name: Optional integration name (e.g., 'fleet2').
                         If None, uses the default SMARTCAR_MANAGEMENT_TOKEN.
    
    Returns:
        The management token string, or None if not configured.
    """
    if integration_name:
        # Try SMARTCAR_MANAGEMENT_TOKEN_<NAME> (case-insensitive lookup)
        token = os.getenv(f'SMARTCAR_MANAGEMENT_TOKEN_{integration_name.upper()}')
        if token:
            return token
        logger.error(f"❌ No management token configured for integration '{integration_name}'")
        logger.error(f"   Set SMARTCAR_MANAGEMENT_TOKEN_{integration_name.upper()} in your .env")
        return None
    return os.getenv('SMARTCAR_MANAGEMENT_TOKEN')


def handle_verification(payload, integration_name=None):
    """
    Handle Smartcar webhook verification challenge.
    
    Smartcar sends a VERIFY event with a challenge string.
    We must respond with an HMAC signature of the challenge.
    """
    try:
        management_token = get_management_token(integration_name)
        
        if not management_token:
            logger.error("❌ Management token not configured")
            return jsonify({"error": "Management token not configured"}), 500
        
        data = payload.get('data', {})
        challenge = data.get('challenge')
        
        if not challenge:
            logger.error("❌ No challenge in verification payload")
            return jsonify({"error": "Missing challenge"}), 400
        
        # Generate signature using Smartcar SDK
        hmac_signature = smartcar.hash_challenge(management_token, challenge)
        integration_label = f" ({integration_name})" if integration_name else ""
        logger.info(f"✓ Webhook verification successful{integration_label}")
        
        return jsonify({'challenge': hmac_signature}), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook verification error: {e}")
        return jsonify({"error": "Verification failed"}), 500


def _handle_webhook(integration_name=None):
    """
    Core webhook handler logic, shared by all integration routes.
    
    Args:
        integration_name: Optional integration name for multi-webhook support.
    """
    try:
        # Parse JSON
        try:
            payload = json.loads(request.get_data(as_text=True))
        except json.JSONDecodeError:
            logger.error("❌ Invalid JSON payload")
            return jsonify({"error": "Invalid JSON"}), 400
        
        if not payload:
            logger.error("❌ Empty payload")
            return jsonify({"error": "Empty payload"}), 400
        
        event_type = payload.get('eventType')
        integration_label = f" [{integration_name}]" if integration_name else ""
        logger.info(f"Webhook received: {event_type}{integration_label}")
        
        # Handle verification challenge
        if event_type == 'VERIFY':
            return handle_verification(payload, integration_name)
        
        # Handle vehicle state updates
        if event_type == 'VEHICLE_STATE':
            # Validate signature for all webhooks (including TEST mode)
            raw_payload = request.get_data(as_text=True)
            signature = request.headers.get('SC-Signature')
            webhook_secret = get_management_token(integration_name)
            
            if not webhook_secret:
                logger.error(f"❌ Management token not configured{integration_label}")
                return jsonify({"error": "Management token not configured"}), 500
            
            if not validate_signature(raw_payload, signature, webhook_secret):
                logger.warning(f"❌ Invalid webhook signature{integration_label}: {signature[:20] if signature else 'None'}...")
                return jsonify({"error": "Invalid signature"}), 401
            
            # Extract event data
            event_id, vehicle_id, signals = extract_event_data(payload)
            
            if not event_id or not vehicle_id:
                logger.error("❌ Missing event ID or vehicle ID")
                return jsonify({"error": "Missing required fields"}), 400
            
            # Process webhook
            success = processor.process_webhook(payload)
            logger.info(f"✓ Processed vehicle state for {vehicle_id}{integration_label}")
        
        elif event_type == 'VEHICLE_ERROR':
            logger.warning(f"Vehicle error received{integration_label}: {payload}")
        
        else:
            logger.warning(f"Unknown event type: {event_type}{integration_label}")
        
        # Always return 200 immediately
        # This prevents Smartcar from retrying
        return jsonify({"status": "received"}), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook handler error{integration_label}: {e}")
        return jsonify({"status": "received"}), 200


@app.route('/webhooks/smartcar', methods=['POST'])
def handle_smartcar_webhook():
    """Handle incoming Smartcar webhooks (default integration)."""
    return _handle_webhook()


@app.route('/webhooks/smartcar/<integration_name>', methods=['POST'])
def handle_smartcar_webhook_named(integration_name):
    """Handle incoming Smartcar webhooks for a named integration."""
    return _handle_webhook(integration_name)


@app.route('/webhooks/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({"status": "ok", "service": "smartcar-webhook"}), 200


@app.route('/webhooks/stats', methods=['GET'])
def webhook_stats():
    """Get webhook processing statistics."""
    stats = {
        "processed_events": len(processor.processed_events),
        "traccar_authenticated": processor.traccar.authenticated,
    }
    return jsonify(stats), 200


if __name__ == '__main__':
    # Get configuration from environment
    host = os.getenv('WEBHOOK_HOST', '0.0.0.0')
    port = int(os.getenv('WEBHOOK_PORT', '5000'))
    debug = os.getenv('WEBHOOK_DEBUG', 'false').lower() == 'true'
    
    # Check for required environment variables
    required_vars = ['SMARTCAR_MANAGEMENT_TOKEN', 'TRACCAR_API_URL', 'TRACCAR_USERNAME', 'TRACCAR_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        sys.exit(1)
    
    if debug:
        print("""
╔════════════════════════════════════════════════════════════════╗
║         Smartcar Webhook Server Running (DEBUG MODE)           ║
╠════════════════════════════════════════════════════════════════╣
║ ⚠️  WARNING: Debug mode is ON - NOT suitable for production    ║
╚════════════════════════════════════════════════════════════════╝
        """)
    else:
        print("""
╔════════════════════════════════════════════════════════════════╗
║         Smartcar Webhook Server Running (PRODUCTION)           ║
╠════════════════════════════════════════════════════════════════╣
║ Server: http://{host}:{port}                                    
║ Webhook endpoint: POST /webhooks/smartcar                      
║ Health check: GET /webhooks/health                             
║ Statistics: GET /webhooks/stats                                
╚════════════════════════════════════════════════════════════════╝
        """.format(host=host, port=port))
    
    if not os.getenv('SMARTCAR_MANAGEMENT_TOKEN'):
        print("❌ WARNING: SMARTCAR_MANAGEMENT_TOKEN not set")
        print("   Webhook signature validation will FAIL\n")
    
    app.run(host=host, port=port, debug=debug)
