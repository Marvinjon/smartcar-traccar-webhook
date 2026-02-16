#!/usr/bin/env python3
"""
Quick setup script for Smartcar webhooks.

Interactive guide to configure and test the webhook integration.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv, dotenv_values

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from webhooks.webhook_config import WebhookConfig
from traccar_client import TraccarClient


def print_header(text):
    """Print formatted header."""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}\n")


def check_requirements():
    """Check if required packages are installed."""
    print_header("1. Checking Requirements")
    
    required = {
        'flask': 'Flask',
        'dotenv': 'python-dotenv',
        'requests': 'requests',
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
            print(f"✓ {package}")
        except ImportError:
            print(f"❌ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Install missing packages:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    return True


def check_env_config():
    """Check .env configuration."""
    print_header("2. Checking Configuration")
    
    env_file = Path(__file__).parent.parent / '.env'
    
    if not env_file.exists():
        print(f"❌ .env file not found at {env_file}")
        print("\n   Create it from .env.example:")
        print(f"   cp .env.example .env")
        return False
    
    env_vars = dotenv_values(env_file)
    
    # Check webhook config
    webhook_secret = env_vars.get('SMARTCAR_WEBHOOK_SECRET')
    if not webhook_secret or webhook_secret == 'your_webhook_secret_from_dashboard':
        print("⚠️  SMARTCAR_WEBHOOK_SECRET not configured")
        print("   Get this from Smartcar Dashboard after creating webhook")
    else:
        print(f"✓ SMARTCAR_WEBHOOK_SECRET configured")
    
    # Check Traccar config
    required_traccar = ['TRACCAR_API_URL', 'TRACCAR_USERNAME', 'TRACCAR_PASSWORD']
    missing_traccar = [k for k in required_traccar if not env_vars.get(k)]
    
    if missing_traccar:
        print(f"❌ Missing Traccar config: {', '.join(missing_traccar)}")
        return False
    else:
        print(f"✓ Traccar credentials configured")
    
    # Check webhook server config
    webhook_host = env_vars.get('WEBHOOK_HOST', '0.0.0.0')
    webhook_port = env_vars.get('WEBHOOK_PORT', '5000')
    print(f"✓ Webhook server: {webhook_host}:{webhook_port}")
    
    if webhook_host == '127.0.0.1':
        print("⚠️  WARNING: WEBHOOK_HOST is localhost")
        print("   Smartcar cannot reach localhost - use public IP/domain")
        return False
    
    return bool(webhook_secret) and webhook_secret != 'your_webhook_secret_from_dashboard'


def check_traccar_connection():
    """Test Traccar API connection."""
    print_header("3. Testing Traccar Connection")
    
    try:
        tc = TraccarClient()
        
        if tc.authenticated:
            print("✓ Traccar authentication successful")
            devices = tc.get_devices()
            print(f"✓ Found {len(devices)} devices in Traccar")
            return True
        else:
            print("❌ Traccar authentication failed")
            print("   Check TRACCAR_USERNAME and TRACCAR_PASSWORD in .env")
            return False
            
    except Exception as e:
        print(f"❌ Traccar connection error: {e}")
        return False


def get_domain():
    """Get domain from user."""
    print_header("4. Webhook Domain Configuration")
    
    print("What is your public domain for the webhook?")
    print("Examples: tracker.example.com, 192.168.1.100, webhook.example.dev")
    print()
    
    domain = input("Domain (or press Enter to skip): ").strip()
    return domain if domain else None


def print_setup_guide(domain):
    """Print detailed setup guide."""
    if not domain:
        return
    
    print_header("5. Smartcar Dashboard Setup")
    print(WebhookConfig.get_setup_instructions(domain))


def print_next_steps():
    """Print next steps."""
    print_header("Next Steps")
    
    print("""
1. Get webhook secret from Smartcar Dashboard:
   - Go to https://dashboard.smartcar.com
   - Create a new webhook
   - Copy the Secret shown

2. Update .env with the secret:
   SMARTCAR_WEBHOOK_SECRET=<paste_here>

3. Install Flask:
   pip install flask

4. Start the webhook server:
   python webhooks/webhook_handler.py

5. Test the endpoints:
   curl https://your-domain.com/webhooks/health
   curl https://your-domain.com/webhooks/stats

6. Monitor logs:
   tail -f webhook_dedup.json

For detailed documentation, see: webhooks/README.md
    """)


def main():
    """Run interactive setup."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  Smartcar Webhooks - Interactive Setup Wizard".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    
    # Run checks
    if not check_requirements():
        print("\n❌ Please install missing packages and try again")
        return 1
    
    if not check_env_config():
        print("\n❌ Please configure .env file and try again")
        print("   Copy .env.example to .env and fill in your credentials")
        return 1
    
    if not check_traccar_connection():
        print("\n⚠️  Traccar connection failed")
        print("   Make sure Traccar credentials in .env are correct")
        # Don't exit, user might still want to continue
    
    # Get domain and print guide
    domain = get_domain()
    if domain:
        print_setup_guide(domain)
    
    print_next_steps()
    
    print("\n✓ Setup wizard complete!\n")
    return 0


if __name__ == '__main__':
    sys.exit(main())
