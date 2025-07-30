#!/bin/bash

echo "=========================================="
echo "     ATTENDANCE ANALYSIS REPORT GENERATOR"
echo "=========================================="
echo ""
echo "This will generate the complete attendance analysis report."
echo "Looking for Excel file and processing..."
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Python is available
if ! command_exists python3 && ! command_exists python; then
    echo "ERROR: Python is not installed or not in PATH!"
    echo "Please install Python 3.6+ and try again."
    exit 1
fi

# Determine Python command
if command_exists python3; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Check if virtual environment exists and activate it
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "No virtual environment found. Using system Python..."
fi

# Check if config file exists
if [ ! -f "config.ini" ]; then
    echo "ERROR: config.ini file not found!"
    echo "Please ensure the configuration file exists in the application folder."
    exit 1
fi

# Check if the original folder exists and has Excel files
if [ ! -d "original" ]; then
    echo "Creating original folder..."
    mkdir -p original
    echo ""
    echo "Please place your Excel files (REPORT_*.xlsx) in the 'original' folder"
    echo "and run this script again."
    exit 1
fi

# Check for Excel files
if ! ls original/*.xlsx >/dev/null 2>&1; then
    echo ""
    echo "WARNING: No Excel files found in the 'original' folder!"
    echo "Please place your Excel files (REPORT_*.xlsx) in the 'original' folder"
    echo ""
    read -p "Continue anyway? (y/n): " continue_choice
    if [[ $continue_choice != [Yy] ]]; then
        exit 1
    fi
fi

echo "Starting attendance analysis..."
echo ""
$PYTHON_CMD run_analysis.py --force

# Check if the analysis was successful
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Analysis failed! Please check the error messages above."
    echo "Check analysis.log for detailed error information."
    exit 1
fi

echo ""
echo "=========================================="
echo "     ANALYSIS COMPLETED SUCCESSFULLY!"
echo "=========================================="
echo ""
echo "Results have been generated in the following folders:"
echo "  - analysis/     (Main reports and charts)"
echo "  - final/        (Consolidated data)"
echo ""
echo "Key reports generated:"
echo "  - attendance_analysis_results.csv"
echo "  - monthly_summary_report.csv"
echo "  - comprehensive_attendance_report.csv"
echo "  - Interactive HTML charts"
echo ""
echo "You can find detailed logs in 'analysis.log'"
echo ""
echo "Press any key to continue..."
read -n 1 