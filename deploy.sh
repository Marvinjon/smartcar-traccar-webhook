#!/bin/bash

# Smartcar Webhook Server - Deployment Script
# Run this script on your Ubuntu server to set up the service

set -e  # Exit on error

echo "🚀 Smartcar Webhook Server - Deployment Setup"
echo "=============================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "❌ Please do NOT run this script as root"
   exit 1
fi

PROJECT_DIR=$(pwd)
VENV_DIR="$PROJECT_DIR/venv"

echo "📁 Project directory: $PROJECT_DIR"
echo ""

# Step 1: Virtual environment
echo "Step 1: Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

source "$VENV_DIR/bin/activate"

# Step 2: Install dependencies
echo ""
echo "Step 2: Installing Python dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
echo "✓ Dependencies installed"

# Step 3: Check .env file
echo ""
echo "Step 3: Checking configuration..."
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found"
    echo "   Copy .env.example to .env and fill in your credentials"
    echo "   cp .env.example .env"
    exit 1
fi

# Verify required variables
REQUIRED_VARS=("SMARTCAR_WEBHOOK_SECRET" "TRACCAR_API_URL" "TRACCAR_USERNAME" "TRACCAR_PASSWORD")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" .env; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "❌ ERROR: Missing required variables in .env:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    exit 1
fi

echo "✓ Configuration looks good"

# Step 4: Test connection
echo ""
echo "Step 4: Testing connections..."
python -c "
import os
from dotenv import load_dotenv
from traccar_client import TraccarClient
load_dotenv()
client = TraccarClient()
if client.authenticated:
    print('✓ Traccar connection successful')
else:
    print('❌ Traccar connection failed')
    exit(1)
" || exit 1

# Step 5: Systemd service setup
echo ""
echo "Step 5: Setting up systemd service..."
echo ""
echo "⚠️  This requires sudo access. The following commands will be run:"
echo ""
echo "1. Create log directory:"
echo "   sudo mkdir -p /var/log/smartcar-webhook"
echo "   sudo chown www-data:www-data /var/log/smartcar-webhook"
echo ""
echo "2. Install systemd service:"
echo "   sudo cp smartcar-webhook.service /etc/systemd/system/"
echo ""
echo "3. Edit service file with your paths"
echo "4. Enable and start service:"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable smartcar-webhook"
echo "   sudo systemctl start smartcar-webhook"
echo ""
echo "Continue? (y/n)"
read -r response

if [ "$response" = "y" ]; then
    sudo mkdir -p /var/log/smartcar-webhook
    sudo chown www-data:www-data /var/log/smartcar-webhook
    echo "✓ Log directory created"
    
    sudo cp smartcar-webhook.service /etc/systemd/system/
    echo "✓ Service file installed"
    
    echo ""
    echo "⚠️  IMPORTANT: Edit the service file to match your setup:"
    echo "   sudo nano /etc/systemd/system/smartcar-webhook.service"
    echo ""
    echo "Update these paths:"
    echo "   - WorkingDirectory: /path/to/smartcar-traccar-webhook"
    echo "   - EnvironmentFile: /path/to/.env"
    echo "   - ExecStart: /path/to/venv/bin/gunicorn ..."
    echo ""
    echo "After editing, run:"
    echo "   sudo systemctl daemon-reload"
    echo "   sudo systemctl enable smartcar-webhook"
    echo "   sudo systemctl start smartcar-webhook"
fi

echo ""
echo "=============================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Read DEPLOYMENT.md for detailed instructions"
echo "2. Configure Nginx reverse proxy (if needed)"
echo "3. Set up SSL/TLS with Let's Encrypt"
echo "4. Register webhook in Smartcar Dashboard"
echo ""
