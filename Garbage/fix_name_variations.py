import pandas as pd
import re
import logging

def standardize_employee_names(df):
    """
    Standardize employee names to fix data fragmentation issues.
    """
    logging.info("Starting name standardization process...")
    
    # Create a copy to work with
    df_cleaned = df.copy()
    
    # Track changes made
    changes_made = []
    
    # Define name standardization rules
    name_mappings = {
        # Fix spacing issues in hyphenated names
        'Kriss- Lynn Leslie': 'Kriss-Lynn Leslie',
        'Kris-Lynn Leslie': 'Kriss-Lynn Leslie',  # In case there are other variations
        
        # Fix misspellings
        'Renika Grifftih': 'Renika Griffith',
        'Renika Grifftih ': 'Renika Griffith',  # Handle trailing spaces
        
        # Fix spacing in compound names
        'AshleyMohamed': 'Ashley Mohamed',
        
        # Handle other potential variations
        'Allia Kellman': 'Allia Leandre Kellman',
        'Riquelma Knight': 'Riquelme Knight',
        'Trudy Sealy': 'Trudi Sealy',
        'Tamesha Yearwood': 'Tamisha Yearwood',
        
        # Handle names with inconsistent spacing
        'Shania St Clair': 'Shania St. Clair',
        'Shania St.Clair': 'Shania St. Clair',
    }
    
    # Apply name standardizations
    original_count = len(df_cleaned)
    for old_name, new_name in name_mappings.items():
        mask = df_cleaned['NAMES'] == old_name
        if mask.any():
            count = mask.sum()
            df_cleaned.loc[mask, 'NAMES'] = new_name
            changes_made.append(f"'{old_name}' → '{new_name}' ({count} records)")
            logging.info(f"Standardized '{old_name}' to '{new_name}' ({count} records)")
    
    # Additional cleanup: remove extra spaces and standardize formatting
    df_cleaned['NAMES'] = df_cleaned['NAMES'].str.strip()
    df_cleaned['NAMES'] = df_cleaned['NAMES'].str.replace(r'\s+', ' ', regex=True)  # Multiple spaces to single space
    
    # Remove any completely empty name rows
    before_empty_removal = len(df_cleaned)
    df_cleaned = df_cleaned[df_cleaned['NAMES'].notna() & (df_cleaned['NAMES'] != '')]
    after_empty_removal = len(df_cleaned)
    
    if before_empty_removal != after_empty_removal:
        removed_count = before_empty_removal - after_empty_removal
        changes_made.append(f"Removed {removed_count} rows with empty names")
        logging.info(f"Removed {removed_count} rows with empty names")
    
    # Report summary
    logging.info(f"Name standardization completed:")
    logging.info(f"- Original records: {original_count}")
    logging.info(f"- Final records: {len(df_cleaned)}")
    logging.info(f"- Changes made: {len(changes_made)}")
    
    for change in changes_made:
        logging.info(f"  • {change}")
    
    return df_cleaned, changes_made

def analyze_name_duplicates(df):
    """
    Analyze potential duplicate names that might need standardization.
    """
    logging.info("Analyzing potential name duplicates...")
    
    # Get unique names
    unique_names = df['NAMES'].unique()
    
    # Look for similar names
    potential_duplicates = []
    
    for i, name1 in enumerate(unique_names):
        if pd.isna(name1) or name1 == '':
            continue
        for j, name2 in enumerate(unique_names[i+1:], i+1):
            if pd.isna(name2) or name2 == '':
                continue
            
            # Check for similar names (simple similarity check)
            name1_clean = re.sub(r'[^a-zA-Z]', '', name1.lower())
            name2_clean = re.sub(r'[^a-zA-Z]', '', name2.lower())
            
            # Check if names are very similar (allowing for minor differences)
            if (len(name1_clean) > 3 and len(name2_clean) > 3 and
                (name1_clean in name2_clean or name2_clean in name1_clean or
                 abs(len(name1_clean) - len(name2_clean)) <= 2)):
                
                count1 = len(df[df['NAMES'] == name1])
                count2 = len(df[df['NAMES'] == name2])
                potential_duplicates.append((name1, count1, name2, count2))
    
    if potential_duplicates:
        logging.warning("Potential duplicate names found:")
        for name1, count1, name2, count2 in potential_duplicates:
            logging.warning(f"  • '{name1}' ({count1} records) vs '{name2}' ({count2} records)")
    
    return potential_duplicates

def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Read the consolidated data
    input_file = 'final/consolidated_data.csv'
    output_file = 'final/consolidated_data_fixed.csv'
    
    logging.info(f"Reading data from {input_file}")
    df = pd.read_csv(input_file)
    
    logging.info(f"Original data: {len(df)} records, {df['NAMES'].nunique()} unique names")
    
    # Analyze potential duplicates before fixing
    potential_duplicates = analyze_name_duplicates(df)
    
    # Standardize names
    df_fixed, changes = standardize_employee_names(df)
    
    logging.info(f"Fixed data: {len(df_fixed)} records, {df_fixed['NAMES'].nunique()} unique names")
    
    # Save the fixed data
    df_fixed.to_csv(output_file, index=False)
    logging.info(f"Fixed data saved to {output_file}")
    
    # Also update the main consolidated file
    df_fixed.to_csv(input_file, index=False)
    logging.info(f"Original file updated: {input_file}")
    
    # Create a summary report
    summary_file = 'analysis/name_standardization_report.txt'
    with open(summary_file, 'w') as f:
        f.write("EMPLOYEE NAME STANDARDIZATION REPORT\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Original records: {len(df)}\n")
        f.write(f"Fixed records: {len(df_fixed)}\n")
        f.write(f"Original unique names: {df['NAMES'].nunique()}\n")
        f.write(f"Fixed unique names: {df_fixed['NAMES'].nunique()}\n\n")
        f.write("CHANGES MADE:\n")
        f.write("-" * 20 + "\n")
        for change in changes:
            f.write(f"• {change}\n")
        
        if potential_duplicates:
            f.write(f"\nPOTENTIAL DUPLICATES FOUND:\n")
            f.write("-" * 30 + "\n")
            for name1, count1, name2, count2 in potential_duplicates:
                f.write(f"• '{name1}' ({count1} records) vs '{name2}' ({count2} records)\n")
    
    logging.info(f"Summary report saved to {summary_file}")
    
    return len(changes) > 0

if __name__ == "__main__":
    changes_made = main()
    if changes_made:
        print("\n" + "="*60)
        print("NAME STANDARDIZATION COMPLETED!")
        print("="*60)
        print("Changes were made to fix employee name variations.")
        print("Please re-run the analysis to get corrected results.")
        print("Check 'analysis/name_standardization_report.txt' for details.")
    else:
        print("No name standardization changes were needed.") 