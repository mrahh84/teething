import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

# --- User Configuration ---
# Path to the consolidated data file
consolidated_file_path = r'final/final_sorted_consolidated_data.csv'

# Path to save the analysis results
output_dir = r'analysis'

# Column names - adjust these if your column names are different
name_column = 'NAMES'
date_column = 'DATE'
lunch_time_column = 'LUNCH '  # Note the trailing space
left_lunch_column = 'LEFT AT ASSIGNED LUNCH TIME'
returned_on_time_column = 'RETURNED TO WORKSTATION ON TIME AFTER LUNCH'
returned_after_lunch_column = 'RETURNED  AFTER LUNCH'  # Note the double space
standup_column = 'STAND-UP'
departure_column = 'DEPARTURE TIME'

# Define what constitutes problematic patterns
problematic_values = ['NO', 'ABSENT', 'LATE']
# --- End of User Configuration ---

# Create output directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Created output directory: {output_dir}")

def load_data():
    """Load and prepare the attendance data."""
    try:
        df = pd.read_csv(consolidated_file_path)
        # Convert DATE to datetime
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def analyze_attendance(df):
    """Analyze attendance patterns and identify problematic behaviors."""
    if df is None or df.empty:
        print("No data to analyze.")
        return
    
    # Create a results dataframe to store summary statistics
    columns = [
        'Total Days Tracked',
        'Late Arrivals/Missing Stand-up Count',
        'Early Departure Count',
        'Absent During Spot-Checks Count',
        'Total Problematic Days',
        'Problematic Percentage'
    ]
    
    return df
    
    results = []
    
    # Get unique employees
    employees = df[name_column].unique()
    
    print(f"Analyzing attendance patterns for {len(employees)} employees...")
    
    # Analyze each employee
    for employee in employees:
        employee_data = df[df[name_column] == employee]
        total_days = len(employee_data)
        
        # Count problematic patterns
        late_arrivals = 0
        early_departures = 0
        absent_spot_checks = 0
        
        for _, row in employee_data.iterrows():
            # Check for late arrivals/missing standup
            if standup_column in row and any(val in str(row[standup_column]) for val in problematic_values):
                late_arrivals += 1
            
            # Check for early departures (not leaving at assigned lunch time)
            if left_lunch_column in row and any(val in str(row[left_lunch_column]) for val in problematic_values):
                early_departures += 1
                
            # Check for spot-check absences
            if returned_on_time_column in row and any(val in str(row[returned_on_time_column]) for val in problematic_values):
                absent_spot_checks += 1
            
            # Also check if they returned after lunch (additional spot check)
            if returned_after_lunch_column in row and any(val in str(row[returned_after_lunch_column]) for val in problematic_values):
                absent_spot_checks += 1
        
        # Calculate total problematic days and percentage
        total_problematic = late_arrivals + early_departures + absent_spot_checks
        problematic_percentage = (total_problematic / (total_days * 3)) * 100 if total_days > 0 else 0
        
        # Add to results
        results.append([
            employee,
            total_days,
            late_arrivals,
            early_departures,
            absent_spot_checks,
            total_problematic,
            f"{problematic_percentage:.2f}%"
        ])
    
    # Create results DataFrame
    results_df = pd.DataFrame(results, columns=[name_column] + columns)
    
    # Sort by problematic percentage (descending)
    results_df['Numeric Percentage'] = results_df['Problematic Percentage'].str.rstrip('%').astype(float)
    results_df = results_df.sort_values('Numeric Percentage', ascending=False)
    results_df = results_df.drop('Numeric Percentage', axis=1)
    
    return results_df

def create_visualizations(results_df):
    """Create visualizations of attendance patterns."""
    if results_df is None or results_df.empty:
        print("No data to visualize.")
        return
    
    # Set up the style
    sns.set(style="whitegrid")
    
    # 1. Top 10 employees with highest problematic percentage
    plt.figure(figsize=(12, 8))
    top10 = results_df.head(10).copy()
    top10['Problematic Percentage'] = top10['Problematic Percentage'].str.rstrip('%').astype(float)
    
    sns.barplot(x='Problematic Percentage', y=name_column, data=top10, palette='viridis')
    plt.title('Top 10 Employees with Highest Problematic Attendance', fontsize=16)
    plt.xlabel('Problematic Percentage', fontsize=12)
    plt.ylabel('Employee', fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'top10_problematic_employees.png'))
    
    # 2. Breakdown of problematic patterns
    plt.figure(figsize=(15, 10))
    problem_types = ['Late Arrivals/Missing Stand-up Count', 
                     'Early Departure Count', 
                     'Absent During Spot-Checks Count']
    
    # Filter to top 15 employees by total problematic days
    top15 = results_df.sort_values('Total Problematic Days', ascending=False).head(15)
    
    # Melt the DataFrame for easier plotting
    melted_df = pd.melt(top15, 
                        id_vars=[name_column], 
                        value_vars=problem_types,
                        var_name='Problem Type', 
                        value_name='Count')
    
    # Clean up the problem type names for display
    melted_df['Problem Type'] = melted_df['Problem Type'].str.replace(' Count', '')
    
    # Create the plot
    sns.barplot(x='Count', y=name_column, hue='Problem Type', data=melted_df, palette='muted')
    plt.title('Breakdown of Problematic Attendance Patterns (Top 15 Employees)', fontsize=16)
    plt.xlabel('Count of Occurrences', fontsize=12)
    plt.ylabel('Employee', fontsize=12)
    plt.legend(title='Problem Type', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'problem_type_breakdown.png'))
    
    print(f"Visualizations saved to {output_dir}")

