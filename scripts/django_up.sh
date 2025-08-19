#!/bin/bash

# Set strict mode
# -e    allows scripts to exit immediately if any command has a non-zero exit status
# -u    causes the script to exit if it uses an undefined variable
# -o    ensures that the pipeline exits with the code of the last

set -euo pipefail

# Change to the home directory
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
HOME_DIR=$(dirname "$SCRIPT_DIR")
cd "$HOME_DIR"

# Define log file
LOG_FILE="${HOME_DIR}/logs/django_up.log"

# Create the log file if it doesn't exist
mkdir -p $(dirname "${LOG_FILE}")
touch ${LOG_FILE}

# Function to log messages
log_message() {
    local message="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $message" >> "$LOG_FILE"
}

# Function to handle script errors
handle_error() {
    local exit_code="$?"
    log_message "Script failed with exit code $exit_code."
    exit "$exit_code"
}

# Catch errors
trap 'handle_error' ERR

# Log script start
log_message "Script started."

# Run Django migrations
log_message "Running Django migrations..."
python3 manage.py makemigrations --noinput
python3 manage.py migrate --noinput
log_message "Django migrations completed."

# Collect static files
log_message "Running Django collectstatic..."
python manage.py collectstatic --noinput --clear
log_message "Django collectstatic completed."

# Create schema file
log_message "Creating schema files..."
python manage.py spectacular --color --validate --color --file schema.yml
log_message "Schema files created."

# Start the Django server
log_message "Starting the Django server..."
{
    python3 manage.py runserver "0.0.0.0:8000"
    log_message "Django server started successfully."
} || {
    log_message "Failed to start Django server."
    exit 1
}

log_message "Script finished."
echo "" >> "$LOG_FILE"
