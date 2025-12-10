"""Sensor platform for integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ConfigEntryRuntimeData
from .coordinator import SchoolCanteenMenuDataCoordinator
from .const import (
    DOMAIN,
    CONF_NAME,
    ATTR_WEEK,
    ATTR_DAY,
    ATTR_DAY_NUMBER,
    ATTR_DATE,
    ATTR_NEXT_DATE,
    ATTR_IS_CLOSED,
    ATTR_MENU_NAME,
)
from .models import DayMenuData, MealData


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[ConfigEntryRuntimeData],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: SchoolCanteenMenuDataCoordinator = entry.runtime_data.coordinator
    name = entry.data[CONF_NAME]
    
    entities = [
        SchoolCanteenMenuWeekSensor(coordinator, entry, name),
        SchoolCanteenMenuTotalWeeksSensor(coordinator, entry, name),
        SchoolCanteenMenuDaySensor(coordinator, entry, name, "today"),
        SchoolCanteenMenuDaySensor(coordinator, entry, name, "next"),
        SchoolCanteenMenuMealSensor(coordinator, entry, name, "today", "main_course", "mdi:pasta"),
        SchoolCanteenMenuMealSensor(coordinator, entry, name, "today", "second_course", "mdi:food-steak"),
        SchoolCanteenMenuMealSensor(coordinator, entry, name, "today", "side", "mdi:baguette"),
        SchoolCanteenMenuMealSensor(coordinator, entry, name, "today", "fruit", "mdi:food-apple"),
        SchoolCanteenMenuMealSensor(coordinator, entry, name, "next", "main_course", "mdi:pasta"),
        SchoolCanteenMenuMealSensor(coordinator, entry, name, "next", "second_course", "mdi:food-steak"),
        SchoolCanteenMenuMealSensor(coordinator, entry, name, "next", "side", "mdi:baguette"),
        SchoolCanteenMenuMealSensor(coordinator, entry, name, "next", "fruit", "mdi:food-apple"),
    ]
    
    async_add_entities(entities)


class SchoolCanteenMenuBaseSensor(CoordinatorEntity[SchoolCanteenMenuDataCoordinator], SensorEntity):
    """Base class for sensors."""

    _unrecorded_attributes = frozenset({
        ATTR_WEEK,
        ATTR_DAY,
        ATTR_DAY_NUMBER,
        ATTR_DATE,
        ATTR_NEXT_DATE, 
        ATTR_IS_CLOSED,
        ATTR_MENU_NAME
    })

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SchoolCanteenMenuDataCoordinator,
        entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=name,
        )

    def _get_today_data(self) -> DayMenuData | None:
        """Get today's menu data as structured object."""
        return self.coordinator.data.today if self.coordinator.data else None

    def _get_next_data(self) -> DayMenuData | None:
        """Get next day's menu data as structured object."""
        return self.coordinator.data.next if self.coordinator.data else None


class SchoolCanteenMenuWeekSensor(SchoolCanteenMenuBaseSensor):
    """Sensor for current week number."""

    _attr_icon = "mdi:calendar-week"
    _attr_translation_key = "current_week"

    def __init__(
        self,
        coordinator: SchoolCanteenMenuDataCoordinator,
        entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, name)
        self._attr_unique_id = f"{entry.entry_id}_current_week"

    @property
    def native_value(self) -> int | None:
        """Return the current week number."""
        today = self._get_today_data()

        return today.week if today else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        today = self._get_today_data()

        return {
            ATTR_DATE: today.date.isoformat(),
            ATTR_DAY: today.day_name,
            ATTR_DAY_NUMBER: today.day_number,
            ATTR_IS_CLOSED: today.is_closed,
            ATTR_MENU_NAME: today.menu_name,
        } if today else {}


class SchoolCanteenMenuTotalWeeksSensor(SchoolCanteenMenuBaseSensor):
    """Sensor for total weeks in the rotation cycle."""

    _attr_icon = "mdi:calendar-refresh"
    _attr_translation_key = "total_weeks"

    def __init__(
        self,
        coordinator: SchoolCanteenMenuDataCoordinator,
        entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, name)
        self._attr_unique_id = f"{entry.entry_id}_total_weeks"

    @property
    def native_value(self) -> int | None:
        """Return the total number of weeks in the rotation cycle."""
        return self.coordinator.data.total_weeks if self.coordinator.data else None


