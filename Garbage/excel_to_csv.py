import pandas as pd
import os
from datetime import datetime
import glob
import configparser
import numpy as np
import logging

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Define paths from config
def find_excel_file():
    original_dir = config['Paths']['original']
    # Look for REPORT_2025.xlsx first, then fallback to any REPORT_*.xlsx
    candidates = glob.glob(f'{original_dir}/REPORT_2025.xlsx')
    if candidates:
        return candidates[0]
    # Fallback: find the latest REPORT_*.xlsx
    all_reports = sorted(glob.glob(f'{original_dir}/REPORT_*.xlsx'))
    if all_reports:
        return all_reports[-1]
    raise FileNotFoundError(f"No suitable Excel report file found in '{original_dir}/' directory.")

excel_file = os.environ.get('REPORT_EXCEL_FILE', find_excel_file())
logging.info(f"Using Excel file: {excel_file}")
output_folder = config['Paths']['output']

# Create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

# Define the expected column structure
EXPECTED_COLUMNS = [
    'DATE', 'NAMES', 'LUNCH ', 'STAND-UP', 
    'LEFT AT ASSIGNED LUNCH TIME', 
    'RETURNED TO WORKSTATION ON TIME AFTER LUNCH',
    'RETURNED  AFTER LUNCH', 
    'DEPARTURE TIME'
]

def process_departure_time(time_str):
    """Process departure time to ensure consistent format."""
    if pd.isna(time_str):
        return time_str
    
    # Handle string conversion
    time_str = str(time_str).strip()
    
    # Handle common time format issues
    time_str = time_str.replace('OPM', 'PM').replace('OAM', 'AM')
    
    try:
        # Try to parse the time string
        time_obj = pd.to_datetime(time_str).time()
        # Format as HH:MM AM/PM
        return time_obj.strftime("%I:%M %p")
    except:
        # Return as-is if parsing fails
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
    return value

def fix_sheet_headers(df, sheet_name):
    """
    Fix DataFrame headers - detect if actual headers are in the first row
    and handle mixed production schedule data.
    """
    logging.debug(f"Fixing headers for {sheet_name}...")
    
    # First, check if we already have proper headers
    proper_headers = False
    for col in df.columns:
        if 'DATE' in str(col).upper() and 'NAMES' in str(col).upper():
            # If we find both DATE and NAMES in column headers, we likely have proper headers
            proper_headers = True
            break
        elif 'DATE' in str(col).upper():
            # Check if NAMES appears in any other column
            for other_col in df.columns:
                if 'NAMES' in str(other_col).upper():
                    proper_headers = True
                    break
    
    if proper_headers:
        logging.debug(f"Sheet {sheet_name} already has proper headers")
        # Handle production schedule columns (April-June sheets)
        # Look for attendance data starting from column that contains 'DATE'
        date_col_idx = None
        for idx, col in enumerate(df.columns):
            if 'DATE' in str(col).upper():
                date_col_idx = idx
                break
        
        if date_col_idx is not None and date_col_idx > 0:
            logging.debug(f"Found DATE column at index {date_col_idx}, removing production schedule columns")
            # Keep only columns from DATE onwards
            df = df.iloc[:, date_col_idx:].reset_index(drop=True)
        
        return df
    
    # Check if we have unnamed columns (headers likely in first row)
    unnamed_cols = [col for col in df.columns if str(col).startswith('Unnamed:')]
    
    if len(unnamed_cols) > 4:  # Most columns are unnamed
        logging.debug(f"Found {len(unnamed_cols)} unnamed columns, checking first row for headers...")
        
        # Look for the row that contains our expected headers
        header_row_idx = None
        for idx in range(min(5, len(df))):  # Check first 5 rows
            row_values = df.iloc[idx].astype(str).str.upper()
            date_found = any('DATE' in val for val in row_values)
            names_found = any('NAME' in val for val in row_values)
            
            if date_found and names_found:
                header_row_idx = idx
                break
        
        if header_row_idx is not None:
            logging.debug(f"Found headers in row {header_row_idx}")
            # Use that row as headers
            new_headers = df.iloc[header_row_idx].fillna('').astype(str)
            df.columns = new_headers
            # Remove the header row and everything before it
            df = df.iloc[header_row_idx + 1:].reset_index(drop=True)
        else:
            logging.warning(f"Could not find header row in {sheet_name}")
            return None
    
    # Handle production schedule columns (April-June sheets)
    # Look for attendance data starting from column that contains 'DATE'
    date_col_idx = None
    for idx, col in enumerate(df.columns):
        if 'DATE' in str(col).upper():
            date_col_idx = idx
            break
    
    if date_col_idx is not None and date_col_idx > 0:
        logging.debug(f"Found DATE column at index {date_col_idx}, removing production schedule columns")
        # Keep only columns from DATE onwards
        df = df.iloc[:, date_col_idx:].reset_index(drop=True)
    
    return df

