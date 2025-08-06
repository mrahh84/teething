#!/bin/bash

# Set strict mode
# -e    allows scripts to exit immediately if any command has a non-zero exit status
# -u    causes the script to exit if it uses an undefined variable
# -o    ensures that the pipeline exits with the code of the last

# Enforce strict error handling
set -euo pipefail

# Change to the home directory
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
HOME_DIR=$(dirname "$SCRIPT_DIR")
cd "$HOME_DIR"

# Define variables
BACKUP_DIR="${HOME_DIR}/backups"
DB_FILE="${HOME_DIR}/db.sqlite3"
DATE=$(date +%Y-%m-%d)
BACKUP_FILE="${BACKUP_DIR}/backup_${DATE}.sqlite3"
LOG_FILE="${HOME_DIR}/logs/backup_log.log"
TEMP_FILE=$(mktemp)

# Function to log messages
log_message() {
    local message="$1"
    echo "$(date +'%Y-%m-%d %H:%M:%S') - $message" >> "$LOG_FILE"
}

# Function to handle errors
handle_error() {
    local exit_code=$?
    log_message "ERROR: Command failed with exit code $exit_code on line $LINENO."
    exit $exit_code
}

# Set up the trap to catch errors
trap 'handle_error' ERR

# Start log
log_message "Backup process started."

# Check if the backup directory exists
if [ -d "$BACKUP_DIR" ]; then
    log_message "Backup directory already exists: $BACKUP_DIR"
else
    log_message "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR" 2>>"$LOG_FILE"
fi

# Copy the database file to the backup directory with a timestamp
log_message "Copying database file to backup directory."
cp "$DB_FILE" "$BACKUP_FILE" 2>>"$LOG_FILE"

# Find and delete backups older than 7 days
log_message "Checking for backups older than 7 days."
find "$BACKUP_DIR" -type f -name "backup_*.sqlite3" -mtime +7 -exec ls -la {} \; >> "$LOG_FILE"
OLD_BACKUPS=$(find "$BACKUP_DIR" -type f -name "backup_*.sqlite3" -mtime +7)

if [ -n "$OLD_BACKUPS" ]; then
    log_message "Deleting backups older than 7 days:"
    echo "$OLD_BACKUPS" >> "$LOG_FILE"
    find "$BACKUP_DIR" -type f -name "backup_*.sqlite3" -mtime +7 -delete
    log_message "Old backups deleted."
else
    log_message "No old backups to delete."
fi

# Clean up
rm -f "$TEMP_FILE"

# DB successful backup
log_message "Backup created: $BACKUP_FILE"
log_message "Backup process completed."
echo "" >> "$LOG_FILE"
