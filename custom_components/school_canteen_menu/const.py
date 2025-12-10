"""Constants for the School Canteen Menu integration."""

DOMAIN = "school_canteen_menu"

CONF_NAME = "name"
CONF_STORAGE_ID = "storage_id"
CONF_START_DATE = "start_date"
CONF_START_WEEK = "start_week"
CONF_TOTAL_WEEKS = "total_weeks"
CONF_MENUS = "menus"
CONF_MENU_ID = "menu_id"
CONF_MENU_NAME = "menu_name"
CONF_MENU_DATA = "menu_data"
CONF_MENU_CSV = "menu_csv"
CONF_EFFECTIVE_DATE = "effective_date"
CONF_CLOSURE_PERIODS = "closure_periods"
CONF_CLOSURE_PERIOD_START = "start"
CONF_CLOSURE_PERIOD_END = "end"
CONF_RESTARTS = "restarts"

# CSV column names (fixed positions)
CSV_COL_WEEK_NUMBER = "week_number"
CSV_COL_WEEK_DAY = "week_day"
CSV_COL_MAIN_COURSE = "main_course"
CSV_COL_SECOND_COURSE = "second_course"
CSV_COL_SIDE = "side"
CSV_COL_FRUIT = "fruit"

# Map Python weekday (0=Monday) to CSV day number (1=Monday)
WEEKDAY_TO_CSV = {
    0: 1,  # Monday
    1: 2,  # Tuesday
    2: 3,  # Wednesday
    3: 4,  # Thursday
    4: 5,  # Friday
    5: 6,  # Saturday
    6: 7,  # Sunday
}

# Map CSV day number to Python weekday
CSV_TO_WEEKDAY = {v: k for k, v in WEEKDAY_TO_CSV.items()}

# Day names for display
WEEKDAY_NAMES = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}

ATTR_WEEK = "week"
ATTR_DAY = "day"
ATTR_DAY_NUMBER = "day_number"
ATTR_DATE = "date"
ATTR_NEXT_DATE = "next_date"
ATTR_IS_CLOSED = "is_closed"
ATTR_MENU_NAME = "menu_name"
