# Webhooks Integration Summary

## What's New

A complete webhook-based real-time location tracking system has been added to your project.

### New Files Structure

```
webhooks/
├── __init__.py                 # Package initialization
├── webhook_handler.py          # Flask server to receive webhooks
├── webhook_validator.py        # Signature verification
├── webhook_processor.py        # Event processing & deduplication
├── webhook_config.py           # Configuration helper
├── setup.py                    # Interactive setup wizard
├── README.md                   # Complete webhook documentation
└── webhook_dedup.json          # Processed event IDs (auto-created)
```

## Key Features

✅ **Real-time Updates** - Location changes delivered in seconds  
✅ **Signature Validation** - HMAC-SHA256 verification for security  
✅ **Deduplication** - Prevents duplicate location updates  
✅ **Error Handling** - Graceful failure with detailed logging  
✅ **Production Ready** - Systemd/Docker/Supervisor deployment guides included  

## Quick Start (3 Steps)

### 1. Install Flask

```bash
pip install flask
```

Or:
```bash
pip install -r requirements.txt
```

### 2. Run Setup Wizard

```bash
python webhooks/setup.py
```

This will:
- Check requirements
- Validate .env configuration  
- Test Traccar connection
- Print Smartcar Dashboard setup instructions

### 3. Get Webhook Secret from Smartcar

1. Go to https://dashboard.smartcar.com
2. Create new webhook with URL: `https://your-domain.com/webhooks/smartcar`
3. Subscribe to `VEHICLE_STATE` events with signals:
   - Location.Latitude
   - Location.Longitude  
   - Odometer.Odometer
4. Copy the **Secret** shown
5. Update `.env`: `SMARTCAR_WEBHOOK_SECRET=<paste_here>`

### 4. Start Webhook Server

```bash
python webhooks/webhook_handler.py
```

## Configuration

### Required .env Variables

```bash
# Webhook Secret from Smartcar Dashboard
SMARTCAR_WEBHOOK_SECRET=your_webhook_secret_here

# Server configuration
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000

# Traccar (unchanged)
TRACCAR_API_URL=http://example.com
TRACCAR_USERNAME=admin
TRACCAR_PASSWORD=***
```

### Optional Variables

```bash
# Debug mode (development only)
WEBHOOK_DEBUG=false
```

## How It Works

```
1. Vehicle's location changes
        ↓
2. Smartcar detects change
        ↓
3. Smartcar sends HTTP POST webhook to your server
        ↓
4. Webhook Handler verifies signature (HMAC-SHA256)
        ↓
5. Processor checks for duplicates (using eventId)
        ↓
6. Extracts latitude/longitude/odometer from signals
        ↓
7. Posts location update to Traccar API
        ↓
8. Returns 200 OK immediately
```

All done in under 1 second!

## Endpoints

### Webhook Receiver
- **POST** `/webhooks/smartcar` - Receives Smartcar events
- Validation: `SC-Signature` header (HMAC-SHA256)
- Response: `200 OK` (always, even on processing errors)

### Health Check
- **GET** `/webhooks/health` - Server is running
- Response: `{"status": "ok"}`

### Statistics
- **GET** `/webhooks/stats` - Processing metrics
- Response: `{"processed_events": 42, "traccar_authenticated": true}`

## Deduplication

Prevents duplicate location updates using event IDs stored in `webhook_dedup.json`.

**Why needed?** Smartcar retries failed deliveries with exponential backoff:
- 1st attempt: 0s
- 2nd attempt: 25s later
- 3rd attempt: 50s later
- 4th attempt: 100s later

Each has same `eventId`, so deduplication ensures it's only processed once.

## Security

✓ **Signature Verification** - All webhooks validated with HMAC-SHA256  
✓ **Immediate Response** - Returns 200 right away to prevent timeout retries  
✓ **HTTPS Required** - Smartcar enforces valid SSL certificates  
✓ **Error Isolation** - Processing errors don't affect webhook response  
✓ **Thread-safe** - Per-vehicle locks prevent race conditions  

## Monitoring

### View Logs
```bash
# Real-time output
python webhooks/webhook_handler.py

# Check processed events
cat webhook_dedup.json | python -m json.tool

# Stats endpoint
curl http://localhost:5000/webhooks/stats
```

### Common Logs

```
✓ Updated vehicle abc-123: 37.7749, -122.4194 (156.5 km)
   Vehicle location successfully sent to Traccar

⚠️  Duplicate event f7c0f3e6... - skipping
   This event was already processed (dedup check)

❌ Invalid webhook signature: abc123def...
   Webhook secret doesn't match - check .env

📡 Webhook received: VEHICLE_STATE
   Smartcar sent a vehicle state change event
```

## Troubleshooting

### Webhooks not being received

**Problem:** No logs in webhook handler
**Solution:** Check that:
1. Domain resolves publicly: `nslookup your-domain.com`
2. Port is accessible: `curl https://your-domain.com/webhooks/health`
3. Webhook is enabled in Smartcar Dashboard
4. No firewall blocking incoming connections

### Location not updating

**Problem:** Logs show "No location data"
**Solution:**
1. Check Smartcar Dashboard → Webhook Logs for signal delivery
2. Verify signals subscribed: Location.Latitude, Location.Longitude
3. Check Traccar credentials in .env
4. Verify vehicle ID matches between Smartcar and Traccar

### Getting "Invalid signature" errors

**Problem:** Logs show signature validation failures
**Solution:**
1. Copy webhook SECRET exactly from Dashboard (no extra spaces)
2. Update .env: `SMARTCAR_WEBHOOK_SECRET=<exact_copy>`
3. Restart webhook handler
4. Test: `curl http://localhost:5000/webhooks/health` works (no signature needed)

## Deployment

See [webhooks/README.md](webhooks/README.md#production-deployment) for:
- Systemd (Linux) service setup
- Supervisor process management
- Docker containerization
- Nginx reverse proxy config
- Let's Encrypt SSL setup

## Next Steps

1. **Install Flask:** `pip install flask`
2. **Run Setup:** `python webhooks/setup.py`
3. **Create Webhook:** Follow printed instructions on Smartcar Dashboard
4. **Update .env:** Add `SMARTCAR_WEBHOOK_SECRET`
5. **Start Server:** `python webhooks/webhook_handler.py`
6. **Test:** `curl http://localhost:5000/webhooks/health`
7. **Monitor:** Watch logs for incoming webhook events

## Documentation

- **[webhooks/README.md](webhooks/README.md)** - Full documentation
- **[webhook_handler.py](webhook_handler.py)** - Server code
- **[webhook_processor.py](webhook_processor.py)** - Event processing logic
- **[webhook_config.py](webhook_config.py)** - Configuration helper

## Questions?

For Smartcar API specific issues: https://smartcar.com/docs  
For webhook debugging: View logs in Smartcar Dashboard → Webhooks → Logs  
For integration issues: Check logs from `python webhooks/webhook_handler.py`
