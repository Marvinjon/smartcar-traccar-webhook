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
    
    def extract_all_signals(self, signals: list) -> Optional[Dict]:
        """
        Extract all available signals from webhook payload.
        
        Args:
            signals: Signals list from webhook payload
            
        Returns:
            Dict with all extracted signal data, or None if no useful signals at all
        """
        try:
            data = {
                'latitude': None,
                'longitude': None,
                'timestamp': None,
                'odometer_km': None,
                'battery_level': None,
                'battery_range': None,
                'fuel_level': None,
                'low_voltage_battery': None,
                'is_charging': None,
                'vin': None,
                'doors_status': None,
                'windows_status': None,
                'is_locked': None,
                'custom_attributes': {}
            }
            
            for signal in signals:
                group = signal.get('group', '')
                name = signal.get('name', '')
                body = signal.get('body', {})
                meta = signal.get('meta', {})
                status = signal.get('status', {})
                
                if status.get('value') != 'SUCCESS':
                    continue
                
                if group == 'Location':
                    data['latitude'] = body.get('latitude')
                    data['longitude'] = body.get('longitude')
                    oem_updated_at = meta.get('oemUpdatedAt')
                    if oem_updated_at:
                        data['timestamp'] = int(oem_updated_at / 1000)
                
                elif group == 'Odometer':
                    odometer_value = body.get('value')
                    unit = body.get('unit', 'm')
                    if odometer_value:
                        if unit == 'km':
                            data['odometer_km'] = float(odometer_value)
                        else:
                            data['odometer_km'] = float(odometer_value) / 1000
                
                elif group == 'TractionBattery':
                    if name == 'StateOfCharge':
                        data['battery_level'] = body.get('value')
                    elif name == 'Range':
                        data['battery_range'] = body.get('value')
                
                elif group == 'LowVoltageBattery':
                    if name == 'StateOfCharge':
                        data['low_voltage_battery'] = body.get('value')
                    elif name == 'Status':
                        data['custom_attributes']['low_voltage_status'] = body.get('value')
                
                elif group == 'InternalCombustionEngine':
                    if name == 'FuelLevel':
                        data['fuel_level'] = body.get('value')
                
                elif group == 'Charge':
                    if name == 'IsCharging':
                        is_charging_val = body.get('value')
                        data['is_charging'] = is_charging_val in [True, 'true', 'True', 1]
                    elif name == 'TimeToComplete':
                        data['custom_attributes']['time_to_complete'] = body.get('value')
                
                elif group == 'Closure':
                    if name == 'Doors':
                        data['doors_status'] = body.get('value')
                    elif name == 'Windows':
                        data['windows_status'] = body.get('value')
                    elif name == 'IsLocked':
                        data['is_locked'] = body.get('value')
                    else:
                        data['custom_attributes'][f'closure_{name.lower()}'] = body.get('value')
                
                elif group == 'VehicleIdentification':
                    if name == 'VIN':
                        data['vin'] = body.get('value')
                    else:
                        data['custom_attributes'][f'vehicle_{name.lower()}'] = body.get('value')
                
                else:
                    data['custom_attributes'][f'{group.lower()}_{name.lower()}'] = body.get('value')
            
            # Return data if we have any useful signals (not just empty defaults)
            has_location = data['latitude'] is not None and data['longitude'] is not None
            has_other_data = any(
                data[k] is not None 
                for k in ['odometer_km', 'battery_level', 'battery_range', 'fuel_level',
                          'low_voltage_battery', 'is_charging', 'vin', 'doors_status',
                          'windows_status', 'is_locked']
            ) or bool(data['custom_attributes'])
            
            if has_location or has_other_data:
                return data
            
            return None
        except (KeyError, ValueError, TypeError) as e:
            print(f"⚠️  Could not extract signals: {e}")
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
            # Extract all signal data
            signal_data = self.extract_all_signals(signals)
            
            if not signal_data:
                print(f"\u26a0\ufe0f  No useful data in event {event_id} for vehicle {vehicle_id}")
                self.mark_processed(event_id)
                return True
            
            has_location = signal_data['latitude'] is not None and signal_data['longitude'] is not None
            
            # Update Traccar
            try:
                success, message = self.traccar.send_location(
                    device_id=vehicle_id,
                    latitude=signal_data['latitude'],
                    longitude=signal_data['longitude'],
                    timestamp=signal_data['timestamp'],
                    odometer_km=signal_data['odometer_km'],
                    battery_level=signal_data['battery_level'],
                    battery_range=signal_data['battery_range'],
                    fuel_level=signal_data['fuel_level'],
                    low_voltage_battery=signal_data['low_voltage_battery'],
                    is_charging=signal_data['is_charging'],
                    vin=signal_data['vin'],
                    doors_status=signal_data['doors_status'],
                    windows_status=signal_data['windows_status'],
                    is_locked=signal_data['is_locked'],
                    custom_attributes=signal_data['custom_attributes']
                )
                
                if success:
                    if has_location:
                        details = f"{signal_data['latitude']}, {signal_data['longitude']}"
                    else:
                        details = "no location"
                    if signal_data['odometer_km']:
                        details += f" ({signal_data['odometer_km']:.1f} km)"
                    if signal_data['battery_level']:
                        details += f" [batt: {signal_data['battery_level']}%]"
                    print(f"✓ Updated vehicle {vehicle_id}: {details}")
                    # Mark as processed only after successful update
                    self.mark_processed(event_id)
                    return True
                else:
                    print(f"⚠️  Failed to update vehicle {vehicle_id}: {message}")
                    return False
                
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
