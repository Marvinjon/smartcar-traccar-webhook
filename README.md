# Smartcar Webhooks Integration

Real-time vehicle location updates using Smartcar's event-driven webhook system.

## Architecture

```
Smartcar API
    ↓ (webhook POST)
Webhook Handler (Flask)
    ├→ Validate signature
    ├→ Check for duplicates
    ├→ Extract location
    └→ Send to Traccar
```

## Quick Start

### 1. Install Dependencies

```bash
pip install flask
```

### 2. Configure Webhook

Run setup helper:
```bash
python webhook_config.py your-domain.com
```

This will print setup instructions.

### 3. Manual Setup in Smartcar Dashboard

1. Go to https://dashboard.smartcar.com
2. Create new webhook with:
   - URL: `https://your-domain.com/webhooks/smartcar`
   - Event Type: `VEHICLE_STATE`
   - Signals:
     - ✓ Location.Latitude
     - ✓ Location.Longitude
     - ✓ Odometer.Odometer

3. Note your **Application Management Token** from Smartcar Dashboard

### 4. Update .env

```bash
# Add these variables to .env
SMARTCAR_MANAGEMENT_TOKEN=<paste_token_here>
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
```

### 5. Start Webhook Server

```bash
python webhook_handler.py
```

Expected output:
```
╔════════════════════════════════════════════════════════════════╗
║         Smartcar Webhook Server Running                       ║
╠════════════════════════════════════════════════════════════════╣
║ Server: http://0.0.0.0:5000                                    
║ Webhook endpoint: POST /webhooks/smartcar
```

### 6. Test

```bash
# Health check
curl https://your-domain.com/webhooks/health

# View stats
curl https://your-domain.com/webhooks/stats
```

## Module Overview

### webhook_handler.py
Flask application that receives and validates webhooks.

- `POST /webhooks/smartcar` - Receives Smartcar webhook events
- `GET /webhooks/health` - Health check
- `GET /webhooks/stats` - Webhook statistics
- Validates `SC-Signature` header using HMAC-SHA256
- Returns 200 immediately, processes asynchronously

### webhook_validator.py
Signature validation and payload parsing.

- `validate_signature()` - Verify webhook authenticity
- `extract_event_data()` - Parse vehicle, event, and signal data

### webhook_processor.py
Event processing and deduplication.

- Maintains processed event IDs in `webhook_dedup.json`
- Prevents duplicate location updates
- Extracts latitude/longitude/odometer from signals
- Posts to Traccar API
- Thread-safe per-vehicle processing

### webhook_config.py
Setup helper and configuration validation.

- `get_setup_instructions()` - Print Smartcar Dashboard setup steps
- `validate_config()` - Check .env configuration
- Run with domain: `python webhook_config.py your-domain.com`

## Configuration

### Environment Variables

```env
# Webhook server
WEBHOOK_HOST=0.0.0.0           # Listen on all interfaces
WEBHOOK_PORT=5000              # Port webhook listens on
WEBHOOK_DEBUG=false            # Enable Flask debug mode

# Smartcar
SMARTCAR_MANAGEMENT_TOKEN=***  # From Smartcar Dashboard

# Traccar (required for location updates)
TRACCAR_API_URL=http://example.com
TRACCAR_USERNAME=admin
TRACCAR_PASSWORD=***
```

## Deduplication

Processed event IDs are stored in `webhook_dedup.json` to prevent duplicate updates.

Example:
```json
[
  "f7c0f3e6-4c9d-4f0e-8e5d-6e7f8a9b0c1d",
  "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
]
```

**Why?** Smartcar retries failed deliveries. Using `eventId` ensures the same location change is only processed once.

## Security

✓ **Signature Validation** - All incoming webhooks are validated using HMAC-SHA256
✓ **Rate Limiting** - Consider adding rate limits in production (reverse proxy)
✓ **HTTPS Only** - Smartcar requires valid SSL certificates
✓ **Immediate Response** - Returns 200 immediately to prevent retries on timeout
✓ **Async Processing** - Long operations won't block webhook response

## Monitoring

### Check Logs

```bash
# Follow logs in real-time
tail -f webhook_dedup.json  # View processed events

# In systemd
sudo journalctl -u smartcar-webhook -f
```

### Monitor Stats

```bash
# Get stats endpoint
curl https://your-domain.com/webhooks/stats

# Response example
{
  "processed_events": 42,
  "traccar_authenticated": true
}
```

## Troubleshooting

### Webhook not receiving events

1. **Check signature error** - Verify SMARTCAR_WEBHOOK_SECRET matches Dashboard
2. **Check domain** - Ensure domain resolves and SSL cert is valid
3. **Check Dashboard logs** - View delivery attempts in Smartcar Dashboard
4. **Check port** - Ensure WEBHOOK_PORT is forwarded/accessible

### Location not updating in Traccar

1. **Check Traccar auth** - Verify credentials in .env
2. **Check vehicle ID** - Ensure Smartcar ID matches Traccar device unique ID
3. **Check signals** - Verify Location.Latitude/Longitude are subscribed
4. **Check logs** - Look for extraction errors in webhook handler output

### Duplicate events

1. **Check webhook_dedup.json** - Ensure it's being written to
2. **Check file permissions** - Dedup file must be writable by webhook process
3. **Monitor eventId** - Watch for same eventId appearing multiple times

## API Reference

### Webhook Payload

Incoming `VEHICLE_STATE` event:

```json
{
  "eventId": "f7c0f3e6-4c9d-4f0e-8e5d-6e7f8a9b0c1d",
  "eventType": "VEHICLE_STATE",
  "data": {
    "vehicle": {
      "id": "62e9e3e3-82a8-42f0-9de2-da633c9f2c06"
    },
    "signals": {
      "Location.Latitude": {
        "value": 37.7749,
        "meta": {
          "oemUpdatedAt": 1678901234000,
          "fetchedAt": 1678901235000
        }
      },
      "Location.Longitude": {
        "value": -122.4194,
        "meta": { ... }
      },
      "Odometer.Odometer": {
        "value": 156500,
        "meta": { ... }
      }
    }
  },
  "meta": {
    "deliveryId": "5d569643-3a47-4cd1-a3ec-db5fc1f6f03b",
    "deliveredAt": 1678901234567
  }
}
```

## Deployment

For deployment to Ubuntu servers with systemd. A sample systemd unit file is included in [smartcar-webhook.service](smartcar-webhook.service).

```bash
# 1. Run deployment script
bash deploy.sh

# 2. Copy and edit the systemd service file with your paths
sudo cp smartcar-webhook.service /etc/systemd/system/
sudo nano /etc/systemd/system/smartcar-webhook.service

# 3. Start service
sudo systemctl enable smartcar-webhook
sudo systemctl start smartcar-webhook

# 4. Check status
sudo systemctl status smartcar-webhook
```

### Key Features

- ✓ Gunicorn WSGI server (4 workers by default)
- ✓ Systemd auto-start and restart
- ✓ Structured logging to files
- ✓ Health check endpoint
- ✓ Environment variable validation
- ✓ Webhook signature verification
- ✓ Event deduplication

## Support

For Smartcar API issues: https://smartcar.com/docs
For webhook debugging: Check Smartcar Dashboard → Webhooks → Logs
For Traccar issues: Check Traccar server logs
