"""
Smartcar webhook configuration helper.

This module provides utilities for setting up and registering webhooks
with Smartcar.
"""

import json
from typing import List, Dict
from pathlib import Path


class WebhookConfig:
    """Smartcar webhook configuration."""
    
    # Required signals for location tracking
    REQUIRED_SIGNALS = [
        'Location.Latitude',
        'Location.Longitude', 
        'Odometer.Odometer',
    ]
    
    # Recommended optional signals for additional data
    OPTIONAL_SIGNALS = [
        'Battery.StateOfCharge',
        'Fuel.Level',
        'Engine.Speed',
        'Drivetrain.Transmission.Speed',
    ]
    
    @staticmethod
    def get_setup_instructions(domain: str, port: int = 443) -> str:
        """
        Get instructions for setting up webhook in Smartcar Dashboard.
        
        Args:
            domain: Your public domain (e.g., tracker.example.com)
            port: HTTPS port (default 443)
            
        Returns:
            Formatted setup instructions
        """
        webhook_url = f"https://{domain}:{port}" if port != 443 else f"https://{domain}"
        
        return f"""
SMARTCAR WEBHOOK SETUP INSTRUCTIONS
====================================

1. Go to Smartcar Dashboard: https://dashboard.smartcar.com

2. Navigate to: Webhooks → Create Webhook

3. Configure the webhook:
   
   Webhook URL:
   {webhook_url}/webhooks/smartcar
   
   Event Type:
   VEHICLE_STATE
   
   Signals (REQUIRED):
   {chr(10).join(f'   ✓ {signal}' for signal in WebhookConfig.REQUIRED_SIGNALS)}
   
   Signals (OPTIONAL - for additional features):
   {chr(10).join(f'   ○ {signal}' for signal in WebhookConfig.OPTIONAL_SIGNALS)}

4. Get your Application Management Token from Smartcar Dashboard

5. Update your .env file:
    SMARTCAR_MANAGEMENT_TOKEN=<paste_token_here>
   WEBHOOK_HOST=0.0.0.0
   WEBHOOK_PORT=5000

6. Ensure:
   ✓ Server is publicly accessible
   ✓ HTTPS with valid certificate
   ✓ .env has valid Traccar credentials
   
7. Start webhook server:
   python webhooks/webhook_handler.py

8. Test webhook delivery:
   GET {webhook_url}/webhooks/health
   
   Should return 200 OK with status

9. Monitor webhook events:
   - Check logs from webhook_handler.py
   - View stats at: {webhook_url}/webhooks/stats
   - Monitor in Smartcar Dashboard → Webhook Logs
"""
    
    @staticmethod
    def validate_config(env_dict: Dict[str, str]) -> tuple:
        """
        Validate webhook configuration.
        
        Args:
            env_dict: Environment variables dict
            
        Returns:
            Tuple of (is_valid, missing_keys, warnings)
        """
        required = [
            'SMARTCAR_MANAGEMENT_TOKEN',
            'TRACCAR_API_URL',
            'TRACCAR_USERNAME',
            'TRACCAR_PASSWORD',
        ]
        
        missing = [key for key in required if not env_dict.get(key)]
        warnings = []
        
        if env_dict.get('WEBHOOK_HOST') == '127.0.0.1':
            warnings.append("WEBHOOK_HOST is localhost - webhook will not be reachable from internet")
        
        if not env_dict.get('WEBHOOK_PORT'):
            warnings.append("WEBHOOK_PORT not set, defaulting to 5000")
        
        is_valid = len(missing) == 0
        
        return is_valid, missing, warnings


def print_setup_guide(domain: str):
    """Print formatted setup guide."""
    print(WebhookConfig.get_setup_instructions(domain))


if __name__ == '__main__':
    import sys
    from dotenv import dotenv_values
    
    if len(sys.argv) > 1:
        domain = sys.argv[1]
    else:
        domain = input("Enter your public domain (e.g., tracker.example.com): ").strip()
    
    if not domain:
        print("❌ Domain required")
        sys.exit(1)
    
    # Print setup guide
    print_setup_guide(domain)
    
    # Validate current config
    print("\n\nCURRENT CONFIGURATION CHECK")
    print("=" * 70)
    
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        env_vars = dotenv_values(env_file)
        is_valid, missing, warnings = WebhookConfig.validate_config(env_vars)
        
        if missing:
            print(f"\n❌ Missing required variables:")
            for key in missing:
                print(f"   - {key}")
        
        if warnings:
            print(f"\n⚠️  Warnings:")
            for warning in warnings:
                print(f"   - {warning}")
        
        if is_valid and not warnings:
            print("✓ Configuration looks good!")
    else:
        print(f"⚠️  .env file not found at {env_file}")
        print("   Create it with required variables first")
