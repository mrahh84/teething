#!/bin/bash
# Run all Marimo attendance reports in sequence

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Set up environment
source $PROJECT_ROOT/venv/bin/activate 2>/dev/null || echo "Virtual environment not found at expected location"

# List of notebooks to run
NOTEBOOKS=(
    "daily_attendance_dashboard"
    "employee_attendance_history"
    "attendance_summary_by_period"
    "late_early_report"
)

# Run each notebook
for notebook in "${NOTEBOOKS[@]}"; do
    echo "Running $notebook..."
    python $SCRIPT_DIR/run_marimo_reports.py "$notebook"
    echo "Finished $notebook"
    echo
done

echo "All notebooks completed!" 