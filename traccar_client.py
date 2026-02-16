"""
Traccar GPS tracking server client.

Sends vehicle location updates to Traccar.
"""

import os
import requests
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

# Load environment
load_dotenv(Path(__file__).parent / '.env')


class TraccarClient:
    """Client for Traccar GPS tracking server."""
    
    def __init__(self):
        """Initialize Traccar client with configuration from environment."""
        self.api_url = os.getenv('TRACCAR_API_URL')
        self.username = os.getenv('TRACCAR_USERNAME')
        self.password = os.getenv('TRACCAR_PASSWORD')
        self.authenticated = False
        self.session = requests.Session()
        
        if self.api_url and self.username and self.password:
            self._authenticate()
        else:
            print("⚠️  Traccar credentials not configured")
    
    def _authenticate(self) -> bool:
        """
        Authenticate with Traccar server.
        
        Returns:
            True if authentication successful
        """
        try:
            login_url = f"{self.api_url}/api/session"
            # Traccar expects form data, not JSON
            response = self.session.post(
                login_url,
                data={
                    'email': self.username,
                    'password': self.password
                }
            )
            
            if response.status_code == 200:
                self.authenticated = True
                print(f"✓ Authenticated with Traccar: {self.api_url}")
                return True
            else:
                print(f"❌ Traccar authentication failed: {response.status_code}")
                print(f"   URL: {login_url}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Traccar connection error: {e}")
            return False
    
    def send_location(
        self,
        device_id: str,
        latitude: float,
        longitude: float,
        accuracy: Optional[float] = None,
        altitude: Optional[float] = None,
        speed: Optional[float] = None,
        course: Optional[float] = None
    ) -> bool:
        """
        Send location update to Traccar.
        
        Args:
            device_id: Traccar device ID (or Smartcar vehicle ID)
            latitude: Vehicle latitude
            longitude: Vehicle longitude
            accuracy: Location accuracy in meters (optional)
            altitude: Altitude in meters (optional)
            speed: Speed in km/h (optional)
            course: Bearing/heading in degrees (optional)
            
        Returns:
            True if successfully sent
        """
        if not self.authenticated:
            print(f"⚠️  Not authenticated with Traccar, skipping location update")
            return False
        
        try:
            # Get or create device
            device = self._get_or_create_device(device_id)
            if not device:
                print(f"❌ Could not get/create device {device_id}")
                return False
            
            device_pk = device.get('id')
            
            # Send position data via Traccar API
            position_url = f"{self.api_url}/api/positions"
            position_data = {
                'deviceId': device_pk,
                'serverTime': int(__import__('time').time() * 1000),
                'deviceTime': int(__import__('time').time() * 1000),
                'fixTime': int(__import__('time').time() * 1000),
                'valid': True,
                'latitude': float(latitude),
                'longitude': float(longitude),
                'altitude': altitude or 0,
                'speed': speed or 0,
                'course': course or 0,
                'accuracy': accuracy or 0
            }
            
            response = self.session.post(position_url, json=position_data)
            
            if response.status_code == 200:
                return True
            else:
                print(f"⚠️  Traccar position update failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending location to Traccar: {e}")
            return False
    
    def _get_or_create_device(self, device_id: str) -> Optional[dict]:
        """
        Get device from Traccar or create if it doesn't exist.
        
        Args:
            device_id: Vehicle ID (usually Smartcar vehicle ID)
            
        Returns:
            Device dict with 'id' and 'name' keys, or None
        """
        try:
            # Try to get device by name
            devices_url = f"{self.api_url}/api/devices"
            response = self.session.get(devices_url)
            
            if response.status_code == 200:
                devices = response.json()
                for device in devices:
                    if device.get('uniqueId') == device_id or device.get('name') == device_id:
                        return device
            
            # Device not found, try to create it
            return self._create_device(device_id)
            
        except Exception as e:
            print(f"⚠️  Could not get device {device_id}: {e}")
            return None
    
    def _create_device(self, device_id: str) -> Optional[dict]:
        """
        Create a new device in Traccar.
        
        Args:
            device_id: Vehicle ID
            
        Returns:
            Created device dict, or None
        """
        try:
            devices_url = f"{self.api_url}/api/devices"
            device_data = {
                'name': f"Vehicle {device_id}",
                'uniqueId': device_id,
                'status': 'online'
            }
            
            response = self.session.post(devices_url, json=device_data)
            
            if response.status_code == 200:
                device = response.json()
                print(f"✓ Created Traccar device: {device.get('name')} ({device.get('id')})")
                return device
            else:
                print(f"⚠️  Failed to create device in Traccar: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"⚠️  Error creating device in Traccar: {e}")
            return None
