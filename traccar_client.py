"""
Traccar GPS tracking server client.

Sends vehicle location updates to Traccar using OsmAnd protocol.
"""

import os
import requests
import time
import logging
from typing import Optional, Tuple
from dotenv import load_dotenv
from pathlib import Path

# Load environment
load_dotenv(Path(__file__).parent / '.env')
logger = logging.getLogger(__name__)


class TraccarClient:
    """Client for Traccar GPS tracking server."""
    
    def __init__(self):
        """Initialize Traccar client with configuration from environment."""
        self.api_url = os.getenv('TRACCAR_API_URL')
        self.base_url = os.getenv('TRACCAR_BASE_URL', self.api_url)  # For OsmAnd protocol
        self.username = os.getenv('TRACCAR_USERNAME')
        self.password = os.getenv('TRACCAR_PASSWORD')
        self.authenticated = False
        self.session = requests.Session()
        
        if self.api_url and self.username and self.password:
            self._authenticate()
        else:
            logger.warning("⚠️  Traccar credentials not configured")
    
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
                logger.info(f"✓ Authenticated with Traccar: {self.api_url}")
                return True
            else:
                logger.error(f"❌ Traccar authentication failed: {response.status_code}")
                logger.error(f"   URL: {login_url}")
                logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Traccar connection error: {e}")
            return False
    
    def send_location(
        self,
        device_id: str,
        latitude: float,
        longitude: float,
        accuracy: Optional[float] = None,
        altitude: Optional[float] = None,
        speed: Optional[float] = None,
        course: Optional[float] = None,
        timestamp: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Send vehicle location to Traccar using OsmAnd protocol.
        
        Args:
            device_id: Device unique ID (or identifier)
            latitude: Vehicle latitude
            longitude: Vehicle longitude
            accuracy: Location accuracy in meters (optional)
            altitude: Altitude in meters (optional)
            speed: Speed in km/h (optional)
            course: Bearing/heading in degrees (optional)
            timestamp: Unix timestamp in seconds (optional, defaults to now)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.authenticated:
            logger.warning(f"⚠️  Not authenticated with Traccar, skipping location update for {device_id}")
            return False, "Not authenticated"
        
        try:
            # Ensure device exists - create if needed
            devices = self.get_devices()
            device_exists = any(d.get('uniqueId') == device_id for d in devices)
            
            if not device_exists:
                logger.info(f"📱 Device {device_id} not found, creating...")
                success, msg, _ = self.create_device(device_id, f"Vehicle {device_id}", device_id)
                if not success:
                    logger.error(f"Failed to create device: {msg}")
                    return False, f"Could not create device: {msg}"
            
            # Use current time if not provided (in milliseconds for Traccar)
            if timestamp is None:
                timestamp_ms = int(time.time() * 1000)
            else:
                timestamp_ms = int(timestamp * 1000) if timestamp < 100000000000 else int(timestamp)
            
            # Build OsmAnd protocol request
            # The device should now exist, send location via API
            url = f"{self.api_url}/api/positions"
            
            # Get device ID from uniqueId
            devices = self.get_devices()
            device = next((d for d in devices if d.get('uniqueId') == device_id), None)
            
            if not device:
                return False, "Device not found after creation"
            
            device_pk = device.get('id')
            
            # Send position data via API
            position_data = {
                'deviceId': device_pk,
                'latitude': float(latitude),
                'longitude': float(longitude),
                'altitude': altitude or 0,
                'speed': speed or 0,
                'course': course or 0,
                'accuracy': accuracy or 0,
                'fixTime': timestamp_ms,
                'serverTime': int(time.time() * 1000),
                'valid': True
            }
            
            response = self.session.post(url, json=position_data, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✓ Sent location for device {device_id}: {latitude}, {longitude}")
                return True, "Location updated"
            else:
                logger.error(f"❌ Traccar error {response.status_code} for device {device_id}")
                logger.error(f"   Response: {response.text}")
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            logger.error(f"❌ Error sending location to Traccar for device {device_id}: {e}")
            return False, str(e)
    
    def get_devices(self):
        """
        Get list of all devices from Traccar API.
        Requires authentication.
        
        Returns:
            List of device dictionaries
        """
        if not self.authenticated:
            logger.warning("Not authenticated with Traccar - cannot fetch devices")
            return []
        
        try:
            url = f"{self.api_url}/api/devices"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                devices = response.json()
                logger.info(f"Retrieved {len(devices)} devices from Traccar")
                return devices
            else:
                logger.error(f"Error fetching devices: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching devices from Traccar: {e}")
            return []
    
    def create_device(self, device_id: str, name: str, unique_id: Optional[str] = None) -> Tuple[bool, str, Optional[int]]:
        """
        Create a new device in Traccar.
        Requires authentication.
        
        Args:
            device_id: Unique identifier for the device (e.g., Smartcar vehicle ID)
            name: Human-readable name for the device
            unique_id: Optional unique ID (defaults to device_id if not provided)
            
        Returns:
            Tuple of (success: bool, message: str, traccar_device_id: int or None)
        """
        if not self.authenticated:
            logger.warning("Not authenticated - cannot create device")
            return False, "Not authenticated with Traccar", None
        
        try:
            url = f"{self.api_url}/api/devices"
            
            payload = {
                'name': name,
                'uniqueId': unique_id or device_id,
                'category': 'car',
            }
            
            response = self.session.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                traccar_id = result.get('id')
                logger.info(f"✓ Created device '{name}' in Traccar (ID: {traccar_id})")
                return True, f"Created device {name}", traccar_id
            elif response.status_code == 409:
                logger.warning(f"Device {name} already exists in Traccar")
                return False, "Device already exists", None
            else:
                logger.error(f"Error creating device: {response.status_code}")
                return False, str(response.text), None
                
        except Exception as e:
            logger.error(f"Error creating device {name}: {e}")
            return False, str(e), None
