# Webhooks Integration Summary

### Files Structure

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
4. use the application management token to put in the .env file SMARTCAR_MANAGEMENT_TOKEN=<your-management-token>

### 4. Start Webhook Server

```bash
python webhooks/webhook_handler.py
```

## Configuration

### Required .env Variables

```bash
# Webhook Secret from Smartcar Dashboard - the application management token
SMARTCAR_WEBHOOK_SECRET=your_webhook_secret_here

# Server configuration
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000

# Traccar (unchanged)
TRACCAR_API_URL=http://example.com
TRACCAR_USERNAME=admin@admin.com
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
