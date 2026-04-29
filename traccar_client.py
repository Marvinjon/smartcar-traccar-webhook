"""
Traccar GPS tracking server client.

Sends vehicle location updates to Traccar using OsmAnd protocol.
"""

import os
import requests
import time
import logging
from typing import Optional, Tuple, Dict
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
                self.authenticated = False
                logger.error(f"❌ Traccar authentication failed: {response.status_code}")
                logger.error(f"   URL: {login_url}")
                logger.error(f"   Response: {response.text}")
                return False

        except Exception as e:
            self.authenticated = False
            logger.error(f"❌ Traccar connection error: {e}")
            return False

    def _request_with_reauth(self, method: str, url: str, retried: bool = False, **kwargs):
        """
        Make an authenticated API request, automatically re-authenticating on 401.

        Args:
            method: HTTP method ('get', 'post', etc.)
            url: Request URL
            retried: Internal flag to prevent infinite retry loops
            **kwargs: Additional arguments passed to requests.Session.request()

        Returns:
            requests.Response object
        """
        response = self.session.request(method, url, **kwargs)

        if response.status_code == 401 and not retried:
            self.authenticated = False
            logger.warning("⚠️  Traccar session expired, re-authenticating...")
            if self._authenticate():
                logger.info("✓ Re-authenticated with Traccar successfully")
                return self._request_with_reauth(method, url, retried=True, **kwargs)
            else:
                logger.error("❌ Re-authentication failed")

        return response

    def send_location(
        self,
        device_id: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        accuracy: Optional[float] = None,
        altitude: Optional[float] = None,
        speed: Optional[float] = None,
        course: Optional[float] = None,
        timestamp: Optional[int] = None,
        odometer_km: Optional[float] = None,
        battery_level: Optional[float] = None,
        battery_range: Optional[float] = None,
        fuel_level: Optional[float] = None,
        low_voltage_battery: Optional[float] = None,
        is_charging: Optional[bool] = None,
        vin: Optional[str] = None,
        doors_status: Optional[str] = None,
        windows_status: Optional[str] = None,
        is_locked: Optional[bool] = None,
        custom_attributes: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        Send vehicle location and telemetry to Traccar using OsmAnd protocol.

        Args:
            device_id: Device unique ID (Smartcar vehicle ID)
            latitude: Vehicle latitude
            longitude: Vehicle longitude
            accuracy: Location accuracy in meters (optional)
            altitude: Altitude in meters (optional)
            speed: Speed in km/h (optional)
            course: Bearing/heading in degrees (optional)
            timestamp: Unix timestamp in seconds (optional, defaults to now)
            odometer_km: Odometer reading in kilometers (optional)
            battery_level: Main battery level in percent (optional)
            battery_range: Battery range in km (optional)
            fuel_level: Fuel level in percent (optional)
            low_voltage_battery: Low voltage battery level in percent (optional)
            is_charging: Whether vehicle is charging (optional)
            vin: Vehicle Identification Number (optional)
            doors_status: Door status (optional)
            windows_status: Window status (optional)
            is_locked: Whether vehicle is locked (optional)
            custom_attributes: Dict of custom attributes to send (optional)

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.authenticated:
            logger.warning("⚠️  Not authenticated, attempting re-authentication...")
            if not self._authenticate():
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

            # Use current time if not provided (in seconds for OsmAnd)
            if timestamp is None:
                timestamp = int(time.time())

            # Build OsmAnd protocol request
            # OsmAnd protocol: GET /?id={uniqueId}&timestamp={timestamp}[&lat={lat}&lon={lon}]...
            url = f"{self.base_url}/?id={device_id}&timestamp={timestamp}"

            # Add location if available
            if latitude is not None and longitude is not None:
                url += f"&lat={latitude}&lon={longitude}"

            # Add optional location parameters
            if accuracy is not None:
                url += f"&accuracy={accuracy}"
            if altitude is not None:
                url += f"&altitude={altitude}"
            if speed is not None:
                url += f"&speed={speed}"
            if course is not None:
                url += f"&course={course}"
            if odometer_km is not None:
                url += f"&odometer={int(odometer_km * 1000)}"

            # Add battery and charging parameters
            if battery_level is not None:
                url += f"&batt={int(battery_level)}"
            if is_charging is not None:
                url += f"&charge={str(is_charging).lower()}"
            if battery_range is not None:
                url += f"&battery_range={int(battery_range)}"
            if low_voltage_battery is not None:
                url += f"&low_voltage_batt={int(low_voltage_battery)}"

            # Add fuel and vehicle info
            if fuel_level is not None:
                url += f"&fuel_level={int(fuel_level)}"
            if vin is not None:
                url += f"&vin={vin}"

            # Add closure status
            if doors_status is not None:
                url += f"&doors_status={doors_status}"
            if windows_status is not None:
                url += f"&windows_status={windows_status}"
            if is_locked is not None:
                url += f"&is_locked={str(is_locked).lower()}"

            # Add custom attributes
            if custom_attributes:
                for key, value in custom_attributes.items():
                    if value is not None:
                        url += f"&{key}={value}"

            response = self._request_with_reauth('get', url, timeout=10)

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
            logger.warning("Not authenticated with Traccar - attempting re-authentication...")
            if not self._authenticate():
                return []

        try:
            url = f"{self.api_url}/api/devices"
            response = self._request_with_reauth('get', url, timeout=10)

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
            logger.warning("Not authenticated - attempting re-authentication...")
            if not self._authenticate():
                return False, "Not authenticated with Traccar", None

        try:
            url = f"{self.api_url}/api/devices"

            payload = {
                'name': name,
                'uniqueId': unique_id or device_id,
                'category': 'car',
            }

            response = self._request_with_reauth('post', url, json=payload, timeout=10)

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
