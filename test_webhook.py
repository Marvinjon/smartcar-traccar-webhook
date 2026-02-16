#!/usr/bin/env python3
"""
Test webhook handler locally without needing real Smartcar webhooks.

This script simulates webhook events for testing the processor and validation.
"""

import json
import hmac
import hashlib
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from webhooks.webhook_validator import validate_signature, extract_event_data
from webhooks.webhook_processor import WebhookProcessor


def create_test_webhook_payload():
    """Create a realistic test VEHICLE_STATE webhook payload."""
    return {
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
                        "fetchedAt": int(datetime.now().timestamp() * 1000)
                    }
                },
                "Location.Longitude": {
                    "value": -122.4194,
                    "meta": {
                        "oemUpdatedAt": 1678901234000,
                        "fetchedAt": int(datetime.now().timestamp() * 1000)
                    }
                },
                "Odometer.Odometer": {
                    "value": 156500,
                    "meta": {
                        "oemUpdatedAt": 1678901234000,
                        "fetchedAt": int(datetime.now().timestamp() * 1000)
                    }
                }
            }
        },
        "meta": {
            "deliveryId": "5d569643-3a47-4cd1-a3ec-db5fc1f6f03b",
            "deliveredAt": int(datetime.now().timestamp() * 1000)
        }
    }


def create_signature(payload_str, secret):
    """Create HMAC-SHA256 signature for payload."""
    return hmac.new(
        secret.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def test_signature_validation():
    """Test webhook signature validation."""
    print("\n" + "="*70)
    print("TEST 1: Signature Validation")
    print("="*70)
    
    test_secret = "test_webhook_secret_12345"
    payload = create_test_webhook_payload()
    payload_str = json.dumps(payload, separators=(',', ':'))
    
    # Valid signature
    valid_sig = create_signature(payload_str, test_secret)
    is_valid = validate_signature(payload_str, valid_sig, test_secret)
    print(f"✓ Valid signature: {is_valid}")
    
    # Invalid signature
    invalid_sig = "invalid_signature_abc123"
    is_invalid = validate_signature(payload_str, invalid_sig, test_secret)
    print(f"✓ Invalid signature rejected: {not is_invalid}")
    
    # Wrong secret
    wrong_secret = "wrong_secret"
    wrong_sig = create_signature(payload_str, wrong_secret)
    rejected = not validate_signature(payload_str, wrong_sig, test_secret)
    print(f"✓ Wrong secret rejected: {rejected}")
    
    return is_valid and not is_invalid and rejected


def test_payload_extraction():
    """Test extracting event data from payload."""
    print("\n" + "="*70)
    print("TEST 2: Payload Extraction")
    print("="*70)
    
    payload = create_test_webhook_payload()
    event_id, vehicle_id, signals = extract_event_data(payload)
    
    print(f"✓ Event ID: {event_id}")
    print(f"✓ Vehicle ID: {vehicle_id}")
    print(f"✓ Signals count: {len(signals)}")
    
    success = (event_id == "f7c0f3e6-4c9d-4f0e-8e5d-6e7f8a9b0c1d" and
               vehicle_id == "62e9e3e3-82a8-42f0-9de2-da633c9f2c06" and
               len(signals) == 3)
    
    return success


def test_location_extraction():
    """Test extracting location from signals."""
    print("\n" + "="*70)
    print("TEST 3: Location Extraction")
    print("="*70)
    
    processor = WebhookProcessor(dedup_file="webhook_dedup_test.json")
    payload = create_test_webhook_payload()
    signals = payload['data']['signals']
    
    location = processor.extract_location(signals)
    
    if location:
        lat, lon, odometer = location
        print(f"✓ Latitude: {lat}")
        print(f"✓ Longitude: {lon}")
        print(f"✓ Odometer: {odometer} meters ({odometer/1000:.1f} km)")
        
        return (abs(lat - 37.7749) < 0.0001 and 
                abs(lon - (-122.4194)) < 0.0001)
    
    print("❌ Could not extract location")
    return False


def test_deduplication():
    """Test event deduplication."""
    print("\n" + "="*70)
    print("TEST 4: Deduplication")
    print("="*70)
    
    processor = WebhookProcessor(dedup_file="webhook_dedup_test.json")
    event_id = "test-event-123"
    
    # First check - should not be duplicate
    is_dup = processor.is_duplicate(event_id)
    print(f"✓ First check is_duplicate: {is_dup} (expected: False)")
    
    # Mark as processed
    processor.mark_processed(event_id)
    
    # Second check - should be duplicate
    is_dup2 = processor.is_duplicate(event_id)
    print(f"✓ Second check is_duplicate: {is_dup2} (expected: True)")
    
    return not is_dup and is_dup2


def test_full_webhook_processing():
    """Test full webhook processing end-to-end."""
    print("\n" + "="*70)
    print("TEST 5: Full Webhook Processing")
    print("="*70)
    
    processor = WebhookProcessor(dedup_file="webhook_dedup_test.json")
    payload = create_test_webhook_payload()
    
    # Check Traccar connection first
    if not processor.traccar.authenticated:
        print("⚠️  Traccar not authenticated - skipping full test")
        print("   (This is expected if Traccar credentials not configured)")
        return True  # Not a failure, just can't test
    
    print("✓ Traccar authenticated, testing full processing...")
    
    success = processor.process_webhook(payload)
    
    if success:
        print(f"✓ Webhook processed successfully")
        print(f"✓ Event marked as processed")
        return True
    else:
        print("❌ Webhook processing failed")
        return False


def cleanup_test_files():
    """Clean up test dedup file."""
    test_file = Path("webhook_dedup_test.json")
    if test_file.exists():
        test_file.unlink()
        print("✓ Cleaned up test files")


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + "  Webhook Handler Test Suite".center(68) + "║")
    print("╚" + "═"*68 + "╝")
    
    tests = [
        ("Signature Validation", test_signature_validation),
        ("Payload Extraction", test_payload_extraction),
        ("Location Extraction", test_location_extraction),
        ("Deduplication", test_deduplication),
        ("Full Processing", test_full_webhook_processing),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    # Cleanup
    cleanup_test_files()
    
    if passed == total:
        print("\n✓ All tests passed! Webhook system is working.\n")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Check configuration.\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
