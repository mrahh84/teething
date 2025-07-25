#!/bin/bash

echo "=========================================="
echo "  NETWORK-AWARE ATTENDANCE REPORT GENERATOR"
echo "=========================================="
echo ""

# Configuration file to use
CONFIG_FILE="config_network.ini"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to read config value
get_config_value() {
    local section=$1
    local key=$2
    local config_file=${3:-$CONFIG_FILE}
    
    # Use Python to parse the INI file
    python3 -c "
import configparser
config = configparser.ConfigParser()
config.read('$config_file')
try:
    print(config['$section']['$key'])
except:
    print('')
" 2>/dev/null
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

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: $CONFIG_FILE file not found!"
    echo "Please ensure the network configuration file exists."
    echo "You can copy config.ini to $CONFIG_FILE and modify it for your network setup."
    exit 1
fi

# Read network configuration
EXCEL_SOURCE_PATH=$(get_config_value "Network" "excel_source_path")
EXCEL_PATTERN=$(get_config_value "Network" "excel_file_pattern")
COPY_TO_LOCAL=$(get_config_value "Network" "copy_to_local")
BACKUP_PATH=$(get_config_value "Network" "backup_local_path")

echo "Reading network configuration..."
echo "Excel source path: ${EXCEL_SOURCE_PATH:-"(using local folder)"}"
echo "Excel file pattern: $EXCEL_PATTERN"
echo ""

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

# Create local directories
mkdir -p original output final analysis

# Function to find and copy Excel files
find_excel_files() {
    local found_files=0
    
    # If network path is configured, try to find files there
    if [ -n "$EXCEL_SOURCE_PATH" ] && [ -d "$EXCEL_SOURCE_PATH" ]; then
        echo "Searching for Excel files in network location: $EXCEL_SOURCE_PATH"
        
        # Find Excel files in network location
        if ls "$EXCEL_SOURCE_PATH"/$EXCEL_PATTERN >/dev/null 2>&1; then
            echo "Found Excel files in network location!"
            
            if [ "$COPY_TO_LOCAL" = "true" ]; then
                echo "Copying Excel files to local 'original' folder..."
                cp "$EXCEL_SOURCE_PATH"/$EXCEL_PATTERN original/ 2>/dev/null
                if [ $? -eq 0 ]; then
                    echo "Successfully copied Excel files from network location."
                    found_files=1
                else
                    echo "Warning: Failed to copy some files from network location."
                fi
            else
                # Update config to point to network location
                echo "Using Excel files directly from network location."
                export REPORT_EXCEL_SOURCE="$EXCEL_SOURCE_PATH"
                found_files=1
            fi
        else
            echo "No Excel files found in network location: $EXCEL_SOURCE_PATH"
        fi
    fi
    
    # If no files found in network location, check local backup
    if [ $found_files -eq 0 ]; then
        echo "Checking local backup location: $BACKUP_PATH"
        if ls $BACKUP_PATH/$EXCEL_PATTERN >/dev/null 2>&1; then
            echo "Found Excel files in local backup location!"
            if [ "$BACKUP_PATH" != "original" ]; then
                cp "$BACKUP_PATH"/$EXCEL_PATTERN original/ 2>/dev/null
            fi
            found_files=1
        else
            echo "No Excel files found in local backup location either."
        fi
    fi
    
    return $found_files
}

# Find Excel files
if ! find_excel_files; then
    echo ""
    echo "ERROR: No Excel files found in any configured location!"
    echo ""
    echo "Please ensure Excel files are available in one of these locations:"
    [ -n "$EXCEL_SOURCE_PATH" ] && echo "  - Network: $EXCEL_SOURCE_PATH"
    echo "  - Local: $BACKUP_PATH"
    echo ""
    echo "Excel files should match pattern: $EXCEL_PATTERN"
    exit 1
fi

echo ""
echo "Starting attendance analysis..."
echo ""
$PYTHON_CMD run_analysis.py --config "$CONFIG_FILE" --force

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