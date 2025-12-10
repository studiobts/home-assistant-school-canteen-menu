# School Canteen Menu

Home Assistant integration for managing a school canteen menu with multi-menu support and configurable rotation cycles.

## Features

- **Multi-menu support**: Configure multiple menus with different effective dates
- **Dynamic N-week rotation**: Automatically detected from CSV
- **Closure management**: Single dates or date ranges
- **Restart dates**: Resume from a specific week after breaks
- **Custom attributes**: Calories, allergens, menu type, etc.
- **Sensors**: Current week, total weeks, day info, meals for today and next valid day

## Installation

1. Copy the `school_canteen_menu` folder to `config/custom_components/`
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration
4. Search for "School Canteen Menu"

## Initial Configuration

### Step 1: Basic Setup

- **Name**: Integration identifier (e.g., "School Canteen Menu")
- **Cycle start date**: Date from which the rotation cycle starts
- **Starting week**: Initial week number
- **Menu name**: Name for the initial menu (default: "Menu Iniziale")

### Step 2: Menu Upload

Paste the CSV content with the menu data.

## CSV Format

```csv
week_number,week_day,[day_attrs...],main_course,[main_attrs...],second_course,[second_attrs...],side,[side_attrs...]
```

### Required Columns (Fixed Positions)

| Column          | Description                                    |
|-----------------|------------------------------------------------|
| `week_number`   | Week number (1 to N)                           |
| `week_day`      | Day number: 1=Monday, 2=Tuesday, ..., 7=Sunday |
| `main_course`   | Main course name                               |
| `second_course` | Second course name                             |
| `side`          | Side dish name                                 |
| `fruit`         | Fruit name                                |

### Optional Attribute Columns

Add columns between required ones for custom attributes:

- **Between `week_day` and `main_course`**: Day attributes (menu_type, special_day)
- **Between `main_course` and `second_course`**: Main course attributes
- **Between `second_course` and `side`**: Second course attributes
- **Between `side` and `fruit`**: Side dish attributes
- **After `fruit`**: Fruit attributes

Example:
```csv
week_number,week_day,menu_type,main_course,main_calories,second_course,side,side_note
1,1,Standard,Pasta,320,Chicken,Carrots,organic
```

## Options Flow

After initial setup, access options to manage:

### Actions Available

1. **Add closure date**: Single day closure
2. **Add closure period**: Date range closure (e.g., Christmas break)
3. **Delete closure**: Remove configured closures
4. **Add restart date**: Resume from specific week after a break
5. **Delete restart date**: Remove restart configurations
6. **Edit menu**: Modify existing menu name, date, or CSV data
7. **Add new menu**: Upload a new menu with effective date

### Multi-Menu Behavior

When multiple menus are configured, the integration automatically uses the most recent menu based on effective date. This allows you to:

- Prepare next semester's menu in advance
- Keep historical menus for reference
- Switch menus automatically on the effective date

## Sensors

| Sensor                | Description                   |
|-----------------------|-------------------------------|
| `current_week`        | Current week number (1 to N)  |
| `total_weeks`         | Total weeks in rotation cycle |
| `day_today`           | Current day name              |
| `day_next`            | Next valid school day name    |
| `main_course_today`   | Today's main course           |
| `second_course_today` | Today's second course         |
| `side_today`          | Today's side dish             |
| `fruit_today`         | Today's fruit                 |
| `main_course_next`    | Next day's main course        |
| `second_course_next`  | Next day's second course      |
| `side_next`           | Next day's side dish          |
| `fruit_next`          | Next day's fruit dish         |

### Sensor Attributes

All sensors include:
- `date` / `next_date`: Reference date
- `day` / `day_number`: Day name and number
- `week`: Current week number
- `is_closed`: School closure status
- `menu_name`: Active menu name
- Custom attributes from CSV

"Today" sensors become unavailable on closure days.