def clean_this_df(raw_df):
	selected_cols_df=raw_df[['DATE', 'NAMES', 'LUNCH ', 'STAND-UP', 'LEFT AT ASSIGNED LUNCH TIME','RETURNED TO WORKSTATION ON TIME AFTER LUNCH', 'RETURNED  AFTER LUNCH','DEPARTURE TIME']]
	selected_cols_df=selected_cols_df.dropna()
	#THIS MAPPING IS FORGIVING: IT DOESN'T COUNT ABSENCES AGAINST PEOPLE
	#TO DO THAT, SET ABSENT AND/OR APPOINTMENT TO 1
	valuemap={'NO': 1, 'YES': 0, 'ABSENT': None, np.nan: None, 'APPOINTMENT': None}
	selected_cols_df['STAND-UP']=selected_cols_df['STAND-UP'].apply(lambda x: valuemap[x])
	selected_cols_df['RETURNED TO WORKSTATION ON TIME AFTER LUNCH']=selected_cols_df['RETURNED TO WORKSTATION ON TIME AFTER LUNCH'].apply(lambda x: valuemap[x])
	narrow_df=selected_cols_df[['NAMES','STAND-UP','RETURNED TO WORKSTATION ON TIME AFTER LUNCH','DATE']]
	narrow_df['problems']=narrow_df['STAND-UP']+narrow_df['RETURNED TO WORKSTATION ON TIME AFTER LUNCH']
	narrow_df_problems=narrow_df[['NAMES','problems','DATE']]
	narrow_df_problems=narrow_df_problems.dropna()
	grouped_narrow_df_problems=narrow_df_problems.groupby(by=['NAMES','DATE']).agg({'problems':'sum'})
	reset=grouped_narrow_df_problems.reset_index()
	greaterthan1=reset[reset['problems']>1]
	greaterthan1narrow=greaterthan1['NAMES']
	total_working_days=len(raw_df['DATE'].unique())
	greaterthan1narrow=greaterthan1[['NAMES','DATE']]
	groupby=greaterthan1narrow.groupby('NAMES').count()
	groupby=groupby.reset_index()
	#THEN RENAME THAT ERRONEOUSLY-NAMED DATE COLUMN PLEASE
	groupby['percent']=100*(groupby['DATE']/total_working_days)
	#then graph it
	return groupby

def save_monthly_analysis(raw_df):
    """
    For each month in the data, run clean_this_df and save the results to a CSV file.
    Also, create a summary CSV listing all months and the number of problematic employees per month.
    """
    if 'DATE' not in raw_df.columns:
        print("No DATE column found in data.")
        return
    raw_df['MONTH'] = raw_df['DATE'].dt.to_period('M')
    months = raw_df['MONTH'].dropna().unique()
    summary = []
    for month in months:
        month_df = raw_df[raw_df['MONTH'] == month]
        result = clean_this_df(month_df)
        out_path = os.path.join(output_dir, f'attendance_analysis_{month}.csv')
        result.to_csv(out_path, index=False)
        print(f"Saved monthly analysis for {month} to {out_path}")
        summary.append({'Month': str(month), 'Problematic Employees': len(result)})
    # Save summary CSV
    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(os.path.join(output_dir, 'monthly_problematic_summary.csv'), index=False)
    print(f"Saved monthly summary to {os.path.join(output_dir, 'monthly_problematic_summary.csv')}")

def main():
    # Load the data
    print(f"Loading data from {consolidated_file_path}...")
    raw_df = load_data()
    if raw_df is None:
        print("Failed to load data. Exiting.")
        return
    # Run overall analysis
    clean_df = clean_this_df(raw_df)
    clean_df.to_csv(os.path.join(output_dir, 'attendance_analysis_results.csv'), index=False)
    print(f"Saved overall analysis to {os.path.join(output_dir, 'attendance_analysis_results.csv')}")
    # Run monthly analysis
    save_monthly_analysis(raw_df)
    return clean_df

if __name__ == "__main__":
    main() 