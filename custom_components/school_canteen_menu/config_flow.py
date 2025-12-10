"""Config flow for School Canteen Menu integration."""
from __future__ import annotations

import copy
import csv
import io
import logging
import uuid
from datetime import date
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    DateSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CLOSURE_PERIODS,
    CONF_EFFECTIVE_DATE,
    CONF_MENU_CSV,
    CONF_MENU_DATA,
    CONF_MENU_NAME,
    CONF_MENUS,
    CONF_NAME,
    CONF_RESTARTS,
    CONF_START_DATE,
    CONF_START_WEEK,
    CONF_STORAGE_ID,
    CONF_TOTAL_WEEKS,
    CSV_COL_FRUIT,
    CSV_COL_MAIN_COURSE,
    CSV_COL_SECOND_COURSE,
    CSV_COL_SIDE,
    CSV_COL_WEEK_DAY,
    CSV_COL_WEEK_NUMBER,
    DOMAIN, CONF_CLOSURE_PERIOD_START, CONF_CLOSURE_PERIOD_END,
)
from .storage import SchoolCanteenMenuStorage

_LOGGER = logging.getLogger(__name__)

# Options flow action choices
ACTION_CHOICE = "action"
ACTION_ADD_CLOSURE_DATE = "add_closure_date"
ACTION_ADD_CLOSURE_PERIOD = "add_closure_period"
ACTION_DELETE_CLOSURE = "delete_closure"
ACTION_ADD_RESTART = "add_restart"
ACTION_DELETE_RESTART = "delete_restart"
ACTION_EDIT_MENU = "edit_menu"
ACTION_ADD_MENU = "add_menu"


INPUT_CLOSURE_DATE = "closure_date"
INPUT_CLOSURES_TO_REMOVE = "closures_to_remove"
INPUT_RESTART_DATE = "restart_date"
INPUT_RESTART_WEEK = "restart_week"
INPUT_RESTARTS_TO_REMOVE = "restarts_to_remove"
INPUT_MENU_ID = "menu_id"


