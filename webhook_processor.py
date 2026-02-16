"""
Webhook event processor for Smartcar vehicle state changes.

Handles deduplication, location extraction, and Traccar updates.
"""

import json
import time
from threading import Lock
from typing import Optional, Dict, Set
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from traccar_client import TraccarClient


class WebhookProcessor:
    """Process Smartcar webhook events and update Traccar."""
    
    def __init__(self, dedup_file: str = "webhook_dedup.json"):
        """
        Initialize webhook processor.
        
        Args:
            dedup_file: Path to store processed event IDs for deduplication
        """
        self.traccar = TraccarClient()
        self.dedup_file = Path(dedup_file)
        self.processed_events: Set[str] = self._load_processed_events()
        self.lock = Lock()
        self.vehicle_locks: Dict[str, Lock] = {}
        
    def _load_processed_events(self) -> Set[str]:
        """Load previously processed event IDs from disk."""
        if self.dedup_file.exists():
            try:
                with open(self.dedup_file, 'r') as f:
                    data = json.load(f)
                    print(f"✓ Loaded {len(data)} processed event IDs")
                    return set(data)
            except Exception as e:
                print(f"⚠️  Could not load dedup file: {e}")
        return set()
    
    def _save_processed_events(self):
        """Save processed event IDs to disk."""
        try:
            with open(self.dedup_file, 'w') as f:
                json.dump(sorted(list(self.processed_events)), f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save dedup file: {e}")
    
    def is_duplicate(self, event_id: str) -> bool:
        """Check if event has already been processed."""
        with self.lock:
            return event_id in self.processed_events
    
    def mark_processed(self, event_id: str):
        """Mark event as processed."""
        with self.lock:
            self.processed_events.add(event_id)
            self._save_processed_events()
    
    def extract_location(self, signals: dict) -> Optional[tuple]:
        """
        Extract latitude and longitude from signals.
        
        Args:
            signals: Signal dict from webhook payload
            
        Returns:
            Tuple of (latitude, longitude, odometer_m) or None
        """
        try:
            # Location signals from Smartcar API
            location = signals.get('Location.Latitude', {}).get('value')
            latitude = signals.get('Location.Latitude', {}).get('value')
            longitude = signals.get('Location.Longitude', {}).get('value')
            odometer_m = signals.get('Odometer.Odometer', {}).get('value')
            
            if latitude is not None and longitude is not None:
                return float(latitude), float(longitude), odometer_m
            
            return None
        except (KeyError, ValueError, TypeError) as e:
            print(f"⚠️  Could not extract location: {e}")
            return None
    
    def process_vehicle_state_event(self, event_id: str, vehicle_id: str, signals: dict) -> bool:
        """
        Process VEHICLE_STATE event and update Traccar.
        
        Args:
            event_id: Unique event identifier
            vehicle_id: Smartcar vehicle ID
            signals: Signal data from webhook
            
        Returns:
            True if successfully processed
        """
        # Check for duplicates
        if self.is_duplicate(event_id):
            print(f"⚠️  Duplicate event {event_id} - skipping")
            return True
        
        # Get or create lock for this vehicle (thread-safe per-vehicle processing)
        if vehicle_id not in self.vehicle_locks:
            self.vehicle_locks[vehicle_id] = Lock()
        
        with self.vehicle_locks[vehicle_id]:
            # Extract location data
            location_data = self.extract_location(signals)
            
            if not location_data:
                print(f"⚠️  No location data in event {event_id} for vehicle {vehicle_id}")
                self.mark_processed(event_id)
                return True
            
            latitude, longitude, odometer_m = location_data
            odometer_km = (odometer_m / 1000) if odometer_m else 0
            
            # Update Traccar
            try:
                self.traccar.send_location(
                    device_id=vehicle_id,
                    latitude=latitude,
                    longitude=longitude,
                    accuracy=None
                )
                print(f"✓ Updated vehicle {vehicle_id}: {latitude}, {longitude} ({odometer_km:.1f} km)")
                
                # Mark as processed only after successful update
                self.mark_processed(event_id)
                return True
                
            except Exception as e:
                print(f"❌ Failed to update vehicle {vehicle_id}: {e}")
                return False
    
    def process_webhook(self, payload: dict) -> bool:
        """
        Process incoming webhook payload.
        
        Args:
            payload: Parsed webhook JSON
            
        Returns:
            True if successfully processed
        """
        try:
            event_id = payload.get('eventId')
            event_type = payload.get('eventType')
            vehicle_id = payload['data']['vehicle']['id']
            
            print(f"\n📡 Webhook received:")
            print(f"   Event: {event_type}")
            print(f"   Vehicle: {vehicle_id}")
            print(f"   EventId: {event_id}")
            
            if event_type == 'VEHICLE_STATE':
                signals = payload.get('data', {}).get('signals', {})
                return self.process_vehicle_state_event(event_id, vehicle_id, signals)
            
            elif event_type == 'VEHICLE_ERROR':
                print(f"⚠️  Vehicle error: {payload['data']['error']}")
                return True
            
            else:
                print(f"⚠️  Unknown event type: {event_type}")
                return True
                
        except (KeyError, TypeError) as e:
            print(f"❌ Error processing webhook: {e}")
            return False
