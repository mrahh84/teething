# Marimo Attendance Reports

This directory contains Marimo notebooks that provide interactive attendance reports for the Road Attendance system.

## Available Reports

1. **Daily Attendance Dashboard** (`daily_attendance_dashboard.py`)
   - Shows real-time attendance status for the current day
   - Lists employees who are clocked in and not clocked in
   - Provides summary statistics and visualizations

2. **Individual Employee Attendance History** (`employee_attendance_history.py`)
   - Shows detailed attendance history for a single employee
   - Allows selection of date range
   - Calculates total hours worked
   - Visualizes daily hours worked

3. **Attendance Summary by Period** (`attendance_summary_by_period.py`)
   - Provides aggregated attendance statistics per employee
   - Supports daily, weekly, and monthly reporting periods
   - Tracks late arrivals, early departures, and missing punches

4. **Late Arrival and Early Departure Report** (`late_early_report.py`)
   - Identifies instances of employees clocking in late or out early
   - Allows customization of thresholds for lateness/early departure
   - Provides detailed reports and visualizations

## Running Reports

### From Django Web Interface

Reports are integrated into the Django web interface and can be accessed from the Reports dashboard.

### Directly from Command Line

You can also run the reports directly using the provided script:

```bash
# List available notebooks
python scripts/run_marimo_reports.py --list

# Run a specific notebook
python scripts/run_marimo_reports.py daily_attendance_dashboard
```

## Requirements

These notebooks require:
- Marimo (`pip install marimo[recommended]`)
- Pandas
- Plotly
- Django project environment

## Development

To create a new report, follow the pattern in the existing notebooks:
1. Import required libraries
2. Set up Django environment in a cell
3. Create interactive UI elements with `mo.ui` components
4. Load and process data from the Django models
5. Create visualizations and layouts
6. Export as needed for integration with Django views 