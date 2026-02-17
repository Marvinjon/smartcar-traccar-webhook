# Production Deployment Guide

This guide explains how to deploy the Smartcar Webhook Server to an Ubuntu server for production use.

## Prerequisites

- Ubuntu 20.04 or later
- Python 3.8+
- Sudo access
- HTTPS with valid SSL certificate (required by Smartcar)
- Public domain pointing to your server (e.g., `example.com`)

## 1. Initial Setup

### Clone or upload the project

```bash
cd ~/allskonar
git clone <repo-url> smartcar-traccar-webhook
cd smartcar-traccar-webhook
```

### Create Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Configure Environment

### Copy and edit .env

```bash
cp .env.example .env
nano .env
```

Fill in all required values:

```bash
# Smartcar API credentials
SMARTCAR_MANAGEMENT_TOKEN=your-token-here
SMARTCAR_WEBHOOK_SECRET=your-secret-here

# Webhook server configuration
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_DEBUG=false

# Traccar server configuration
TRACCAR_API_URL=https://example.com
TRACCAR_BASE_URL=http://example.com:5055
TRACCAR_USERNAME=your-email@example.com
TRACCAR_PASSWORD=your-password
```

### Test the configuration

```bash
python webhook_handler.py
```

Should output something like:
```
✓ Authenticated with Traccar: https://example.com

╔════════════════════════════════════════════════════════════════╗
║         Smartcar Webhook Server Running                       ║
```

Press `Ctrl+C` to stop.

## 3. Set Up Systemd Service

### Create log directory

```bash
sudo mkdir -p /var/log/smartcar-webhook
sudo chown www-data:www-data /var/log/smartcar-webhook
```

### Install systemd service

```bash
sudo cp smartcar-webhook.service /etc/systemd/system/
sudo nano /etc/systemd/system/smartcar-webhook.service```

**Update these paths to match your setup:**
- `WorkingDirectory` - Path to your project
- `EnvironmentFile` - Path to your .env file  
- `ExecStart` - Path to venv and project

Example for `/opt/smartcar-traccar-webhook`:

```ini
WorkingDirectory=/opt/smartcar-traccar-webhook
EnvironmentFile=/opt/smartcar-traccar-webhook/.env
ExecStart=/opt/smartcar-traccar-webhook/venv/bin/gunicorn \
    --workers 4 \
    --bind 0.0.0.0:5000 \
    --timeout 30 \
    --access-logfile /var/log/smartcar-webhook/access.log \
    --error-logfile /var/log/smartcar-webhook/error.log \
    wsgi:app
```

### Enable and start service

```bash
sudo systemctl daemon-reload
sudo systemctl enable smartcar-webhook
sudo systemctl start smartcar-webhook
sudo systemctl status smartcar-webhook
```