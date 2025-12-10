"""Storage management for School Canteen Menu integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import ulid as ulid_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}"


class SchoolCanteenMenuStorage:
    """Manage storage for School Canteen Menu config entries."""

    def __init__(self, hass: HomeAssistant, storage_id: str | None) -> None:
        """Initialize storage."""
        self.hass = hass
        self.storage_id = storage_id or ulid_util.ulid_now()
        self._store = Store[dict[str, Any]](
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}.{self.storage_id}",
            atomic_writes=True,
        )
        self._data: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        """Load data from storage."""
        data = await self._store.async_load()
        if data is None:
            self._data = {}
        else:
            self._data = data
        _LOGGER.debug("Loaded storage data %s: %s keys", self.storage_id, len(self._data))
        return self._data

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save data to storage."""
        self._data = data
        await self._store.async_save(self._data)
        _LOGGER.debug("Saved storage data %s: %s keys", self.storage_id, len(self._data))

    async def async_remove(self) -> None:
        """Remove storage file."""
        await self._store.async_remove()
        self._data = {}
        _LOGGER.debug("Removed storage data %s", self.storage_id)

    @property
    def data(self) -> dict[str, Any]:
        """Get current data."""
        return self._data

    async def async_update(self, updates: dict[str, Any]) -> None:
        """Update specific keys in storage."""
        self._data.update(updates)
        await self._store.async_save(self._data)
        _LOGGER.debug("Updated storage data %s", self.storage_id)

