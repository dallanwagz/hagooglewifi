"""The Google Wifi Integration for Home Assistant."""
import asyncio

import voluptuous as vol
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.const import ATTR_NAME

from googlewifi import GoogleWifi

from .const import (
    DOMAIN, 
    COORDINATOR, 
    GOOGLEWIFI_API,
    POLLING_INTERVAL,
    REFRESH_TOKEN,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Google WiFi component."""
    hass.data.setdefault(DOMAIN, {})

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Google WiFi component from a config entry."""
    polling_interval = POLLING_INTERVAL

    conf = entry.data

    session = aiohttp_client.async_get_clientsession(hass)

    api = GoogleWifi(refresh_token=conf[REFRESH_TOKEN], session=session)
    
    try:
        await api.connect()
    except ConnectionError as error:
        _LOGGER.debug(f"Google WiFi API: {error}")
        raise PlatformNotReady from error
    except ValueError as error:
        _LOGGER.debug(f"Google WiFi API: {error}")
        raise ConfigEntryNotReady from error

    coordinator = GoogleWiFiUpdater(
        hass,
        api=api,
        name="GoogleWifi",
        polling_interval=polling_interval,
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        GOOGLEWIFI_API: api,
    }

    for component in PLATFORMS:
        _LOGGER.info(f"Setting up platform: {component}")
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

class GoogleWiFiUpdater(DataUpdateCoordinator):
    """Class to manage fetching update data from the Google Wifi API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: str,
        name: str,
        polling_interval: int,
    ):
        """Initialize the global Google Wifi data updater."""
        self.api = api

        super().__init__(
            hass = hass,
            logger = _LOGGER,
            name = name,
            update_interval = timedelta(seconds=polling_interval),
        )

    async def _async_update_data(self):
        """Fetch data from Google Wifi API."""

        try:
            system_data = await self.api.get_systems()
        except ConnectionError as error:
            _LOGGER.info(f"Google Wifi API: {error}")
            raise PlatformNotReady from error
        except ValueError as error:
            _LOGGER.info(f"Google Wifi API: {error}")
            raise ConfigEntryNotReady from error

        return system_data

class GoogleWifiEntity(CoordinatorEntity):
    """Defines the base Google WiFi entity."""

    def __init__(
        self,
        coordinator: GoogleWiFiUpdater,
        name: str,
        icon: str,
        system_id: str,
        item_id: str,
    ):
        """Initialize the Google WiFi Entity."""
        super().__init__(coordinator)

        self._name = name
        self._unique_id = item_id if item_id else system_id
        self._icon = icon
        self._system_id = system_id
        self._item_id = item_id
        self._attrs = {}

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the entity."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the attributes."""
        return self._attrs

    @property
    def device_info(self):
        """Define the device as an individual Google WiFi system."""

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._system_id)},
            ATTR_NAME: f"Google Wifi System {self._system_id}",
            ATTR_MANUFACTURER: "Google",
            ATTR_MODEL: "WiFi",
        }