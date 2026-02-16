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


def handle_verification(payload):
    """
    Handle Smartcar webhook verification challenge.
    
    Smartcar sends a VERIFY event with a challenge string.
    We must respond with an HMAC signature of the challenge.
    """
    try:
        management_token = os.getenv('SMARTCAR_MANAGEMENT_TOKEN')
        
        if not management_token:
            logger.error("❌ SMARTCAR_MANAGEMENT_TOKEN not configured")
            return jsonify({"error": "Management token not configured"}), 500
        
        data = payload.get('data', {})
        challenge = data.get('challenge')
        
        if not challenge:
            logger.error("❌ No challenge in verification payload")
            return jsonify({"error": "Missing challenge"}), 400
        
        # Generate signature using Smartcar SDK
        hmac_signature = smartcar.hash_challenge(management_token, challenge)
        logger.info(f"✓ Webhook verification successful")
        
        return jsonify({'challenge': hmac_signature}), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook verification error: {e}")
        return jsonify({"error": "Verification failed"}), 500


@app.route('/webhooks/smartcar', methods=['POST'])
def handle_smartcar_webhook():
    """
    Handle incoming Smartcar webhooks.
    
    Handles VERIFY events for webhook validation and VEHICLE_STATE events
    for location updates. Returns immediately (200 OK).
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
        logger.info(f"Webhook received: {event_type}")
        
        # Handle verification challenge
        if event_type == 'VERIFY':
            return handle_verification(payload)
        
        # Handle vehicle state updates
        if event_type == 'VEHICLE_STATE':
            # Check if this is a test webhook (skip signature validation for tests)
            is_test_mode = payload.get('meta', {}).get('mode') == 'TEST'
            
            if not is_test_mode:
                # Validate signature for production webhooks only
                raw_payload = request.get_data(as_text=True)
                signature = request.headers.get('SC-Signature')
                webhook_secret = os.getenv('SMARTCAR_WEBHOOK_SECRET')
                
                if not webhook_secret:
                    logger.error("❌ SMARTCAR_WEBHOOK_SECRET not configured")
                    return jsonify({"error": "Webhook secret not configured"}), 500
                
                if not validate_signature(raw_payload, signature, webhook_secret):
                    logger.warning(f"❌ Invalid webhook signature: {signature[:20] if signature else 'None'}...")
                    return jsonify({"error": "Invalid signature"}), 401
            else:
                logger.info("ℹ️  Skipping signature validation for TEST webhook")
            
            # Extract event data
            event_id, vehicle_id, signals = extract_event_data(payload)
            
            if not event_id or not vehicle_id:
                logger.error("❌ Missing event ID or vehicle ID")
                return jsonify({"error": "Missing required fields"}), 400
            
            # Process webhook asynchronously
            success = processor.process_webhook(payload)
            logger.info(f"✓ Processed vehicle state for {vehicle_id}")
        
        elif event_type == 'VEHICLE_ERROR':
            logger.warning(f"Vehicle error received: {payload}")
        
        else:
            logger.warning(f"Unknown event type: {event_type}")
        
        # Always return 200 immediately
        # This prevents Smartcar from retrying
        return jsonify({"status": "received"}), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook handler error: {e}")
        return jsonify({"status": "received"}), 200


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
    required_vars = ['SMARTCAR_WEBHOOK_SECRET', 'TRACCAR_API_URL', 'TRACCAR_USERNAME', 'TRACCAR_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        sys.exit(1)
    
    if debug:
        print("""
╔════════════════════════════════════════════════════════════════╗
║         Smartcar Webhook Server Running (DEBUG MODE)          ║
╠════════════════════════════════════════════════════════════════╣
║ ⚠️  WARNING: Debug mode is ON - NOT suitable for production   ║
╚════════════════════════════════════════════════════════════════╝
        """)
    else:
        print("""
╔════════════════════════════════════════════════════════════════╗
║         Smartcar Webhook Server Running (PRODUCTION)          ║
╠════════════════════════════════════════════════════════════════╣
║ Server: http://{host}:{port}                                    
║ Webhook endpoint: POST /webhooks/smartcar                      
║ Health check: GET /webhooks/health                             
║ Statistics: GET /webhooks/stats                                
╚════════════════════════════════════════════════════════════════╝
        """.format(host=host, port=port))
    
    if not os.getenv('SMARTCAR_WEBHOOK_SECRET'):
        print("❌ WARNING: SMARTCAR_WEBHOOK_SECRET not set")
        print("   Webhook signature validation will FAIL\n")
    
    app.run(host=host, port=port, debug=debug)