def find_data_columns(df, sheet_name):
    """
    Intelligently find the correct data columns in the DataFrame,
    handling different sheet formats.
    """
    logging.debug(f"Analyzing column structure for {sheet_name}...")
    
    # Look for the key columns we need
    column_mapping = {}
    
    # Find DATE column
    for col in df.columns:
        if 'DATE' in str(col).upper():
            column_mapping['DATE'] = col
            break
    
    # Find NAMES column
    for col in df.columns:
        if 'NAME' in str(col).upper():  # More flexible matching
            column_mapping['NAMES'] = col
            break
    
    # Find other columns by pattern matching
    column_patterns = {
        'LUNCH ': ['LUNCH', 'LUNCH '],
        'STAND-UP': ['STAND-UP', 'STANDUP', 'STAND UP'],
        'LEFT AT ASSIGNED LUNCH TIME': ['LEFT AT ASSIGNED LUNCH TIME', 'LEFT AT LUNCH'],
        'RETURNED TO WORKSTATION ON TIME AFTER LUNCH': ['RETURNED TO WORKSTATION ON TIME AFTER LUNCH', 'RETURNED ON TIME'],
        'RETURNED  AFTER LUNCH': ['RETURNED  AFTER LUNCH', 'RETURNED AFTER LUNCH'],
        'DEPARTURE TIME': ['DEPARTURE TIME', 'DEPARTURE']
    }
    
    for expected_col, patterns in column_patterns.items():
        for col in df.columns:
            col_str = str(col).upper().strip()
            for pattern in patterns:
                if pattern.upper() in col_str:
                    column_mapping[expected_col] = col
                    break
            if expected_col in column_mapping:
                break
    
    logging.debug(f"Found column mappings for {sheet_name}: {column_mapping}")
    return column_mapping

def correct_date_from_sheet_name(sheet_name):
    """
    Extract the correct date from the sheet name.
    Sheet names are in format REPORT_MM_DD_YYYY which should be the correct date.
    """
    import re
    match = re.match(r'REPORT_(\d{2})_(\d{2})_(\d{4})', sheet_name)
    if match:
        month, day, year = match.groups()
        correct_date = f"{year}-{month}-{day}"
        logging.debug(f"Extracted correct date from sheet name {sheet_name}: {correct_date}")
        return correct_date
    return None

def normalize_dataframe(df, column_mapping, sheet_name):
    """
    Create a normalized DataFrame with consistent column structure.
    """
    logging.debug(f"Normalizing data structure for {sheet_name}...")
    
    # Create a new DataFrame with the expected columns
    normalized_df = pd.DataFrame()
    
    for expected_col in EXPECTED_COLUMNS:
        if expected_col in column_mapping:
            original_col = column_mapping[expected_col]
            normalized_df[expected_col] = df[original_col].copy()
        else:
            # Create empty column if not found
            normalized_df[expected_col] = np.nan
            logging.warning(f"Column '{expected_col}' not found in {sheet_name}, creating empty column")
    
    # Filter out rows that don't contain actual attendance data
    # Remove rows where both DATE and NAMES are empty/NaN
    before_count = len(normalized_df)
    normalized_df = normalized_df.dropna(subset=['DATE', 'NAMES'], how='all')
    
    # Remove rows that contain only scheduling information or headers
    mask = normalized_df['NAMES'].astype(str).str.contains(
        r'PRODUCTION|SCHEDULE|TRAINEES|LUNCH \d|^\s*$|^Unnamed|^DATE$|^NAMES$', 
        case=False, na=False
    )
    normalized_df = normalized_df[~mask]
    
    # Remove rows where DATE is not a valid date
    try:
        # Try to convert DATE column to datetime to filter invalid dates
        date_mask = pd.to_datetime(normalized_df['DATE'], errors='coerce').notna()
        normalized_df = normalized_df[date_mask]
    except:
        pass
    
    # CRITICAL FIX: Correct the date based on sheet name
    # The Excel file has incorrect dates - the sheet name is the source of truth
    correct_date = correct_date_from_sheet_name(sheet_name)
    if correct_date and 'DATE' in normalized_df.columns:
        original_date = normalized_df['DATE'].iloc[0] if len(normalized_df) > 0 else None
        if original_date:
            logging.info(f"Correcting date in {sheet_name}: {original_date} → {correct_date}")
        normalized_df['DATE'] = correct_date
    
    after_count = len(normalized_df)
    logging.debug(f"Filtered data for {sheet_name}: {before_count} → {after_count} rows (removed {before_count - after_count} non-data rows)")
    
    return normalized_df

