import pandas as pd
import os
import glob # Module to find files matching a pattern
from datetime import datetime
import configparser

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# --- User Configuration ---
# Use relative paths for input and output from config
current_dir = os.path.dirname(os.path.abspath(__file__))
csv_folder_path = os.path.join(current_dir, config['Paths']['output'])
final_dir = os.path.join(current_dir, config['Paths']['final'])

# Create the final directory if it doesn't exist
if not os.path.exists(final_dir):
    os.makedirs(final_dir)
    print(f"Created final directory: {final_dir}")

consolidated_file_path = os.path.join(final_dir, 'final_sorted_consolidated_data.csv')

# 3. Verify these column names match your CSV headers exactly!
name_column = 'NAMES' 
date_column = 'DATE'  
# --- End of User Configuration ---

def process_departure_time(time_str):
    """Process departure time to ensure consistent format."""
    if pd.isna(time_str):
        return time_str
    
    # Handle special values
    time_str_upper = str(time_str).strip().upper()
    if time_str_upper in ['ABSENT', 'APPOINTMENT']:
        return time_str_upper
    
    try:
        # Try to parse the time string
        time_obj = pd.to_datetime(time_str).time()
        # Format as HH:MM AM/PM
        return time_obj.strftime("%I:%M %p")
    except:
        return time_str

def process_standup(value):
    """Process STAND-UP values to ensure consistent format."""
    if pd.isna(value):
        return value
    value = str(value).strip().upper()
    if value in ['Y', 'YES', '1', 'TRUE']:
        return 'YES'
    elif value in ['N', 'NO', '0', 'FALSE']:
        return 'NO'
    elif value in ['ABSENT', 'APPOINTMENT']:
        return value  # Keep ABSENT and APPOINTMENT as-is
    return value

def validate_columns(df):
    """Validate and process STAND-UP and DEPARTURE TIME columns."""
    if 'STAND-UP' in df.columns:
        df['STAND-UP'] = df['STAND-UP'].apply(process_standup)
        # Validate STAND-UP values - Accept ABSENT and APPOINTMENT as valid
        invalid_standup = df[~df['STAND-UP'].isin(['YES', 'NO', 'ABSENT', 'APPOINTMENT', pd.NA])]
        if not invalid_standup.empty:
            print(f"Warning: Found {len(invalid_standup)} invalid STAND-UP values")
            print(invalid_standup[['NAMES', 'STAND-UP']])
    
    if 'DEPARTURE TIME' in df.columns:
        df['DEPARTURE TIME'] = df['DEPARTURE TIME'].apply(process_departure_time)
        # Validate DEPARTURE TIME format - Accept ABSENT and APPOINTMENT as valid
        invalid_times = df[
            ~df['DEPARTURE TIME'].isin(['ABSENT', 'APPOINTMENT']) &  # Valid special values
            ~df['DEPARTURE TIME'].isna() &  # Valid NaN values
            ~df['DEPARTURE TIME'].str.match(r'^\d{1,2}:\d{2} [AP]M$', na=False)  # Valid time format
        ]
        if not invalid_times.empty:
            print(f"Warning: Found {len(invalid_times)} invalid DEPARTURE TIME values")
            print(invalid_times[['NAMES', 'DEPARTURE TIME']])
    
    return df

def consolidate_csv_files(input_folder=None, output_file=None):
    """Consolidate all CSV files in the input folder into a single CSV file."""
    # Use config defaults if not provided
    if input_folder is None:
        input_folder = config['Paths']['output']
    if output_file is None:
        output_file = os.path.join(config['Paths']['final'], 'consolidated_data.csv')
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Get all CSV files in the input folder
    csv_files = [f for f in os.listdir(input_folder) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"No CSV files found in {input_folder}")
        return
    
    print(f"Found {len(csv_files)} CSV files to consolidate")
    
    # Initialize an empty list to store DataFrames
    dfs = []
    
    # Read each CSV file and append to the list
    for file in csv_files:
        file_path = os.path.join(input_folder, file)
        print(f"Processing {file}...")
        
        try:
            df = pd.read_csv(file_path)
            # Validate and process columns
            df = validate_columns(df)
            dfs.append(df)
            print(f"Successfully processed {file} with {len(df)} rows")
        except Exception as e:
            print(f"Error processing {file}: {str(e)}")
    
    if not dfs:
        print("No valid data to consolidate")
        return
    
    # Concatenate all DataFrames
    consolidated_df = pd.concat(dfs, ignore_index=True)
    
    # Save the consolidated DataFrame to a CSV file
    consolidated_df.to_csv(output_file, index=False)
    print(f"\nSuccessfully consolidated {len(consolidated_df)} rows into {output_file}")

if __name__ == "__main__":
    consolidate_csv_files()