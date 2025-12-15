from typing import Any

import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .coordinator import SchoolCanteenMenuDataCoordinator

from .const import (
    DOMAIN,
    CONF_NAME,
)

_LOGGER = logging.getLogger(__name__)

@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the logbook websocket API."""
    websocket_api.async_register_command(hass, ws_get_menus)

@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/get_menus",
        vol.Optional("device_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_menus(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle get menus websocket command."""
    msg_id: int = msg["id"]
    device_id = msg.get("device_id")

    device_registry = dr.async_get(hass)

    result = {"entries": []}

    for device in list(device_registry.devices.values()):
        # Filter by device_id if requested
        if device_id and device_id != device.id:
            _LOGGER.debug("Skipping device [%s] (not matching device_id)", device.name)
            continue

        if (
            (config_entry := hass.config_entries.async_get_entry(device.primary_config_entry))
            and config_entry.domain != DOMAIN
        ):
            continue

        # Get coordinator for this config entry
        coordinator: SchoolCanteenMenuDataCoordinator = config_entry.runtime_data.coordinator

        # Build menus data with serializable dates
        menus = []
        for menu_info in coordinator.menus:
            menus.append({
                "id": menu_info.menu_id,
                "name": menu_info.menu_name,
                "effective_date": menu_info.effective_date,
                "total_weeks": menu_info.total_weeks,
                "data": menu_info.menu_data,
            })

        # Sort menus by effective date
        menus.sort(key=lambda m: m["effective_date"])

        # Build closure periods
        closure_periods = []
        for period in coordinator.closure_periods:
            closure_periods.append({
                "start": period.start.isoformat(),
                "end": period.end.isoformat(),
            })

        # Build restarts
        restarts = []
        for date_str, week in coordinator.restarts.items():
            restarts.append({
                "date": date_str,
                "week": week,
            })
        restarts.sort(key=lambda r: r["date"])

        result["entries"].append({
            "device_id": device.id,
            "name": config_entry.data.get(CONF_NAME),
            "start_date": coordinator.start_date,
            "start_week": coordinator.start_week,
            "menus": menus,
            "closure_periods": closure_periods,
            "restarts": restarts,
        })

    connection.send_result(msg_id, result)
