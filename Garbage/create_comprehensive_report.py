import pandas as pd
import os

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(current_dir, 'analysis')

# Read the raw consolidated data
consolidated_file_path = os.path.join(current_dir, 'final', 'final_sorted_consolidated_data.csv')
df = pd.read_csv(consolidated_file_path)

# Read the attendance analysis results (alternative analysis)
attendance_results = pd.read_csv(os.path.join(output_dir, 'attendance_analysis_results.csv'))

# Create a list of all employees from the raw data
all_employees = list(set(df['NAMES'].str.strip().dropna()))
all_employees = [name for name in all_employees if name and not name.isdigit() and name.lower() != 'nan']

# Create a new comprehensive report
report_data = []

# For each employee, calculate metrics
for employee in all_employees:
    employee_data = df[df['NAMES'] == employee]
    total_days = len(employee_data)
    
    # Skip employees with no data
    if total_days == 0:
        continue
    
    # Count detailed patterns
    late_arrivals = sum(employee_data['STAND-UP'].fillna('').isin(['NO', 'LATE', 'ABSENT']))
    early_departures = sum(employee_data['LEFT AT ASSIGNED LUNCH TIME'].fillna('').isin(['NO', 'LATE', 'ABSENT']))
    missed_returns = sum(employee_data['RETURNED TO WORKSTATION ON TIME AFTER LUNCH'].fillna('').isin(['NO', 'LATE', 'ABSENT']))
    after_lunch_issues = sum(employee_data['RETURNED  AFTER LUNCH'].fillna('').isin(['NO', 'LATE', 'ABSENT']))
    
    # Check if employee is in the alternative analysis (problematic only if they have multiple issues on same day)
    alt_row = attendance_results[attendance_results['NAMES'] == employee]
    if not alt_row.empty:
        alt_problematic_days = alt_row['Problematic Days'].values[0]
        alt_problematic_pct = alt_row['Problematic Percentage'].values[0]
        is_problematic = True
    else:
        alt_problematic_days = 0
        alt_problematic_pct = 0
        is_problematic = False
    
    # Add to the report data
    report_data.append({
        'Employee': employee,
        'Total Days Tracked': total_days,
        'Late Arrivals/Missing Stand-up': late_arrivals,
        'Early Departures': early_departures,
        'Missed Returns': missed_returns,
        'After Lunch Issues': after_lunch_issues,
        'Problematic Days (Multiple Issues)': alt_problematic_days,
        'Problematic Percentage': alt_problematic_pct,
        'Is Problematic': 'Yes' if is_problematic else 'No'
    })

# Create the comprehensive report DataFrame
comprehensive_report = pd.DataFrame(report_data)

# Sort by problematic percentage (descending)
comprehensive_report = comprehensive_report.sort_values('Problematic Percentage', ascending=False)

# Save the comprehensive report
comprehensive_report.to_csv(os.path.join(output_dir, 'comprehensive_employee_report.csv'), index=False)
print(f'Comprehensive employee report saved to {os.path.join(output_dir, "comprehensive_employee_report.csv")}') 