#!/bin/bash

# Exit on error
set -e

# Function to check if a package is installed
check_package() {
    pip freeze | grep -q "^$1=="
    return $?
}

# Function to verify all required packages are installed
verify_packages() {
    local packages=("pandas" "plotly" "matplotlib" "seaborn" "numpy")
    local missing_packages=()
    
    for package in "${packages[@]}"; do
        if ! check_package "$package"; then
            missing_packages+=("$package")
        fi
    done
    
    if [ ${#missing_packages[@]} -ne 0 ]; then
        echo "Missing packages: ${missing_packages[*]}"
        return 1
    fi
    return 0
}

# Function to check if a file exists
check_file() {
    if [ ! -f "$1" ]; then
        echo "Error: Required file '$1' not found!"
        echo "Please ensure the file exists in the correct location."
        exit 1
    fi
}

# Function to check if a directory exists
check_directory() {
    if [ ! -d "$1" ]; then
        echo "Creating directory: $1"
        mkdir -p "$1"
    fi
}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    NEED_SETUP=true
else
    echo "Virtual environment found."
    NEED_SETUP=false
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Always ensure pip is up to date
echo "Upgrading pip..."
pip install --upgrade pip

# Install or verify required packages
if [ "$NEED_SETUP" = true ] || ! verify_packages; then
    echo "Installing required packages..."
    pip install pandas plotly matplotlib seaborn numpy
    echo "Verifying package installation..."
    if ! verify_packages; then
        echo "Error: Failed to install all required packages!"
        exit 1
    fi
else
    echo "All dependencies are already installed."
fi

# Check for required directories and files
echo "Checking required files and directories..."
check_directory "analysis"
check_directory "final"

# Check for input data file
check_file "final/final_sorted_consolidated_data.csv"

# Run the main analysis script first
echo "Running main analysis script..."
python analyze_attendance.py

# Verify analysis output files were created
check_file "analysis/attendance_analysis_results.csv"
check_file "analysis/comprehensive_attendance_report.csv"

# Run the chart generation script
echo "Generating chart..."
python create_problematic_employees_chart.py

# Check if chart was generated successfully
if [ ! -f "analysis/top_problematic_employees_chart.html" ]; then
    echo "Error: Chart generation failed!"
    exit 1
fi

# Deactivate virtual environment
deactivate

echo "Analysis and chart generation complete!"
echo "Check the following files in the analysis directory:"
echo "- attendance_analysis_results.csv"
echo "- comprehensive_attendance_report.csv"
echo "- top_problematic_employees_chart.html" 