def parse_csv_menu(csv_content: str) -> tuple[dict, int]:
    """Parse CSV content into the menu data structure.
    
    Expected CSV format (fixed column positions):
    week_number, week_day, [day_attr1, day_attr2, ...], main_course, [main_attr1, ...], second_course, [second_attr1, ...], side, [side_attr1, ...], fruit, [fruit_attr1, ...]
    
    - week_number: 1 to N (any number of weeks)
    - week_day: 1-7 (1=Monday, 7=Sunday)
    - Columns between week_day and main_course are day attributes
    - Columns between main_course and second_course are main_course attributes
    - Columns between second_course and side are second_course attributes
    - Columns between side and fruit are side attributes
    - Columns after fruit are fruit attributes
    
    Returns:
        Tuple of (menu_data dict, total_weeks int)
    """
    menu_data = {}
    max_week = 0
    
    reader = csv.reader(io.StringIO(csv_content))
    
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("Empty CSV file")
    
    # Normalize header names
    header = [h.strip().lower() for h in header]
    
    # Find required column indices
    try:
        week_number_idx = header.index(CSV_COL_WEEK_NUMBER)
        week_day_idx = header.index(CSV_COL_WEEK_DAY)
        main_course_idx = header.index(CSV_COL_MAIN_COURSE)
        second_course_idx = header.index(CSV_COL_SECOND_COURSE)
        side_idx = header.index(CSV_COL_SIDE)
        fruit_idx = header.index(CSV_COL_FRUIT)
    except ValueError as e:
        raise ValueError(f"Missing required column: {e}")
    
    # Validate column order
    if not (week_number_idx < week_day_idx < main_course_idx < second_course_idx < side_idx < fruit_idx):
        raise ValueError(
            f"Columns must be in order: {CSV_COL_WEEK_NUMBER}, {CSV_COL_WEEK_DAY}, "
            f"{CSV_COL_MAIN_COURSE}, {CSV_COL_SECOND_COURSE}, {CSV_COL_SIDE}, {CSV_COL_FRUIT}"
        )
    
    # Extract attribute column names
    day_attrs = header[week_day_idx + 1:main_course_idx]
    main_course_attrs = header[main_course_idx + 1:second_course_idx]
    second_course_attrs = header[second_course_idx + 1:side_idx]
    side_attrs = header[side_idx + 1:fruit_idx]
    fruit_attrs = header[fruit_idx + 1:]

    _LOGGER.debug("Day attributes: %s", day_attrs)
    _LOGGER.debug("Main course attributes: %s", main_course_attrs)
    _LOGGER.debug("Second course attributes: %s", second_course_attrs)
    _LOGGER.debug("Side attributes: %s", side_attrs)
    _LOGGER.debug("Fruit attributes: %s", fruit_attrs)

    # Process data rows
    for row_num, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        
        # Validate row length
        min_required = max(week_number_idx, week_day_idx, main_course_idx, second_course_idx, side_idx, fruit_idx) + 1
        if len(row) < min_required:
            _LOGGER.warning("Row %d has insufficient columns, skipping", row_num)
            continue
        
        # Parse week number
        try:
            week = int(row[week_number_idx].strip())
            if week < 1:
                _LOGGER.warning("Row %d has invalid week %d (must be >= 1), skipping", row_num, week)
                continue
            # Track maximum week number
            if week > max_week:
                max_week = week
        except ValueError:
            _LOGGER.warning("Row %d has invalid week value, skipping", row_num)
            continue
        
        # Parse day number
        try:
            day = int(row[week_day_idx].strip())
            if day < 1 or day > 7:
                _LOGGER.warning("Row %d has invalid day %d (must be 1-7), skipping", row_num, day)
                continue
        except ValueError:
            _LOGGER.warning("Row %d has invalid day value, skipping", row_num)
            continue
        
        # Extract day attributes
        day_attrs_data = {}
        for i, attr_name in enumerate(day_attrs):
            attr_idx = week_day_idx + 1 + i
            if len(row) > attr_idx and row[attr_idx].strip():
                day_attrs_data[attr_name] = row[attr_idx].strip()
        
        # Extract meal values
        main_course_value = row[main_course_idx].strip() if len(row) > main_course_idx else ""
        second_course_value = row[second_course_idx].strip() if len(row) > second_course_idx else ""
        side_value = row[side_idx].strip() if len(row) > side_idx else ""
        fruit_value = row[fruit_idx].strip() if len(row) > fruit_idx else ""

        # Helper function to build course data with attributes
        def build_course_data(value: str | None, base_idx: int, attrs: list[str]) -> dict[str, str] | None:
            """Build a course data dictionary with attributes from row."""
            if not value:
                return None
            data = {"value": value}
            for j, course_attr_name in enumerate(attrs):
                course_attr_idx = base_idx + 1 + j
                if len(row) > course_attr_idx and row[course_attr_idx].strip():
                    data[course_attr_name] = row[course_attr_idx].strip()

            return data

        # Build course data with attributes
        main_course_data = build_course_data(main_course_value, main_course_idx, main_course_attrs)
        second_course_data = build_course_data(second_course_value, second_course_idx, second_course_attrs)
        side_data = build_course_data(side_value, side_idx, side_attrs)
        fruit_data = build_course_data(fruit_value, fruit_idx, fruit_attrs)

        # Store in menu_data structure
        week_str = str(week)
        day_str = str(day)
        
        if week_str not in menu_data:
            menu_data[week_str] = {}
        
        menu_data[week_str][day_str] = {
            "day_attrs": day_attrs_data,
            "main_course": main_course_data,
            "second_course": second_course_data,
            "side": side_data,
            "fruit": fruit_data,
        }
    
    # Return menu data and total number of weeks
    total_weeks = max_week if max_week > 0 else 1
    return menu_data, total_weeks


class SchoolCanteenMenuAsiloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._name: str = ""
        self._start_date: str = ""
        self._start_week: int = 1
        self._menu_name: str = ""
        self._menu_data: dict = {}
        self._total_weeks: int = 4

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._name = user_input[CONF_NAME]
            self._menu_name = user_input.get(CONF_MENU_NAME)
            
            # Validate start date
            try:
                date.fromisoformat(user_input[CONF_START_DATE])
                self._start_date = user_input[CONF_START_DATE]
            except ValueError:
                errors[CONF_START_DATE] = "invalid_date"
            
            # Validate start week (must be >= 1, upper limit validated after CSV upload)
            if user_input[CONF_START_WEEK] < 1:
                errors[CONF_START_WEEK] = "invalid_week"
            else:
                self._start_week = int(user_input[CONF_START_WEEK])
            
            if not errors:
                return await self.async_step_upload()

        today = date.today().isoformat()

        data_schema = vol.Schema({
            vol.Required(CONF_NAME, default="School Canteen Menu"): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_START_DATE, default=today): DateSelector(),
            vol.Required(CONF_START_WEEK, default=1): NumberSelector(
                NumberSelectorConfig(min=1, max=52, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_MENU_NAME, default="Initial Menu"): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_upload(self, user_input: dict[str, Any] | None = None):
        """Handle the CSV upload step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            csv_content = user_input.get(CONF_MENU_CSV, "")

            if csv_content:
                try:
                    self._menu_data, self._total_weeks = parse_csv_menu(csv_content)
                    
                    if not self._menu_data:
                        errors[CONF_MENU_CSV] = "invalid_csv"
                    elif self._start_week > self._total_weeks:
                        # Start week cannot exceed total weeks in CSV
                        errors[CONF_MENU_CSV] = "start_week_exceeds_total"
                except Exception as ex:
                    _LOGGER.error("Error parsing CSV: %s", ex)
                    errors[CONF_MENU_CSV] = "invalid_csv"

            if not errors:
                await self.async_set_unique_id(f"{DOMAIN}_{self._name}")
                self._abort_if_unique_id_configured()

                # Create storage and save initial data
                storage = SchoolCanteenMenuStorage(self.hass, None)
                await storage.async_save({
                    CONF_START_DATE: self._start_date,
                    CONF_START_WEEK: self._start_week,
                    CONF_MENUS: {
                        str(uuid.uuid4()): {
                            CONF_MENU_NAME: self._menu_name,
                            CONF_EFFECTIVE_DATE: self._start_date,
                            CONF_MENU_DATA: self._menu_data,
                            CONF_TOTAL_WEEKS: self._total_weeks,
                        }
                    },
                    CONF_CLOSURE_PERIODS: [],
                    CONF_RESTARTS: {},
                })

                # Create config entry with storage ID
                return self.async_create_entry(
                    title=self._name,
                    data={
                        CONF_NAME: self._name,
                        CONF_STORAGE_ID: storage.storage_id,
                    },
                )

        data_schema = vol.Schema({
            CONF_MENU_CSV: TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.TEXT,
                    multiline=True,
                )
            ),
        })

        return self.async_show_form(
            step_id="upload",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options' flow."""
        return SchoolCanteenMenuOptionsFlow(config_entry)


class SchoolCanteenMenuOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options' flow."""
        self._config_entry = config_entry
        self._selected_menu_id: str | None = None
        self._new_menu_data: dict = {}
        self._new_total_weeks: int = 0
        self._storage: SchoolCanteenMenuStorage | None = None

    async def _get_storage(self) -> SchoolCanteenMenuStorage:
        """Get storage instance and load data."""
        if self._storage is None:
            self._storage = SchoolCanteenMenuStorage(self.hass, self._config_entry.data.get(CONF_STORAGE_ID, self._config_entry.entry_id))
            await self._storage.async_load()
        return self._storage

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Handle initial options step - show action selection."""
        self._storage = await self._get_storage()

        if user_input is not None:
            action = user_input.get(ACTION_CHOICE)
            
            if action == ACTION_ADD_CLOSURE_DATE:
                return await self.async_step_add_closure_date()
            elif action == ACTION_ADD_CLOSURE_PERIOD:
                return await self.async_step_add_closure_period()
            elif action == ACTION_DELETE_CLOSURE:
                return await self.async_step_delete_closure()
            elif action == ACTION_ADD_RESTART:
                return await self.async_step_add_restart()
            elif action == ACTION_DELETE_RESTART:
                return await self.async_step_delete_restart()
            elif action == ACTION_EDIT_MENU:
                return await self.async_step_edit_menu()
            elif action == ACTION_ADD_MENU:
                return await self.async_step_add_menu()

        data_schema = vol.Schema({
            vol.Required(ACTION_CHOICE, default=None): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=ACTION_ADD_CLOSURE_DATE, label="Add Closure Date"),
                        SelectOptionDict(value=ACTION_ADD_CLOSURE_PERIOD, label="Add Closure Period"),
                        SelectOptionDict(value=ACTION_DELETE_CLOSURE, label="Delete Closure"),
                        SelectOptionDict(value=ACTION_ADD_RESTART, label="Add Restart Date"),
                        SelectOptionDict(value=ACTION_DELETE_RESTART, label="Delete Restart Date"),
                        SelectOptionDict(value=ACTION_EDIT_MENU, label="Edit Menu"),
                        SelectOptionDict(value=ACTION_ADD_MENU, label="Add New menu"),
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            last_step=False,
        )

    async def async_step_add_closure_date(self, user_input: dict[str, Any] | None = None):
        """Handle adding a single closure date."""
        errors: dict[str, str] = {}

        if user_input is not None:
            closure_date = user_input.get(INPUT_CLOSURE_DATE)

            try:
                date.fromisoformat(closure_date)
            except ValueError:
                errors[INPUT_CLOSURE_DATE] = "invalid_date"
                # Check if the closure date already exists
                closure_periods = self._storage.data.get(CONF_CLOSURE_PERIODS, [])
                for period in closure_periods:
                    start = period[CONF_CLOSURE_PERIOD_START]
                    end = period[CONF_CLOSURE_PERIOD_END]
                    # Check if the date falls within an existing period or matches exactly
                    if start <= closure_date <= end:
                        errors[INPUT_CLOSURE_DATE] = "closure_date_already_configured"
                        break

            if not errors:
                # Add as a period with the same start and end date
                closure_periods = list(self._storage.data.get(CONF_CLOSURE_PERIODS, []))
                closure_periods.append({
                    CONF_CLOSURE_PERIOD_START: closure_date,
                    CONF_CLOSURE_PERIOD_END: closure_date,
                })
                await self._storage.async_update({CONF_CLOSURE_PERIODS: closure_periods})
                return self.async_create_entry(title="", data={})

        data_schema = vol.Schema({
            vol.Required(INPUT_CLOSURE_DATE): DateSelector(),
        })

        return self.async_show_form(
            step_id="add_closure_date",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_add_closure_period(self, user_input: dict[str, Any] | None = None):
        """Handle adding a closure period."""
        errors: dict[str, str] = {}

        if user_input is not None:
            start_date = user_input.get(CONF_CLOSURE_PERIOD_START)
            end_date = user_input.get(CONF_CLOSURE_PERIOD_END)

            try:
                start = date.fromisoformat(start_date)
            except ValueError:
                start = None
                errors[CONF_CLOSURE_PERIOD_START] = "invalid_date"

            try:
                end = date.fromisoformat(end_date)
            except ValueError:
                end = None
                errors[CONF_CLOSURE_PERIOD_END] = "invalid_date"

            if not errors and start > end:
                errors[CONF_CLOSURE_PERIOD_END] = "end_before_start"

            if not errors:
                # Check for overlapping periods
                closure_periods = self._storage.data.get(CONF_CLOSURE_PERIODS, [])
                for period in closure_periods:
                    existing_start = date.fromisoformat(period[CONF_CLOSURE_PERIOD_START])
                    existing_end = date.fromisoformat(period[CONF_CLOSURE_PERIOD_END])

                    # Check if a new period overlaps with an existing period
                    if not (end < existing_start or start > existing_end):
                        errors["base"] = "closure_period_overlapping"
                        break

            if not errors:
                closure_periods = list(self._storage.data.get(CONF_CLOSURE_PERIODS, []))
                closure_periods.append({
                    CONF_CLOSURE_PERIOD_START: start_date,
                    CONF_CLOSURE_PERIOD_END: end_date,
                })
                await self._storage.async_update({CONF_CLOSURE_PERIODS: closure_periods})
                return self.async_create_entry(title="", data={})

        data_schema = vol.Schema({
            vol.Required(CONF_CLOSURE_PERIOD_START): DateSelector(),
            vol.Required(CONF_CLOSURE_PERIOD_END): DateSelector(),
        })

        return self.async_show_form(
            step_id="add_closure_period",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_delete_closure(self, user_input: dict[str, Any] | None = None):
        """Handle deleting closure periods."""
        closure_periods = self._storage.data.get(CONF_CLOSURE_PERIODS, [])

        if not closure_periods:
            return self.async_abort(reason="no_closures")

        if user_input is not None:
            to_remove = user_input.get(INPUT_CLOSURES_TO_REMOVE, [])

            if to_remove:
                new_periods = [
                    p for i, p in enumerate(closure_periods)
                    if str(i) not in to_remove
                ]
                await self._storage.async_update({CONF_CLOSURE_PERIODS: new_periods})
                return self.async_create_entry(title="", data={})

            return self.async_abort(reason="no_selection")

        # Build options for closure periods
        closure_options = []
        for i, period in enumerate(closure_periods):
            start = period[CONF_CLOSURE_PERIOD_START]
            end = period[CONF_CLOSURE_PERIOD_END]
            if start == end:
                label = start
            else:
                label = f"{start} - {end}"

            closure_options.append(SelectOptionDict(value=str(i), label=label))

        data_schema = vol.Schema({
            vol.Required(INPUT_CLOSURES_TO_REMOVE, default=None): SelectSelector(
                SelectSelectorConfig(
                    options=closure_options,
                    mode=SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            )
        })

        return self.async_show_form(
            step_id="delete_closure",
            data_schema=data_schema,
        )

    async def async_step_add_restart(self, user_input: dict[str, Any] | None = None):
        """Handle adding a new restart date."""
        errors: dict[str, str] = {}

        # Get max total weeks from all menus
        menus = self._storage.data.get(CONF_MENUS, {})
        max_weeks = max(
            (m.get(CONF_TOTAL_WEEKS, 4) for m in menus.values()),
            default=4
        )

        if user_input is not None:
            restart_date = user_input.get(INPUT_RESTART_DATE)
            restart_week = user_input.get(INPUT_RESTART_WEEK, 1)

            try:
                date.fromisoformat(restart_date)
            except ValueError:
                errors[INPUT_RESTART_DATE] = "invalid_date"

            if restart_week < 1 or restart_week > max_weeks:
                errors[INPUT_RESTART_WEEK] = "invalid_week"

            # Check if the restart date already exists
            if not errors:
                restarts = self._storage.data.get(CONF_RESTARTS, {})
                if restart_date in restarts:
                    errors[INPUT_RESTART_DATE] = "restart_date_already_configured"

            if not errors:
                restarts = dict(self._storage.data.get(CONF_RESTARTS, {}))
                restarts[restart_date] = int(restart_week)
                await self._storage.async_update({CONF_RESTARTS: restarts})
                return self.async_create_entry(title="", data={})

        data_schema = vol.Schema({
            vol.Required(INPUT_RESTART_DATE, default=None): DateSelector(),
            vol.Required(INPUT_RESTART_WEEK, default=1): NumberSelector(
                NumberSelectorConfig(min=1, max=max_weeks, step=1, mode=NumberSelectorMode.BOX)
            ),
        })

        return self.async_show_form(
            step_id="add_restart",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_delete_restart(self, user_input: dict[str, Any] | None = None):
        """Handle deleting restart dates."""
        restarts = self._storage.data.get(CONF_RESTARTS, {})

        if not restarts:
            return self.async_abort(reason="no_restarts")

        if user_input is not None:
            to_remove = user_input.get(INPUT_RESTARTS_TO_REMOVE, [])

            if to_remove:
                new_restarts = {
                    d: w for d, w in restarts.items()
                    if d not in to_remove
                }
                await self._storage.async_update({CONF_RESTARTS: new_restarts})
                return self.async_create_entry(title="", data={})

            return self.async_abort(reason="no_selection")

        # Build options for restarts
        restart_options = [
            SelectOptionDict(value=d, label=f"{d}: week {w}")
            for d, w in sorted(restarts.items())
        ]

        data_schema = vol.Schema(
            {
                vol.Required(INPUT_RESTARTS_TO_REMOVE, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=restart_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="delete_restart",
            data_schema=data_schema,
        )

    async def async_step_edit_menu(self, user_input: dict[str, Any] | None = None):
        """Handle selecting a menu to edit."""
        menus = self._storage.data.get(CONF_MENUS, {})

        if not menus:
            return self.async_abort(reason="no_menus")

        if user_input is not None:
            self._selected_menu_id = user_input.get(INPUT_MENU_ID)
            if self._selected_menu_id:
                return await self.async_step_edit_menu_details()

        # Build options for menus
        menu_options = []
        for menu_id, menu_data in menus.items():
            name = menu_data.get(CONF_MENU_NAME, "Unknown")
            effective = menu_data.get(CONF_EFFECTIVE_DATE, "Unknown")
            menu_options.append(SelectOptionDict(value=menu_id, label=f"{name} ({effective})"))

        # Sort by effective date
        menu_options.sort(key=lambda x: x["label"])

        data_schema = vol.Schema({
            vol.Required(INPUT_MENU_ID, default=[]): SelectSelector(
                SelectSelectorConfig(
                    options=menu_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        })

        return self.async_show_form(
            step_id="edit_menu",
            data_schema=data_schema,
            last_step=False,
        )

    async def async_step_edit_menu_details(self, user_input: dict[str, Any] | None = None):
        """Handle editing menu details."""
        errors: dict[str, str] = {}
        menus = self._storage.data.get(CONF_MENUS, {})
        current_menu = menus.get(self._selected_menu_id, {})

        if user_input is not None:
            new_name = user_input.get(CONF_MENU_NAME, "")
            new_date = user_input.get(CONF_EFFECTIVE_DATE, "")
            csv_content = user_input.get(CONF_MENU_CSV, "")

            # Validate date
            try:
                date.fromisoformat(new_date)
            except ValueError:
                errors[CONF_EFFECTIVE_DATE] = "invalid_date"

            # Parse CSV if provided
            new_menu_data = current_menu.get(CONF_MENU_DATA, {})
            new_total_weeks = current_menu.get(CONF_TOTAL_WEEKS, 4)

            if csv_content.strip():
                try:
                    new_menu_data, new_total_weeks = parse_csv_menu(csv_content)
                    if not new_menu_data:
                        errors[CONF_MENU_CSV] = "invalid_csv"
                except Exception as ex:
                    _LOGGER.error("Error parsing CSV: %s", ex)
                    errors[CONF_MENU_CSV] = "invalid_csv"

            if not errors:
                # Update the menu in storage
                new_menus = dict(menus)
                new_menus[self._selected_menu_id] = {
                    CONF_MENU_NAME: new_name,
                    CONF_EFFECTIVE_DATE: new_date,
                    CONF_MENU_DATA: new_menu_data,
                    CONF_TOTAL_WEEKS: new_total_weeks,
                }
                await self._storage.async_update({CONF_MENUS: new_menus})
                return self.async_create_entry(title="", data={})

        data_schema = vol.Schema({
            vol.Required(CONF_MENU_NAME, default=current_menu.get(CONF_MENU_NAME, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_EFFECTIVE_DATE, default=current_menu.get(CONF_EFFECTIVE_DATE, "")): DateSelector(),
            vol.Optional(CONF_MENU_CSV, default=""): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.TEXT,
                    multiline=True,
                )
            ),
        })

        return self.async_show_form(
            step_id="edit_menu_details",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "csv_hint": "Leave empty to keep current menu data"
            },
        )

    async def async_step_add_menu(self, user_input: dict[str, Any] | None = None):
        """Handle adding a new menu."""
        errors: dict[str, str] = {}

        if user_input is not None:
            menu_name = user_input.get(CONF_MENU_NAME)
            effective_date = user_input.get(CONF_EFFECTIVE_DATE)
            csv_content = user_input.get(CONF_MENU_CSV)

            # Validate date
            try:
                date.fromisoformat(effective_date)
            except ValueError:
                errors[CONF_EFFECTIVE_DATE] = "invalid_date"
            
            # Parse CSV
            if csv_content.strip():
                try:
                    self._new_menu_data, self._new_total_weeks = parse_csv_menu(csv_content)
                    if not self._new_menu_data:
                        errors[CONF_MENU_CSV] = "invalid_csv"
                except Exception as ex:
                    _LOGGER.error("Error parsing CSV: %s", ex)
                    errors[CONF_MENU_CSV] = "invalid_csv"
            else:
                errors[CONF_MENU_CSV] = "csv_required"

            if not errors:
                # Add new menu to storage
                menus = dict(self._storage.data.get(CONF_MENUS, {}))
                menu_id = str(uuid.uuid4())
                menus[menu_id] = {
                    CONF_MENU_NAME: menu_name,
                    CONF_EFFECTIVE_DATE: effective_date,
                    CONF_MENU_DATA: self._new_menu_data,
                    CONF_TOTAL_WEEKS: self._new_total_weeks,
                }
                await self._storage.async_update({CONF_MENUS: menus})
                return self.async_create_entry(title="", data={})

        data_schema = vol.Schema({
            vol.Required(CONF_MENU_NAME): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_EFFECTIVE_DATE, default=None): DateSelector(),
            vol.Required(CONF_MENU_CSV): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.TEXT,
                    multiline=True,
                )
            ),
        })

        return self.async_show_form(
            step_id="add_menu",
            data_schema=data_schema,
            errors=errors,
        )
