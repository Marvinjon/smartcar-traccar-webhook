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


@app.route('/webhooks/smartcar', methods=['POST'])
def handle_smartcar_webhook():
    """
    Handle incoming Smartcar webhooks.
    
    Validates signature, deduplicates events, and processes location updates.
    Returns immediately (200 OK) and processes asynchronously.
    """
    try:
        # Get raw body for signature verification
        raw_payload = request.get_data(as_text=True)
        signature = request.headers.get('SC-Signature')
        webhook_secret = os.getenv('SMARTCAR_WEBHOOK_SECRET')
        
        # Validate signature
        if not webhook_secret:
            logger.error("❌ SMARTCAR_WEBHOOK_SECRET not configured")
            return jsonify({"error": "Webhook secret not configured"}), 500
        
        if not validate_signature(raw_payload, signature, webhook_secret):
            logger.warning(f"❌ Invalid webhook signature: {signature[:20]}...")
            return jsonify({"error": "Invalid signature"}), 401
        
        # Parse JSON
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.error("❌ Invalid JSON payload")
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Extract event data
        event_id, vehicle_id, signals = extract_event_data(payload)
        
        if not event_id or not vehicle_id:
            logger.error("❌ Missing event ID or vehicle ID")
            return jsonify({"error": "Missing required fields"}), 400
        
        # Process webhook asynchronously
        # In production, you might want to queue this to a background worker
        success = processor.process_webhook(payload)
        
        # Always return 200 immediately, even if processing fails
        # This prevents Smartcar from retrying
        return jsonify({"status": "received"}), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook handler error: {e}")
        # Return 200 anyway to prevent retries on our end
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
    
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║         Smartcar Webhook Server Running                       ║
╠════════════════════════════════════════════════════════════════╣
║ Server: http://{host}:{port}                                    
║ Webhook endpoint: POST /webhooks/smartcar                      
║ Health check: GET /webhooks/health                             
║ Statistics: GET /webhooks/stats                                
╚════════════════════════════════════════════════════════════════╝

⚠️  Important Setup Steps:
1. Ensure this server is accessible from the internet (public IP/domain)
2. Configure HTTPS with a valid SSL certificate
3. Get webhook secret from Smartcar Dashboard
4. Set SMARTCAR_WEBHOOK_SECRET in .env
5. Register webhook in Dashboard: https://your-domain.com/webhooks/smartcar
6. Subscribe to VEHICLE_STATE events with these signals:
   - Location.Latitude
   - Location.Longitude
   - Odometer.Odometer
    """)
    
    if not os.getenv('SMARTCAR_WEBHOOK_SECRET'):
        print("❌ WARNING: SMARTCAR_WEBHOOK_SECRET not set in .env")
        print("   Webhook signature validation will FAIL\n")
    
    app.run(host=host, port=port, debug=debug)
