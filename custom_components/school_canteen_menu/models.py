"""Data models for School Canteen Menu integration."""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from .const import (
    CONF_CLOSURE_PERIOD_END,
    CONF_CLOSURE_PERIOD_START,
    CONF_EFFECTIVE_DATE,
    CONF_MENU_DATA,
    CONF_MENU_NAME,
    CONF_TOTAL_WEEKS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class MealData:
    """Represents a single meal."""

    value: str | None = None
    attributes: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict | None) -> "MealData | None":
        """Create MealData from dictionary."""
        if not data:
            return None
        
        # Extract value and all other attributes
        value = data.get("value")
        attributes = {k: v for k, v in data.items() if k != "value"}
        
        return cls(
            value=value,
            attributes=attributes if attributes else None,
        )

    def to_dict(self) -> dict[str, Any] | None:
        """Convert to dictionary."""
        if not self.value:
            return None
        result = {"value": self.value}
        if self.attributes:
            result.update(self.attributes)
        return result


@dataclass
class DayMenuData:
    """Represents a single day's menu."""

    date: date
    week: int
    day_number: int
    day_name: str
    menu_name: str
    is_closed: bool
    day_attrs: dict[str, Any]
    main_course: MealData | None
    second_course: MealData | None
    side: MealData | None
    fruit: MealData | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for coordinator data."""
        return {
            "date": self.date.isoformat(),
            "week": self.week,
            "day_number": self.day_number,
            "day_name": self.day_name,
            "menu_name": self.menu_name,
            "is_closed": self.is_closed,
            "day_attrs": self.day_attrs,
            "main_course": self.main_course.to_dict() if self.main_course else None,
            "second_course": self.second_course.to_dict() if self.second_course else None,
            "side": self.side.to_dict() if self.side else None,
            "fruit": self.fruit.to_dict() if self.fruit else None,
        }

    def get_meal_data(self, meal_type: str) -> MealData | None:
        return getattr(self, meal_type)


@dataclass
class MenuInfo:
    """Represents a menu configuration."""

    menu_id: str
    menu_name: str
    effective_date: date
    total_weeks: int
    menu_data: dict[str, Any]

    @classmethod
    def from_config(cls, menu_id: str, menu_info: dict) -> "MenuInfo":
        """Create MenuInfo from config entry data."""
        return cls(
            menu_id=menu_id,
            menu_name=menu_info.get(CONF_MENU_NAME),
            effective_date=date.fromisoformat(menu_info[CONF_EFFECTIVE_DATE]),
            total_weeks=menu_info.get(CONF_TOTAL_WEEKS, 4),
            menu_data=menu_info.get(CONF_MENU_DATA, {}),
        )


@dataclass
class ClosurePeriod:
    """Represents a closure period."""

    start: date
    end: date

    @classmethod
    def from_dict(cls, data: dict) -> "ClosurePeriod | None":
        """Create ClosurePeriod from dictionary."""
        try:
            return cls(
                start=date.fromisoformat(data[CONF_CLOSURE_PERIOD_START]),
                end=date.fromisoformat(data[CONF_CLOSURE_PERIOD_END]),
            )
        except (ValueError, KeyError) as e:
            _LOGGER.warning("Invalid closure period: %s", e)
            return None

    def contains(self, check_date: date) -> bool:
        """Check if date is within this closure period."""
        return self.start <= check_date <= self.end


@dataclass
class CoordinatorData:
    """Represents the coordinator's data structure."""

    today: DayMenuData | None
    next: DayMenuData | None
    total_weeks: int