def clean_sheet_name(sheet_name):
    """Clean up sheet names to be valid filenames."""
    # Remove problematic characters
    cleaned = sheet_name.strip()
    cleaned = cleaned.replace(')', '').replace('(', '')
    cleaned = cleaned.replace('  ', ' ')  # Replace double spaces with single
    return cleaned

try:
    # Load the Excel file
    xls = pd.ExcelFile(excel_file)
    
    # Get all sheet names
    sheet_names = xls.sheet_names
    
    logging.info(f"Found {len(sheet_names)} sheets in the Excel file")
    for sheet_name in sheet_names:
        logging.debug(f"Sheet found: {sheet_name}")
    
    successful_sheets = 0
    failed_sheets = 0
    
    # Process each sheet
    for sheet_name in sheet_names:
        # Skip production schedule sheet
        if 'PRODUCTION SCHEDULE' in sheet_name.upper():
            logging.info(f"Skipping production schedule sheet: {sheet_name}")
            continue
            
        logging.info(f"Processing sheet: {sheet_name}")
        
        try:
            # Read the sheet
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            if df.empty:
                logging.warning(f"Skipping empty sheet: {sheet_name}")
                continue
            
            # Fix headers if needed
            df = fix_sheet_headers(df, sheet_name)
            if df is None:
                logging.warning(f"Could not fix headers for {sheet_name}, skipping...")
                failed_sheets += 1
                continue
            
            # Find the correct columns in this sheet
            column_mapping = find_data_columns(df, sheet_name)
            
            # Check if we found the essential columns
            if 'DATE' not in column_mapping or 'NAMES' not in column_mapping:
                logging.warning(f"Essential columns not found in {sheet_name}, skipping...")
                failed_sheets += 1
                continue
            
            # Normalize the DataFrame structure
            normalized_df = normalize_dataframe(df, column_mapping, sheet_name)
            
            if normalized_df.empty:
                logging.warning(f"No valid data found in {sheet_name}, skipping...")
                failed_sheets += 1
                continue
            
            # Process STAND-UP column if it exists
            if 'STAND-UP' in normalized_df.columns:
                normalized_df['STAND-UP'] = normalized_df['STAND-UP'].apply(process_standup)
            
            # Process DEPARTURE TIME column if it exists
            if 'DEPARTURE TIME' in normalized_df.columns:
                normalized_df['DEPARTURE TIME'] = normalized_df['DEPARTURE TIME'].apply(process_departure_time)
            
            # Clean the sheet name for filename
            clean_name = clean_sheet_name(sheet_name)
            output_file = os.path.join(output_folder, f"{clean_name}.csv")
            
            # Save as CSV
            normalized_df.to_csv(output_file, index=False)
            logging.info(f"Successfully saved {len(normalized_df)} rows to {output_file}")
            successful_sheets += 1
            
        except Exception as e:
            logging.error(f"Error processing {sheet_name}: {str(e)}")
            failed_sheets += 1
            continue
    
    logging.info("="*70)
    logging.info("EXCEL TO CSV PROCESSING SUMMARY:")
    logging.info(f"Total sheets: {len(sheet_names)}")
    logging.info(f"Successfully processed: {successful_sheets}")
    logging.info(f"Failed to process: {failed_sheets}")
    logging.info(f"Success rate: {(successful_sheets/len(sheet_names)*100):.1f}%")
    logging.info("="*70)

except FileNotFoundError:
    logging.error(f"Could not find the Excel file at {excel_file}")
except Exception as e:
    logging.error(f"An error occurred: {str(e)}")