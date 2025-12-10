import logging
from datetime import date, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_CLOSURE_PERIODS,
    CONF_MENUS,
    CONF_RESTARTS,
    CONF_START_DATE,
    CONF_START_WEEK,
    WEEKDAY_TO_CSV,
    WEEKDAY_NAMES,
)
from .models import (
    ClosurePeriod,
    CoordinatorData,
    DayMenuData,
    MealData,
    MenuInfo,
)
from .storage import SchoolCanteenMenuStorage

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Update interval - once per hour is enough for a daily menu
UPDATE_INTERVAL = timedelta(hours=1)

class SchoolCanteenMenuDataCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinator for data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, storage: SchoolCanteenMenuStorage) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self._storage = storage

        # These will be loaded from storage in async_setup
        self._start_date: date | None = None
        self._start_week: int = 1

        # Load menus (sorted by effective date)
        self._menus: list[MenuInfo] = []

        # Load closure periods and restarts
        self._closure_periods: list[ClosurePeriod] = []
        self._restarts: dict[date, int] = {}

    async def async_setup(self) -> None:
        """Set up the coordinator - load data from storage."""
        await self._storage.async_load()

        storage_data = self._storage.data

        # Get start date and week from storage
        self._start_date = date.fromisoformat(storage_data[CONF_START_DATE])
        self._start_week = storage_data[CONF_START_WEEK]

        # Load menus
        self._load_menus()

        # Load closure periods and restarts
        self._load_options()

    def _load_menus(self) -> None:
        """Load menus from storage."""
        menus_data = self._storage.data.get(CONF_MENUS, {})

        self._menus = []
        for menu_id, menu_info in menus_data.items():
            self._menus.append(MenuInfo.from_config(menu_id, menu_info))

        # Sort by effective date
        self._menus.sort(key=lambda m: m.effective_date)

    def _load_options(self) -> None:
        """Load options from storage."""
        storage_data = self._storage.data

        closure_periods_data = storage_data.get(CONF_CLOSURE_PERIODS, [])
        restarts_data = storage_data.get(CONF_RESTARTS, {})

        # Parse closure periods
        self._closure_periods = []
        for period_data in closure_periods_data:
            period = ClosurePeriod.from_dict(period_data)
            if period:
                self._closure_periods.append(period)

        # Parse restart dates
        self._restarts = {}
        for date_str, week in restarts_data.items():
            try:
                self._restarts[date.fromisoformat(date_str)] = week
            except ValueError:
                _LOGGER.warning("Invalid restart date: %s", date_str)

    def _get_menu_for_date(self, check_date: date) -> MenuInfo | None:
        """Get the active menu for a specific date."""
        active_menu = None
        for menu in self._menus:
            if menu.effective_date <= check_date:
                active_menu = menu
            else:
                break
        return active_menu

    def _is_closed(self, check_date: date) -> bool:
        """Check if the school is closed on a given date."""
        # Weekends are always closed
        if check_date.weekday() >= 5:
            return True

        # Check closure periods
        for period in self._closure_periods:
            if period.contains(check_date):
                return True

        return False

    def _get_current_week(self, check_date: date) -> int:
        """Calculate the current week number (1 to total_weeks) for a given date.

        The week calculation is based on calendar weeks from the start date,
        regardless of closures or number of available days per week.
        Weeks advance on Monday (weekday 0).
        """
        menu = self._get_menu_for_date(check_date)
        if not menu:
            return 1

        total_weeks = menu.total_weeks

        effective_start_date = self._start_date
        effective_start_week = self._start_week

        # Find the most recent restart before or on check_date
        sorted_restarts = sorted(self._restarts.keys())
        for restart_date in sorted_restarts:
            if restart_date <= check_date:
                effective_start_date = restart_date
                effective_start_week = self._restarts[restart_date]
            else:
                break

        # Find the Monday of the week for both dates
        # This ensures we count complete weeks from Monday to Sunday
        start_monday = effective_start_date - timedelta(days=effective_start_date.weekday())
        check_monday = check_date - timedelta(days=check_date.weekday())

        # Calculate the number of complete weeks between the two Mondays
        weeks_diff = (check_monday - start_monday).days // 7

        # Calculate the current week in the cycle (1 to total_weeks)
        current_week = ((effective_start_week - 1 + weeks_diff) % total_weeks) + 1

        _LOGGER.debug(
            "Week calculation for %s: start_date=%s, start_week=%s, "
            "start_monday=%s, check_monday=%s, weeks_diff=%d, current_week=%d",
            check_date, effective_start_date, effective_start_week,
            start_monday, check_monday, weeks_diff, current_week
        )

        return current_week

    def _get_day_data(self, check_date: date) -> dict:
        """Get day-level data (attributes) for a specific date."""
        if self._is_closed(check_date):
            return {}

        menu = self._get_menu_for_date(check_date)
        if not menu:
            return {}

        week = self._get_current_week(check_date)
        day_number = WEEKDAY_TO_CSV[check_date.weekday()]

        week_data = menu.menu_data.get(str(week), {})
        day_data = week_data.get(str(day_number))

        if day_data:
            return day_data.get("day_attrs", {})
        return {}

    def _get_meal_for_date(self, check_date: date, meal_type: str) -> MealData | None:
        """Get meal data for a specific date and meal type."""
        if self._is_closed(check_date):
            return None

        menu = self._get_menu_for_date(check_date)
        if not menu:
            return None

        week = self._get_current_week(check_date)
        day_number = WEEKDAY_TO_CSV[check_date.weekday()]

        week_data = menu.menu_data.get(str(week), {})
        day_data = week_data.get(str(day_number))

        if day_data:
            meal_dict = day_data.get(meal_type)
            return MealData.from_dict(meal_dict)
        return None

    def _get_menu_name_for_date(self, check_date: date) -> str:
        """Get the menu name for a specific date."""
        menu = self._get_menu_for_date(check_date)
        if menu:
            return menu.menu_name
        return "Unknown"

    def _get_next_valid_date(self, from_date: date) -> date | None:
        """Get the next valid school day after the given date."""
        check_date = from_date + timedelta(days=1)
        max_days = 30

        for _ in range(max_days):
            if not self._is_closed(check_date):
                return check_date
            check_date += timedelta(days=1)

        return None

    def _build_day_menu_data(self, check_date: date) -> DayMenuData:
        """Build DayMenuData for a specific date."""
        is_closed = self._is_closed(check_date)
        week = self._get_current_week(check_date)
        day_number = WEEKDAY_TO_CSV[check_date.weekday()]
        day_name = WEEKDAY_NAMES.get(day_number, "Unknown")
        menu_name = self._get_menu_name_for_date(check_date)
        day_attrs = self._get_day_data(check_date) if not is_closed else {}

        main_course = None if is_closed else self._get_meal_for_date(check_date, "main_course")
        second_course = None if is_closed else self._get_meal_for_date(check_date, "second_course")
        side = None if is_closed else self._get_meal_for_date(check_date, "side")
        fruit = None if is_closed else self._get_meal_for_date(check_date, "fruit")

        return DayMenuData(
            date=check_date,
            week=week,
            day_number=day_number,
            day_name=day_name,
            menu_name=menu_name,
            is_closed=is_closed,
            day_attrs=day_attrs,
            main_course=main_course,
            second_course=second_course,
            side=side,
            fruit=fruit,
        )

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from the coordinator."""
        today = date.today()
        next_valid = self._get_next_valid_date(today)

        # Get current menu info
        menu = self._get_menu_for_date(today)
        total_weeks = menu.total_weeks if menu else 4

        # Build structured data for today
        today_data = self._build_day_menu_data(today)

        # Build structured data for the next valid day
        next_data = self._build_day_menu_data(next_valid) if next_valid else None

        # Create coordinator data
        return CoordinatorData(
            today=today_data,
            next=next_data,
            total_weeks=total_weeks,
        )

    @property
    def menus(self) -> list[MenuInfo]:
        """Return list of all menus."""
        return self._menus

    @property
    def start_date(self) -> date:
        """Return start date."""
        return self._start_date

    @property
    def start_week(self) -> int:
        """Return start week."""
        return self._start_week

    @property
    def closure_periods(self) -> list[ClosurePeriod]:
        """Return closure periods."""
        return self._closure_periods

    @property
    def restarts(self) -> dict[date, int]:
        """Return restart dates."""
        return self._restarts