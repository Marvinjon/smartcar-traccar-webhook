# Smartcar Webhooks Integration

Real-time vehicle location updates using Smartcar's event-driven webhook system.

## Architecture

```
Smartcar API
    ↓ (webhook POST)
Webhook Handler (Flask)
    ├→ Validate signature
    ├→ Check for duplicates
    ├→ Ensure Traccar user exists (create if new customer)
    ├→ Ensure Traccar device exists (create if new vehicle)
    ├→ Link user to device (Traccar permissions)
    └→ Send telemetry to Traccar
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
- Auto-provisions Traccar user accounts (see [User Auto-Provisioning](#user-auto-provisioning))
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

## User Auto-Provisioning

When a `VEHICLE_STATE` webhook arrives, the service automatically creates a Traccar account for the Smartcar user if one does not already exist, then grants that account access to the user's vehicle.

### How it works

1. The webhook payload includes a `data.user.id` field (a Smartcar UUID).
2. The service looks up a Traccar user with the email `{smartcar_user_id}@smartcar.local`.
3. If none is found, a new Traccar user is created with:
   - **Name:** `Smartcar {first 8 chars of UUID}`
   - **Email:** `{smartcar_user_id}@smartcar.local`
   - **Password:** randomly generated (printed once to the server log)
4. The user is then granted access to their vehicle's Traccar device via the permissions API.

### First-time customer log output

When a new customer is seen for the first time, you will see something like this in your server logs:

```
✓ Created Traccar user for Smartcar user f923e070 (Traccar ID: 42)
   Email: f923e070-b240-48e0-9244-74e2dd0fc7b3@smartcar.local
   Password: xK9mPqR2vLs8dNjT  ← save this, it will not be shown again
✓ Linked Traccar device 7 to user 42
```

**Save the generated password** — it is only logged once at creation time. You can distribute it to the customer or use the Traccar admin panel to set a new one.

### Subsequent webhooks

After the first provisioning, `ensure_user` finds the existing user by email and skips creation. The device-to-user permission link is also idempotent (duplicate attempts are silently ignored).

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

1. **Check signature error** - Verify `SMARTCAR_MANAGEMENT_TOKEN` matches the token in the Smartcar Dashboard
2. **Check domain** - Ensure domain resolves and SSL cert is valid
3. **Check Dashboard logs** - View delivery attempts in Smartcar Dashboard
4. **Check port** - Ensure WEBHOOK_PORT is forwarded/accessible

### Location not updating in Traccar

1. **Check Traccar auth** - Verify credentials in .env
2. **Check vehicle ID** - Ensure Smartcar vehicle UUID appears as the device's `uniqueId` in Traccar
3. **Check signals** - Verify location signals are subscribed in the Smartcar Dashboard webhook config
4. **Check logs** - Look for extraction errors in webhook handler output

### Traccar user not being created

1. **Check Traccar credentials** - The service logs in as an admin; non-admin accounts cannot create users via the API
2. **Check `GET /api/users`** - If this returns a 403, the configured Traccar account lacks admin privileges
3. **Check logs** - Search for `ensure_user` or `create_user` error messages
4. **Password not saved** - If you missed the one-time password log, use the Traccar admin panel to set a new password for the user

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
- ✓ Automatic Traccar user provisioning per customer
- ✓ Automatic device-to-user permission linking

## Support

For Smartcar API issues: https://smartcar.com/docs
For webhook debugging: Check Smartcar Dashboard → Webhooks → Logs
For Traccar issues: Check Traccar server logs
