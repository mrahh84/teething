#!/usr/bin/env python3
import os
import sys
import subprocess
import time
from datetime import datetime
import configparser
import argparse
import logging

def log_header(message):
    """Log a formatted header for the current step."""
    logging.info("=" * 70)
    logging.info(f"  {message}")
    logging.info("=" * 70)

def run_script(script_name, description, args=None):
    """Run a Python script and return its success status."""
    log_header(f"STEP: {description}")
    logging.info(f"Running {script_name}...")
    
    start_time = time.time()
    
    # Build the command
    cmd = [sys.executable, script_name]
    if args:
        cmd.extend(args)
    
    logging.debug(f"Executing command: {' '.join(cmd)}")
    
    # Run the script as a subprocess
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Log the output
    if result.stdout:
        logging.debug(f"Script output:\n{result.stdout}")
        # Still print stdout to console for user visibility
        print(result.stdout)
    
    # Check if the script was successful
    if result.returncode == 0:
        logging.info(f"✓ {script_name} completed successfully in {execution_time:.2f} seconds.")
        return True
    else:
        logging.error(f"✗ {script_name} failed with return code {result.returncode}.")
        if result.stderr:
            logging.error(f"Error details: {result.stderr}")
        return False

def main():
    # Initialize argument parser
    parser = argparse.ArgumentParser(
        description='Attendance Analysis System - Automated Workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python run_analysis.py                    # Run with confirmation prompts
  python run_analysis.py --force            # Skip confirmation prompts
  python run_analysis.py --config my.ini    # Use custom config file
  python run_analysis.py --force --config custom.ini  # Both options
        '''
    )
    
    # Add command-line arguments
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts and run the workflow automatically')
    parser.add_argument('--config', default='config.ini',
                       help='Path to configuration file (default: config.ini)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Configure logging
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Create file handler (DEBUG level and above)
    file_handler = logging.FileHandler('analysis.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Create console handler (INFO level and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Record start time
    start_time = time.time()
    
    # Log welcome message
    logging.info("=" * 70)
    logging.info("  ATTENDANCE ANALYSIS SYSTEM - AUTOMATED WORKFLOW")
    logging.info("=" * 70)
    logging.info(f"Starting analysis at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"Using configuration file: {args.config}")
    logging.info("This script will run the entire analysis pipeline in sequence.")
    
    # Load configuration
    config = configparser.ConfigParser()
    if not os.path.exists(args.config):
        logging.error(f"Configuration file '{args.config}' not found.")
        return False
    config.read(args.config)
    logging.info(f"Successfully loaded configuration from {args.config}")
    
    # Define workflow descriptions for each script
    workflow_descriptions = {
        "excel_to_csv.py": "Converting Excel files to CSV",
        "consolidate_csv.py": "Consolidating CSV files", 
        "analyze_attendance.py": "Analyzing attendance patterns",
        "cleanup.py": "Cleaning up temporary files"
    }
    
    # Build workflow dynamically from config
    workflow = []
    for key, script in config['Workflow'].items():
        step = {
            "script": script,
            "description": workflow_descriptions.get(script, f"Running {script}")
        }
        # Add special args for cleanup script
        if script == "cleanup.py":
            step["args"] = ["--force"]
        workflow.append(step)
    
    # Ask for confirmation unless --force is specified
    if not args.force:
        confirm = input("Ready to start the analysis workflow? (y/n): ")
        if confirm.lower() != 'y':
            logging.info("Workflow cancelled by user.")
            return False
    
    # Check if required folders exist and create them if needed
    current_dir = os.path.dirname(os.path.abspath(__file__))
    required_folders = list(config['Paths'].values())
    
    for folder in required_folders:
        folder_path = os.path.join(current_dir, folder)
        if not os.path.exists(folder_path):
            logging.info(f"Creating required folder: {folder}")
            os.makedirs(folder_path)
    
    # Check if there are Excel files in the original folder
    excel_files = [f for f in os.listdir(os.path.join(current_dir, config['Paths']['original'])) 
                  if f.endswith('.xlsx') or f.endswith('.xls')]
    
    if not excel_files:
        log_header("WARNING: No Excel files found in the 'original' folder")
        logging.warning("Please place your Excel files in the 'original' folder before running this script.")
        confirm = input("Continue anyway? (y/n): ")
        if confirm.lower() != 'y':
            logging.info("Workflow cancelled by user.")
            return False
    
    # Run each step in the workflow
    all_successful = True
    
    for i, step in enumerate(workflow):
        script = step["script"]
        description = step["description"]
        
        # Run the script
        success = run_script(script, f"{i+1}. {description}", step.get("args"))
        
        # If a script fails, stop the workflow
        if not success:
            log_header(f"WORKFLOW HALTED: Error in step {i+1}")
            logging.error(f"The workflow was halted due to an error in {script}.")
            all_successful = False
            break
    
    # Calculate total execution time
    total_time = time.time() - start_time
    
    # Log summary
    if all_successful:
        log_header("WORKFLOW COMPLETED SUCCESSFULLY")
        logging.info(f"All steps completed successfully in {total_time:.2f} seconds.")
        logging.info("Results can be found in the following locations:")
        logging.info(f"- Analysis results: {os.path.join(current_dir, config['Paths']['analysis'])}")
        logging.info(f"- Consolidated data: {os.path.join(current_dir, config['Paths']['final'])}")
    else:
        log_header("WORKFLOW COMPLETED WITH ERRORS")
        logging.error(f"The workflow was completed with errors in {total_time:.2f} seconds.")
        logging.error("Please check the error messages above and the analysis.log file for details.")
    
    return all_successful

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 