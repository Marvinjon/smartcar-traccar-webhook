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

## 4. Configure Nginx Reverse Proxy

### Install Nginx

```bash
sudo apt update
sudo apt install nginx
```

### Create Nginx config

```bash
sudo nano /etc/nginx/sites-available/smartcar-webhook
```

Add:

```nginx
upstream smartcar_webhook {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name example.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;
    
    # SSL certificates (use Let's Encrypt or your own)
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Logging
    access_log /var/log/nginx/smartcar-webhook-access.log;
    error_log /var/log/nginx/smartcar-webhook-error.log;
    
    # Proxy to Gunicorn
    location / {
        proxy_pass http://smartcar_webhook;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for webhook delivery
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

### Enable site

```bash
sudo ln -s /etc/nginx/sites-available/smartcar-webhook /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Set up SSL with Let's Encrypt (optional but recommended)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d example.com
```

## 5. Register Webhook in Smartcar Dashboard

1. Go to https://dashboard.smartcar.com
2. Navigate to Integrations → Webhooks
3. Create webhook with:
   - **URI:** `https://example.com/webhooks/smartcar`
   - **Mode:** Production
   - **Events:** VEHICLE_STATE
   - **Signals:**
     - Location.Latitude
     - Location.Longitude
     - Odometer.Odometer
4. Copy the **Webhook Secret** and add to `.env`:
   ```bash
   SMARTCAR_WEBHOOK_SECRET=<your-secret>
   ```
5. Click **Verify** - the server will auto-respond
6. Subscribe vehicles to the webhook

## 6. Monitoring

### Check service status

```bash
sudo systemctl status smartcar-webhook
sudo journalctl -u smartcar-webhook -f
```

### View logs

```bash
# Application logs
tail -f /var/log/smartcar-webhook/error.log
tail -f /var/log/smartcar-webhook/access.log

# System logs
sudo journalctl -u smartcar-webhook -n 100
```

### Health check

```bash
curl https://example.com/webhooks/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "smartcar-webhook"
}
```

## 7. Maintenance

### Update dependencies

```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart smartcar-webhook
```

### Backup data

```bash
# Backup deduplication cache
cp webhook_dedup.json webhook_dedup.json.backup
```

### View statistics

```bash
curl https://example.com/webhooks/stats
```

## Troubleshooting

### Service won't start

```bash
sudo journalctl -u smartcar-webhook -n 50
# Check for environment variable errors
cat /opt/smartcar-traccar-webhook/.env
```

### Connection refused

- Check if Gunicorn is running: `ps aux | grep gunicorn`
- Verify Nginx config: `sudo nginx -t`
- Check firewall: `sudo ufw status`

### Webhook not processing

- Verify signature in `.env`: `SMARTCAR_WEBHOOK_SECRET`
- Check logs: `sudo journalctl -u smartcar-webhook -f`
- Test webhook: Send test from Smartcar Dashboard

### Traccar authentication failed

- Verify credentials in `.env`
- Check Traccar server is accessible: `curl https://example.com/api/session`
- Verify user has admin/API access in Traccar

## Performance Tuning

### Adjust Gunicorn workers

For the system, update `/etc/systemd/system/smartcar-webhook.service`:

```bash
# Rule: workers = (2 × CPU cores) + 1
# For 4-core system: 9 workers
--workers 9
```

Then restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart smartcar-webhook
```

### Monitor resource usage

```bash
# Watch CPU/Memory
watch 'ps aux | grep gunicorn'
```
