# Road Attendance Scripts

This directory contains utility scripts for the Road Attendance system.

## Available Scripts

### 1. `generate_secret_key.py`

Generates a secure random string for use as Django's SECRET_KEY setting.

```bash
python scripts/generate_secret_key.py
```

### 2. `create_initial_data.py`

Creates the required initial data for the application - the "Clock In" and "Clock Out" event types, and the "Main Security" location.

```bash
python manage.py shell < scripts/initial_data.py
```

### 3. `create_sample_data.py`

Populates the database with 20 sample employees, each with their own card, and random clock events.

```bash
python manage.py shell < scripts/create_sample_data.py
```

### 4. `check_employee_status.py`

Displays a report of all employees and their current clock-in status.

```bash
python manage.py shell < scripts/check_employee_status.py
```

## Marimo Report Scripts

### run_marimo_reports.py

A Python script to run individual Marimo attendance reports from the command line.

Usage:
```bash
# List all available notebooks
python run_marimo_reports.py --list

# Run a specific notebook
python run_marimo_reports.py daily_attendance_dashboard
```

### run_all_reports.sh

A shell script that runs all Marimo attendance reports in sequence.

Usage:
```bash
# Run all reports
./run_all_reports.sh
```

## Django Management Commands

### 1. `batch_clock`

A Django management command to clock employees in or out in batch.

**Usage:**

```bash
# Clock out all employees
python manage.py batch_clock out all

# Clock in specific employees by card number
python manage.py batch_clock in CARD-1001,CARD-1002,CARD-1003

# Clock out specific employees by card number
python manage.py batch_clock out CARD-1001,CARD-1002
```

## Requirements

These scripts require:
- Python 3.x
- Django project environment
- Marimo (`pip install marimo[recommended]`)
- Pandas
- Plotly
