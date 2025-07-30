import os
import glob
import shutil
import sys
import configparser

def cleanup():
    """
    Cleans up temporary files after analysis is complete.
    Removes all CSV files from the output directory while preserving original Excel files.
    """
    # Load configuration
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define paths from config
    output_dir = os.path.join(current_dir, config['Paths']['output'])
    
    # Check if output directory exists
    if not os.path.exists(output_dir):
        print(f"Output directory {output_dir} does not exist. Nothing to clean up.")
        return False
    
    try:
        # Count files before cleanup
        csv_files = glob.glob(os.path.join(output_dir, "*.csv"))
        file_count = len(csv_files)
        
        if file_count == 0:
            print("No CSV files found in the output directory. Nothing to clean up.")
            return True
        
        print(f"Found {file_count} CSV files to remove from {output_dir}.")
        
        # Ask for confirmation
        if len(sys.argv) > 1 and sys.argv[1] == '--force':
            confirm = 'y'
        else:
            confirm = input(f"Are you sure you want to delete {file_count} CSV files from the output directory? (y/n): ")
        
        if confirm.lower() == 'y':
            # Remove all CSV files
            for csv_file in csv_files:
                os.remove(csv_file)
                print(f"Removed: {csv_file}")
            
            print(f"\nSuccessfully removed {file_count} CSV files from {output_dir}.")
            return True
        else:
            print("Cleanup cancelled.")
            return False
            
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return False

if __name__ == "__main__":
    print("\n===== CLEANUP UTILITY =====")
    print("This script will remove all temporary CSV files from the output directory.\n")
    
    success = cleanup()
    
    if success:
        # Load config for printing paths
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        print("\nCleanup completed successfully!")
        print(f"Original Excel files in the '{config['Paths']['original']}' directory are preserved.")
        print(f"Analysis results in the '{config['Paths']['analysis']}' directory are preserved.")
        print(f"Consolidated data in the '{config['Paths']['final']}' directory are preserved.")
    else:
        print("\nCleanup was not completed.")
        
    print("\n============================") 