class SchoolCanteenMenuDaySensor(SchoolCanteenMenuBaseSensor):
    """Sensor for current day or next valid day."""

    _attr_icon = "mdi:calendar-today"

    def __init__(
        self,
        coordinator: SchoolCanteenMenuDataCoordinator,
        entry: ConfigEntry,
        name: str,
        time_ref: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, name)
        self._time_ref = time_ref
        self._attr_unique_id = f"{entry.entry_id}_day_{time_ref}"
        self._attr_translation_key = f"day_{time_ref}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self._time_ref == "today":
            today = self._get_today_data()
            return today is not None and not today.is_closed
        else:
            return self._get_next_data() is not None

    @property
    def native_value(self) -> str | None:
        """Return the day name."""
        if self._time_ref == "today":
            today = self._get_today_data()
            return today.day_name if today and not today.is_closed else None
        else:
            next_day = self._get_next_data()
            return next_day.day_name if next_day else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        
        if self._time_ref == "today":
            today = self._get_today_data()
            if not today:
                return {}

            attrs[ATTR_DATE] = today.date.isoformat()
            attrs[ATTR_DAY_NUMBER] = today.day_number
            attrs[ATTR_WEEK] = today.week
            attrs[ATTR_IS_CLOSED] = today.is_closed

            if not today.is_closed:
                attrs[ATTR_MENU_NAME] = today.menu_name
                # Add day attributes from CSV
                attrs.update(today.day_attrs)
        else:
            next_day = self._get_next_data()
            if not next_day:
                return {}

            attrs[ATTR_NEXT_DATE] = next_day.date.isoformat()
            attrs[ATTR_DAY_NUMBER] = next_day.day_number
            attrs[ATTR_WEEK] = next_day.week
            attrs[ATTR_IS_CLOSED] = False
            attrs[ATTR_MENU_NAME] = next_day.menu_name
            # Add day attributes from CSV
            attrs.update(next_day.day_attrs)

        return attrs


class SchoolCanteenMenuMealSensor(SchoolCanteenMenuBaseSensor):
    """Sensor for a meal (main_course/second_course/side)."""

    def __init__(
        self,
        coordinator: SchoolCanteenMenuDataCoordinator,
        entry: ConfigEntry,
        name: str,
        time_ref: str,
        meal_type: str,
        icon: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, name)
        self._time_ref = time_ref
        self._meal_type = meal_type
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{meal_type}_{time_ref}"
        self._attr_translation_key = f"{meal_type}_{time_ref}"

    def _get_meal_data(self) -> MealData | None:
        """Get meal data for this sensor."""
        day_data = self._get_today_data() if self._time_ref == "today" else self._get_next_data()

        if not day_data or day_data.is_closed:
            return None

        return day_data.get_meal_data(self._meal_type)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self._time_ref == "today":
            today = self._get_today_data()
            return today is not None and not today.is_closed
        else:
            return self._get_next_data() is not None

    @property
    def native_value(self) -> str | None:
        """Return the meal value."""
        meal = self._get_meal_data()
        if not meal:
            return None
        return meal.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        
        if self._time_ref == "today":
            day_data = self._get_today_data()
            if not day_data:
                return {}

            attrs[ATTR_DATE] = day_data.date.isoformat()
            attrs[ATTR_DAY] = day_data.day_name
            attrs[ATTR_DAY_NUMBER] = day_data.day_number
            attrs[ATTR_WEEK] = day_data.week
            attrs[ATTR_IS_CLOSED] = day_data.is_closed

            if not day_data.is_closed:
                attrs[ATTR_MENU_NAME] = day_data.menu_name
                # Add day-level attributes
                if day_data.day_attrs:
                    attrs.update(day_data.day_attrs)
                # Add meal-specific attributes
                meal = self._get_meal_data()
                if meal and meal.attributes:
                    attrs.update(meal.attributes)
        else:
            day_data = self._get_next_data()
            if not day_data:
                return {}

            attrs[ATTR_NEXT_DATE] = day_data.date.isoformat()
            attrs[ATTR_DAY] = day_data.day_name
            attrs[ATTR_DAY_NUMBER] = day_data.day_number
            attrs[ATTR_WEEK] = day_data.week
            attrs[ATTR_IS_CLOSED] = False
            attrs[ATTR_MENU_NAME] = day_data.menu_name
            # Add day-level attributes
            if day_data.day_attrs:
                attrs.update(day_data.day_attrs)
            # Add meal-specific attributes
            meal = self._get_meal_data()
            if meal and meal.attributes:
                attrs.update(meal.attributes)

        return attrs
