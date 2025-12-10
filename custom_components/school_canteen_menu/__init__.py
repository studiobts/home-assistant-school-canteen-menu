"""The School Canteen Menu integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .coordinator import SchoolCanteenMenuDataCoordinator
from .const import (
    DOMAIN,
    CONF_STORAGE_ID,
    CONF_START_DATE,
    CONF_START_WEEK,
    CONF_MENUS,
    CONF_MENU_NAME,
    CONF_MENU_DATA,
    CONF_TOTAL_WEEKS,
    CONF_EFFECTIVE_DATE,
    CONF_CLOSURE_PERIODS,
    CONF_RESTARTS,
    WEEKDAY_TO_CSV,
    WEEKDAY_NAMES,
)
from .storage import SchoolCanteenMenuStorage

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

@dataclass
class ConfigEntryRuntimeData:
    """Holds runtime data for config entry."""

    coordinator: SchoolCanteenMenuDataCoordinator
    storage: SchoolCanteenMenuStorage

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    websocket_api.async_setup(hass)

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry[ConfigEntryRuntimeData]) -> bool:
    """Set up from a config entry."""
    entry_storage = SchoolCanteenMenuStorage(hass, entry.data.get(CONF_STORAGE_ID))
    entry_coordinator = SchoolCanteenMenuDataCoordinator(hass, entry, entry_storage)

    await entry_coordinator.async_setup()
    await entry_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ConfigEntryRuntimeData(entry_coordinator, entry_storage)
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry[ConfigEntryRuntimeData]) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry[ConfigEntryRuntimeData]) -> None:
    """Remove a config entry and clean up storage."""
    await entry.runtime_data.storage.async_remove()
