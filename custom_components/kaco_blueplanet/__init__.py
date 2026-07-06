from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN, CONF_HOST, CONF_SERIAL, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from datetime import timedelta
import aiohttp
import logging

from .sensor import async_setup_entry as sensor_setup_entry, KacoCoordinator
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    host = entry.data[CONF_HOST]
    serial = entry.data[CONF_SERIAL]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    _LOGGER.info(f"Using scan interval: {scan_interval} seconds")
    coordinator = KacoCoordinator(hass, host, serial, scan_interval)

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Listener für Options-Änderungen → reload Integration
    entry.async_on_unload(entry.add_update_listener(reload_entry))

    """Forward setup to sensor platform."""
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration."""
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])

async def reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
