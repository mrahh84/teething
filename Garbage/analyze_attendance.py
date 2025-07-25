import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import glob
import numpy as np  # Added for np.nan handling
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import configparser
import calendar

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# --- User Configuration ---
# Use relative paths for input and output from config
current_dir = os.path.dirname(os.path.abspath(__file__))
final_dir = os.path.join(current_dir, config['Paths']['final'])
consolidated_file_path = os.path.join(final_dir, 'final_sorted_consolidated_data.csv')

# Path to save the analysis results
output_dir = os.path.join(current_dir, config['Paths']['analysis'])

# Enable automatic cleanup of temporary CSV files after analysis
auto_cleanup = False  # Set to True to automatically clean up temp CSV files

# Output directory where temporary CSV files are stored
csv_output_dir = os.path.join(current_dir, config['Paths']['output'])

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

def analyze_monthly_attendance(df):
    """Analyze attendance patterns by month and create monthly reports."""
    if df is None or df.empty:
        print("No data to analyze.")
        return None
    
    # Add month and year columns
    df['Month'] = df[date_column].dt.month
    df['Year'] = df[date_column].dt.year
    df['Month_Name'] = df[date_column].dt.strftime('%B')
    df['Month_Year'] = df[date_column].dt.strftime('%Y-%m')
    
    # Get unique months
    months = df['Month_Year'].dropna().unique()
    monthly_reports = {}
    
    print(f"Creating monthly reports for {len(months)} months...")
    
    for month_year in sorted(months):
        month_data = df[df['Month_Year'] == month_year].copy()
        if month_data.empty:
            continue
            
        month_name = month_data['Month_Name'].iloc[0]
        year = int(month_data['Year'].iloc[0])
        month_num = int(month_data['Month'].iloc[0])
        
        print(f"Analyzing {month_name} {year}...")
        
        # Analyze attendance for this month
        monthly_analysis = analyze_month_data(month_data, month_name, year)
        monthly_reports[month_year] = {
            'name': f"{month_name} {year}",
            'data': monthly_analysis,
            'raw_data': month_data
        }
        
        # Save monthly report to CSV
        monthly_file = os.path.join(output_dir, f"monthly_report_{year}_{month_num:02d}_{month_name.lower()}.csv")
        monthly_analysis.to_csv(monthly_file, index=False)
        print(f"Monthly report saved to {monthly_file}")
    
    # Create monthly summary
    create_monthly_summary(monthly_reports)
    create_monthly_visualizations(monthly_reports, df)
    
    return monthly_reports

def analyze_month_data(month_df, month_name, year):
    """Analyze attendance data for a specific month."""
    employees = month_df[name_column].unique()
    
    results = []
    
    for employee in employees:
        employee_data = month_df[month_df[name_column] == employee]
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
    columns = [
        name_column,
        'Total Days Tracked',
        'Late Arrivals/Missing Stand-up Count',
        'Early Departure Count',
        'Absent During Spot-Checks Count',
        'Total Problematic Days',
        'Problematic Percentage'
    ]
    
    results_df = pd.DataFrame(results, columns=columns)
    
    # Sort by problematic percentage (descending)
    results_df['Numeric Percentage'] = results_df['Problematic Percentage'].str.rstrip('%').astype(float)
    results_df = results_df.sort_values('Numeric Percentage', ascending=False)
    results_df = results_df.drop('Numeric Percentage', axis=1)
    
    return results_df

def create_monthly_summary(monthly_reports):
    """Create a summary report comparing all months."""
    summary_data = []
    
    for month_year, report in monthly_reports.items():
        month_name = report['name']
        data = report['data']
        
        total_employees = len(data)
        total_days_tracked = data['Total Days Tracked'].sum()
        total_issues = data['Total Problematic Days'].sum()
        avg_problematic_percentage = data['Problematic Percentage'].str.rstrip('%').astype(float).mean()
        
        # Top 5 most problematic employees
        top_problematic = data.head(5)[name_column].tolist()
        
        summary_data.append([
            month_name,
            total_employees,
            total_days_tracked,
            total_issues,
            f"{avg_problematic_percentage:.2f}%",
            ', '.join(top_problematic[:3])  # Top 3 for readability
        ])
    
    summary_df = pd.DataFrame(summary_data, columns=[
        'Month',
        'Total Employees',
        'Total Days Tracked',
        'Total Issues',
        'Average Problematic %',
        'Top 3 Most Problematic'
    ])
    
    # Save summary
    summary_file = os.path.join(output_dir, "monthly_summary_report.csv")
    summary_df.to_csv(summary_file, index=False)
    print(f"Monthly summary report saved to {summary_file}")
    
    return summary_df

def create_monthly_visualizations(monthly_reports, df):
    """Create visualizations for monthly attendance patterns."""
    
    # 1. Monthly Trend Chart
    fig = go.Figure()
    
    months = []
    total_issues = []
    avg_percentages = []
    
    for month_year in sorted(monthly_reports.keys()):
        report = monthly_reports[month_year]
        data = report['data']
        
        months.append(report['name'])
        total_issues.append(data['Total Problematic Days'].sum())
        avg_percentages.append(data['Problematic Percentage'].str.rstrip('%').astype(float).mean())
    
    # Create subplot with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add total issues bar chart
    fig.add_trace(
        go.Bar(x=months, y=total_issues, name="Total Issues", marker_color='lightcoral'),
        secondary_y=False,
    )
    
    # Add average percentage line chart
    fig.add_trace(
        go.Scatter(x=months, y=avg_percentages, mode='lines+markers', 
                  name="Average Problematic %", line=dict(color='darkblue', width=3)),
        secondary_y=True,
    )
    
    # Set y-axes titles
    fig.update_yaxes(title_text="Total Issues", secondary_y=False)
    fig.update_yaxes(title_text="Average Problematic Percentage", secondary_y=True)
    
    # Set x-axis title
    fig.update_xaxes(title_text="Month")
    
    fig.update_layout(
        title="Monthly Attendance Issues Trend",
        width=1000,
        height=600
    )
    
    monthly_trend_file = os.path.join(output_dir, "monthly_trends.html")
    fig.write_html(monthly_trend_file)
    print(f"Monthly trends chart saved to {monthly_trend_file}")
    
    # 2. Top Problematic Employees by Month
    create_monthly_top_employees_chart(monthly_reports)
    
    # 3. Monthly Issue Types Breakdown
    create_monthly_issue_breakdown(monthly_reports)

def create_monthly_top_employees_chart(monthly_reports):
    """Create a chart showing top problematic employees by month."""
    fig = go.Figure()
    
    months = sorted(monthly_reports.keys())
    all_employees = set()
    
    # Get all unique employees
    for month_year, report in monthly_reports.items():
        data = report['data']
        all_employees.update(data[name_column].tolist())
    
    # Get top 10 overall problematic employees
    overall_top = {}
    for employee in all_employees:
        total_issues = 0
        for month_year, report in monthly_reports.items():
            data = report['data']
            emp_data = data[data[name_column] == employee]
            if not emp_data.empty:
                total_issues += emp_data['Total Problematic Days'].iloc[0]
        overall_top[employee] = total_issues
    
    top_10_employees = sorted(overall_top.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Create traces for each top employee
    for employee, _ in top_10_employees:
        monthly_percentages = []
        month_names = []
        
        for month_year in months:
            report = monthly_reports[month_year]
            data = report['data']
            emp_data = data[data[name_column] == employee]
            
            month_names.append(report['name'])
            if not emp_data.empty:
                percentage = float(emp_data['Problematic Percentage'].iloc[0].rstrip('%'))
                monthly_percentages.append(percentage)
            else:
                monthly_percentages.append(0)
        
        fig.add_trace(
            go.Scatter(
                x=month_names,
                y=monthly_percentages,
                mode='lines+markers',
                name=employee,
                line=dict(width=2)
            )
        )
    
    fig.update_layout(
        title="Top 10 Problematic Employees - Monthly Trends",
        xaxis_title="Month",
        yaxis_title="Problematic Percentage",
        width=1200,
        height=700,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01
        )
    )
    
    monthly_employees_file = os.path.join(output_dir, "monthly_top_employees_trends.html")
    fig.write_html(monthly_employees_file)
    print(f"Monthly top employees trends chart saved to {monthly_employees_file}")

def create_monthly_issue_breakdown(monthly_reports):
    """Create a stacked bar chart showing issue types by month."""
    months = []
    late_arrivals = []
    early_departures = []
    absent_checks = []
    
    for month_year in sorted(monthly_reports.keys()):
        report = monthly_reports[month_year]
        data = report['data']
        
        months.append(report['name'])
        late_arrivals.append(data['Late Arrivals/Missing Stand-up Count'].sum())
        early_departures.append(data['Early Departure Count'].sum())
        absent_checks.append(data['Absent During Spot-Checks Count'].sum())
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=months,
        y=late_arrivals,
        name='Late Arrivals/Missing Stand-up',
        marker_color='lightcoral'
    ))
    
    fig.add_trace(go.Bar(
        x=months,
        y=early_departures,
        name='Early Departures',
        marker_color='lightsalmon'
    ))
    
    fig.add_trace(go.Bar(
        x=months,
        y=absent_checks,
        name='Absent During Spot-Checks',
        marker_color='lightblue'
    ))
    
    fig.update_layout(
        title="Monthly Breakdown of Issue Types",
        xaxis_title="Month",
        yaxis_title="Number of Issues",
        barmode='stack',
        width=1000,
        height=600
    )
    
    monthly_breakdown_file = os.path.join(output_dir, "monthly_issue_breakdown.html")
    fig.write_html(monthly_breakdown_file)
    print(f"Monthly issue breakdown chart saved to {monthly_breakdown_file}")

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
    
    # Create a copy for file output with specific columns removed
    output_df = results_df.copy()
    output_df = output_df.drop(['Total Problematic Days', 'Problematic Percentage'], axis=1)
    
    return results_df, output_df

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

def cleanup_temp_files():
    """Clean up temporary CSV files after analysis is complete."""
    try:
        # Find all CSV files in the output directory
        csv_files = glob.glob(os.path.join(csv_output_dir, "*.csv"))
        file_count = len(csv_files)
        
        if file_count == 0:
            print("No temporary CSV files to clean up.")
            return
        
        print(f"\nCleaning up {file_count} temporary CSV files...")
        
        # Remove all CSV files
        for csv_file in csv_files:
            os.remove(csv_file)
        
        print(f"Successfully removed {file_count} temporary CSV files from {csv_output_dir}.")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")

def clean_this_df(raw_df):
    """
    Analyze problematic attendance patterns.
    This analysis focuses on employees who have multiple issues in a single day.
    
    Args:
        raw_df: Raw DataFrame with attendance data
        
    Returns:
        DataFrame with employees sorted by percentage of problematic days
    """
    # Select relevant columns
    selected_cols_df = raw_df[['DATE', 'NAMES', 'LUNCH ', 'STAND-UP', 
                               'LEFT AT ASSIGNED LUNCH TIME', 
                               'RETURNED TO WORKSTATION ON TIME AFTER LUNCH', 
                               'RETURNED  AFTER LUNCH', 'DEPARTURE TIME']]
    selected_cols_df = selected_cols_df.dropna(subset=['DATE', 'NAMES'])
    
    # Define value mapping: problematic attendance = 1, acceptable = 0, absences not counted
    # THIS MAPPING IS FORGIVING: IT DOESN'T COUNT ABSENCES AGAINST PEOPLE
    valuemap = {'NO': 1, 'YES': 0, 'ABSENT': None, np.nan: None, 'APPOINTMENT': None}
    
    # Process departure times to flag early departures (before 4:40 PM)
    def process_departure_time(time_str):
        if pd.isna(time_str) or time_str in ['ABSENT', 'APPOINTMENT']:
            return None
        try:
            # Try to parse the time string
            time_obj = pd.to_datetime(time_str).time()
            # Check if departure is before 4:40 PM
            if time_obj < datetime.strptime('16:40:00', '%H:%M:%S').time():
                return 1  # Early departure
            return 0  # On-time departure
        except:
            return None
    
    # Apply mapping to relevant columns
    if standup_column in selected_cols_df.columns:
        selected_cols_df[standup_column] = selected_cols_df[standup_column].map(lambda x: valuemap.get(x, None))
    
    if returned_on_time_column in selected_cols_df.columns:
        selected_cols_df[returned_on_time_column] = selected_cols_df[returned_on_time_column].map(lambda x: valuemap.get(x, None))
    
    if departure_column in selected_cols_df.columns:
        selected_cols_df[departure_column] = selected_cols_df[departure_column].apply(process_departure_time)
    
    # Focus only on key columns for analysis
    narrow_df = selected_cols_df[['NAMES', 'STAND-UP', 'RETURNED TO WORKSTATION ON TIME AFTER LUNCH', 'DEPARTURE TIME', 'DATE']]
    
    # Sum up problems for each employee per day
    narrow_df['problems'] = narrow_df['STAND-UP'].fillna(0) + narrow_df['RETURNED TO WORKSTATION ON TIME AFTER LUNCH'].fillna(0) + narrow_df['DEPARTURE TIME'].fillna(0)
    
    # Keep only rows with valid data
    narrow_df_problems = narrow_df[['NAMES', 'problems', 'DATE']]
    narrow_df_problems = narrow_df_problems.dropna()
    
    # Group by employee and date
    grouped_narrow_df_problems = narrow_df_problems.groupby(by=['NAMES', 'DATE']).agg({'problems': 'sum'})
    reset = grouped_narrow_df_problems.reset_index()
    
    # Find days with multiple problems (problematic days)
    greaterthan1 = reset[reset['problems'] > 1]
    greaterthan1narrow = greaterthan1[['NAMES', 'DATE']]
    
    # Calculate total working days
    total_working_days = len(raw_df['DATE'].unique())
    
    # Count problematic days per employee
    groupby = greaterthan1narrow.groupby('NAMES').count()
    groupby = groupby.reset_index()
    
    # Calculate percentage of problematic days
    groupby = groupby.rename(columns={'DATE': 'Problematic Days'})
    groupby['Problematic Percentage'] = 100 * (groupby['Problematic Days'] / total_working_days)
    
    # Sort by percentage in descending order
    groupby = groupby.sort_values('Problematic Percentage', ascending=False)
    
    return groupby

def create_plotly_top_employees(results_df):
    """Create an interactive bar chart of top problematic employees using Plotly."""
    try:
        # Get top 10 employees
        top10 = results_df.head(10).copy() if len(results_df) >= 10 else results_df.copy()
        
        # Create the bar chart
        fig = px.bar(top10, 
                     x='Problematic Percentage',
                     y='NAMES',
                     orientation='h',
                     title='Top Employees with Multiple Issues on Same Day',
                     labels={'Problematic Percentage': 'Percentage of Workdays with Multiple Issues',
                            'NAMES': 'Employee'},
                     color='Problematic Percentage',
                     color_continuous_scale='plasma')
        
        # Update layout
        fig.update_layout(
            height=600,
            width=1000,
            showlegend=False,
            yaxis={'autorange': 'reversed'},  # Reverse y-axis to show highest percentage at top
            font=dict(size=12)
        )
        
        # Save as HTML
        fig.write_html(os.path.join(output_dir, 'top_problematic_employees.html'))
        return True
    except Exception as e:
        print(f"Error creating top employees chart: {e}")
        return False

def create_plotly_infractions_chart(comprehensive_report):
    """Create a horizontal bar chart showing different types of infractions for each employee."""
    try:
        # Sort by total individual issues
        sorted_df = comprehensive_report.sort_values('Total Individual Issues', ascending=True)
        
        # Create the bar chart
        fig = go.Figure(data=[
            go.Bar(name='Stand-up Issues', 
                   y=sorted_df['NAMES'],
                   x=sorted_df['Stand-up Issues'],
                   orientation='h',
                   marker_color='#FF7F0E',
                   opacity=0.8),
            go.Bar(name='Return from Lunch Issues', 
                   y=sorted_df['NAMES'],
                   x=sorted_df['Return from Lunch Issues'],
                   orientation='h',
                   marker_color='#1F77B4',
                   opacity=0.8),
            go.Bar(name='Early Departure Issues', 
                   y=sorted_df['NAMES'],
                   x=sorted_df['Early Departure Issues'],
                   orientation='h',
                   marker_color='#D62728',
                   opacity=0.8),
            go.Bar(name='Total Individual Issues', 
                   y=sorted_df['NAMES'],
                   x=sorted_df['Total Individual Issues'],
                   orientation='h',
                   marker_color='#2CA02C',
                   opacity=0.8,
                   visible='legendonly')
        ])
        
        # Update layout
        fig.update_layout(
            title='Employee Infractions Breakdown',
            barmode='group',
            height=len(sorted_df) * 30 + 200,  # Dynamic height based on number of employees
            width=1000,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.05
            ),
            yaxis=dict(
                title='Employee',
                tickfont=dict(size=8),  # Smaller font size
                automargin=True,
                tickangle=0  # Keep labels horizontal
            ),
            xaxis=dict(
                title='Number of Infractions'
            ),
            margin=dict(l=50, r=150, t=50, b=50),  # Increased right margin for legend
            bargap=0.15,
            bargroupgap=0.1
        )
        
        # Save as HTML
        fig.write_html(os.path.join(output_dir, 'employee_infractions_chart.html'))
        return True
    except Exception as e:
        print(f"Error creating infractions chart: {e}")
        return False

def create_visualizations_from_results(results_df, comprehensive_report):
    """Create all visualizations using Plotly and save them as separate interactive HTML files."""
    if results_df is None or results_df.empty or len(results_df) == 0:
        print("No data to visualize for attendance analysis.")
        return
    
    try:
        # Create top employees visualization
        top_chart_success = create_plotly_top_employees(results_df)
        if top_chart_success:
            print(f"Top employees chart saved to {os.path.join(output_dir, 'top_problematic_employees.html')}")
        
        # Create infractions chart
        infractions_chart_success = create_plotly_infractions_chart(comprehensive_report)
        if infractions_chart_success:
            print(f"Infractions chart saved to {os.path.join(output_dir, 'employee_infractions_chart.html')}")
        
        # Create distribution chart
        distribution_chart_success = create_plotly_distribution(results_df, comprehensive_report['NAMES'].unique())
        if distribution_chart_success:
            print(f"Distribution chart saved to {os.path.join(output_dir, 'employee_distribution.html')}")
        
        if top_chart_success and infractions_chart_success and distribution_chart_success:
            print(f"\nAll interactive visualizations have been saved as separate HTML files in {output_dir}")
            print("These files can be distributed independently and maintain their interactive nature.")
        else:
            print("Some visualizations could not be created. Check the error messages above.")
            
    except Exception as e:
        print(f"Error creating visualizations: {e}")

def create_plotly_distribution(results_df, all_employees):
    """
    Create an interactive distribution graph using Plotly showing all employees' problematic percentages.
    Returns True if successful, False otherwise.
    """
    try:
        # Create a DataFrame with all employees
        all_employees_df = pd.DataFrame({'NAMES': all_employees})
        
        # Merge with results to get problematic percentages
        merged_df = pd.merge(all_employees_df, results_df, on='NAMES', how='left')
        merged_df['Problematic Percentage'] = merged_df['Problematic Percentage'].fillna(0)
        
        # Create the distribution plot
        fig = px.histogram(merged_df, 
                          x='Problematic Percentage',
                          nbins=20,
                          title='Distribution of Problematic Days Across All Employees',
                          labels={'Problematic Percentage': 'Percentage of Problematic Days (%)'},
                          color_discrete_sequence=['#636EFA'])
        
        # Add mean and median lines
        mean_val = merged_df['Problematic Percentage'].mean()
        median_val = merged_df['Problematic Percentage'].median()
        
        fig.add_vline(x=mean_val, line_dash="dash", line_color="red", 
                     annotation_text=f"Mean: {mean_val:.2f}%", 
                     annotation_position="top right")
        fig.add_vline(x=median_val, line_dash="dot", line_color="green", 
                     annotation_text=f"Median: {median_val:.2f}%", 
                     annotation_position="top left")
        
        # Update layout
        fig.update_layout(
            showlegend=False,
            xaxis_title="Percentage of Problematic Days",
            yaxis_title="Number of Employees",
            bargap=0.1,
            height=600,
            width=800
        )
        
        # Save as HTML
        fig.write_html(os.path.join(output_dir, 'employee_distribution.html'))
        return True
        
    except Exception as e:
        print(f"Error creating distribution graph: {e}")
        return False

def create_html_report(comprehensive_report, results_df, non_problematic_df):
    """Create a static HTML report with tabs for all data and visualizations."""
    try:
        html_file = os.path.join(output_dir, 'attendance_analysis_report.html')
        
        # Convert DataFrames to HTML tables with styling
        comprehensive_table = comprehensive_report.to_html(
            classes='table table-striped display',
            table_id='comprehensive-table',
            float_format=lambda x: '{:.2f}'.format(x) if isinstance(x, float) else x,
            index=False,
            justify='left'
        )
        problematic_table = results_df.to_html(
            classes='table table-striped display',
            table_id='problematic-table',
            float_format=lambda x: '{:.2f}'.format(x) if isinstance(x, float) else x,
            index=False,
            justify='left'
        )
        non_problematic_table = non_problematic_df.to_html(
            classes='table table-striped display',
            table_id='non-problematic-table',
            index=False,
            justify='left'
        )
        
        # Read visualization files
        try:
            with open(os.path.join(output_dir, 'top_problematic_employees.html'), 'r') as f:
                top_employees_viz = f.read()
                # Extract the plot content
                start_idx = top_employees_viz.find('<body>') + 6
                end_idx = top_employees_viz.find('</body>')
                top_employees_viz = top_employees_viz[start_idx:end_idx]
        except:
            top_employees_viz = "<p>Visualization not available</p>"
            
        try:
            with open(os.path.join(output_dir, 'employee_infractions_chart.html'), 'r') as f:
                infractions_viz = f.read()
                # Extract the plot content
                start_idx = infractions_viz.find('<body>') + 6
                end_idx = infractions_viz.find('</body>')
                infractions_viz = infractions_viz[start_idx:end_idx]
        except:
            infractions_viz = "<p>Visualization not available</p>"
            
        try:
            with open(os.path.join(output_dir, 'employee_distribution.html'), 'r') as f:
                distribution_viz = f.read()
                # Extract the plot content
                start_idx = distribution_viz.find('<body>') + 6
                end_idx = distribution_viz.find('</body>')
                distribution_viz = distribution_viz[start_idx:end_idx]
        except:
            distribution_viz = "<p>Visualization not available</p>"
        
        # Create HTML content
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Employee Attendance Analysis Report</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdn.datatables.net/1.11.5/css/dataTables.bootstrap5.min.css" rel="stylesheet">
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js"></script>
            <script src="https://cdn.datatables.net/1.11.5/js/dataTables.bootstrap5.min.js"></script>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ padding: 20px; }}
                .tab-content {{ margin-top: 20px; }}
                .table {{ width: 100% !important; margin-bottom: 1rem; }}
                .visualization-container {{ 
                    margin: 20px 0;
                    padding: 20px;
                    background-color: #f8f9fa;
                    border-radius: 5px;
                }}
                .dataTables_wrapper {{ margin-bottom: 20px; }}
                .plot-container {{ 
                    width: 100%;
                    margin-bottom: 30px;
                    overflow: hidden;
                }}
                .visualizations-scroll-container {{
                    max-height: 1200px;
                    overflow-y: auto;
                    padding-right: 15px;
                }}
                .dataTable {{ border-collapse: collapse !important; }}
                .dataTable thead th {{ 
                    background-color: #f8f9fa;
                    border-bottom: 2px solid #dee2e6;
                    padding: 12px;
                    text-align: left;
                }}
                .dataTable tbody td {{ 
                    padding: 12px;
                    border-bottom: 1px solid #dee2e6;
                }}
                .dataTable tbody tr:hover {{ 
                    background-color: #f5f5f5;
                }}
                .dataTables_filter input {{
                    margin-left: 10px;
                    border-radius: 4px;
                    border: 1px solid #ced4da;
                    padding: 6px 12px;
                }}
                .dataTables_length select {{
                    margin: 0 10px;
                    border-radius: 4px;
                    border: 1px solid #ced4da;
                    padding: 6px 12px;
                }}
                .dataTables_info {{
                    margin-top: 10px;
                }}
                .dataTables_paginate {{
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <h1 class="text-center mb-4">Employee Attendance Analysis Report</h1>
            
            <ul class="nav nav-tabs" id="myTab" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="comprehensive-tab" data-bs-toggle="tab" 
                            data-bs-target="#comprehensive" type="button" role="tab">
                        Comprehensive Report
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="problematic-tab" data-bs-toggle="tab" 
                            data-bs-target="#problematic" type="button" role="tab">
                        Problematic Employees
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="non-problematic-tab" data-bs-toggle="tab" 
                            data-bs-target="#non-problematic" type="button" role="tab">
                        Non-Problematic Employees
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="visualizations-tab" data-bs-toggle="tab" 
                            data-bs-target="#visualizations" type="button" role="tab">
                        Visualizations
                    </button>
                </li>
            </ul>
            
            <div class="tab-content" id="myTabContent">
                <div class="tab-pane fade show active" id="comprehensive" role="tabpanel">
                    <h3>All Employees Attendance Data</h3>
                    <div class="table-responsive">
                        {comprehensive_table}
                    </div>
                </div>
                
                <div class="tab-pane fade" id="problematic" role="tabpanel">
                    <h3>Employees with Multiple Issues on Same Day</h3>
                    <div class="table-responsive">
                        {problematic_table}
                    </div>
                </div>
                
                <div class="tab-pane fade" id="non-problematic" role="tabpanel">
                    <h3>Employees with No Multiple Issues</h3>
                    <div class="table-responsive">
                        {non_problematic_table}
                    </div>
                </div>
                
                <div class="tab-pane fade" id="visualizations" role="tabpanel">
                    <h3>Attendance Analysis Visualizations</h3>
                    <div class="visualizations-scroll-container">
                        <div class="visualization-container">
                            <h4>Top Problematic Employees</h4>
                            <div class="plot-container" style="height: 400px;">
                                {top_employees_viz}
                            </div>
                        </div>
                        <div class="visualization-container">
                            <h4>Employee Infractions Breakdown</h4>
                            <div class="plot-container" style="height: 800px;">
                                {infractions_viz}
                            </div>
                        </div>
                        <div class="visualization-container">
                            <h4>Employee Distribution</h4>
                            <div class="plot-container" style="height: 400px;">
                                {distribution_viz}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script>
                // Initialize DataTables
                $(document).ready(function() {{
                    // Configure DataTables options
                    const dataTableOptions = {{
                        pageLength: 25,
                        responsive: true,
                        autoWidth: false,
                        scrollX: true,
                        scrollCollapse: true,
                        fixedHeader: true,
                        orderCellsTop: true,
                        dom: '<"top"lf>rt<"bottom"ip>',
                        language: {{
                            search: "Search:",
                            lengthMenu: "Show _MENU_ entries",
                            info: "Showing _START_ to _END_ of _TOTAL_ entries",
                            infoEmpty: "Showing 0 to 0 of 0 entries",
                            infoFiltered: "(filtered from _MAX_ total entries)"
                        }}
                    }};
                    
                    // Initialize tables with options
                    $('#comprehensive-table').DataTable({{
                        ...dataTableOptions,
                        order: [[2, 'desc']] // Sort by Problematic Days by default
                    }});
                    
                    $('#problematic-table').DataTable({{
                        ...dataTableOptions,
                        order: [[2, 'desc']] // Sort by Problematic Days by default
                    }});
                    
                    $('#non-problematic-table').DataTable({{
                        ...dataTableOptions,
                        order: [[0, 'asc']] // Sort by Name by default
                    }});
                    
                    // Handle tab changes
                    $('button[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {{
                        // Adjust any Plotly plots in the shown tab
                        if (e.target.id === 'visualizations-tab') {{
                            $('.plot-container').each(function() {{
                                if (this.children.length > 0) {{
                                    Plotly.relayout(this.children[0], {{
                                        'width': this.offsetWidth,
                                        'height': this.offsetHeight
                                    }});
                                }}
                            }});
                        }}
                        
                        // Adjust DataTables columns when showing a tab
                        $.fn.dataTable.tables({{ visible: true, api: true }}).columns.adjust();
                    }});
                }});
            </script>
        </body>
        </html>
        '''
        
        # Write the HTML content to file
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        print(f"Interactive HTML report saved to {html_file}")
        
    except Exception as e:
        print(f"Error creating HTML report: {e}")
        import traceback
        print(traceback.format_exc())

def main():
    # Load the data
    print(f"Loading data from {consolidated_file_path}...")
    raw_df = load_data()
    
    if raw_df is None:
        print("Failed to load data. Exiting.")
        return
    
    # Get unique employees and filter out invalid names
    unique_employees = list(set(raw_df['NAMES'].str.strip().dropna()))
    unique_employees = [name for name in unique_employees if name and not name.isdigit() and name.lower() != 'nan']
    print(f"Total unique employees: {len(unique_employees)}")
    
    # Use the multiple-issues analysis method
    results_df = clean_this_df(raw_df)
    
    # Save the analysis results
    results_df.to_csv(os.path.join(output_dir, 'attendance_analysis_results.csv'), index=False)
    print(f"Analysis results saved to {os.path.join(output_dir, 'attendance_analysis_results.csv')}")
    
    # Create a comprehensive report with all employees
    all_employees_df = pd.DataFrame({'NAMES': unique_employees})
    comprehensive_report = pd.merge(all_employees_df, results_df, on='NAMES', how='left')
    
    # Fill NaN values for employees with no issues
    comprehensive_report['Problematic Days'] = comprehensive_report['Problematic Days'].fillna(0)
    comprehensive_report['Problematic Percentage'] = comprehensive_report['Problematic Percentage'].fillna(0)
    
    # Add total working days for each employee
    employee_days = raw_df.groupby('NAMES')['DATE'].nunique().reset_index()
    employee_days.columns = ['NAMES', 'Total Working Days']
    comprehensive_report = pd.merge(comprehensive_report, employee_days, on='NAMES', how='left')
    
    # Calculate additional metrics
    comprehensive_report['Non-Problematic Days'] = comprehensive_report['Total Working Days'] - comprehensive_report['Problematic Days']
    comprehensive_report['Non-Problematic Percentage'] = 100 - comprehensive_report['Problematic Percentage']
    
    # Add detailed issue breakdown
    # Get stand-up issues
    standup_issues = raw_df[raw_df['STAND-UP'] == 'NO'].groupby('NAMES').size().reset_index(name='Stand-up Issues')
    comprehensive_report = pd.merge(comprehensive_report, standup_issues, on='NAMES', how='left')
    
    # Get return from lunch issues
    return_issues = raw_df[raw_df['RETURNED TO WORKSTATION ON TIME AFTER LUNCH'] == 'NO'].groupby('NAMES').size().reset_index(name='Return from Lunch Issues')
    comprehensive_report = pd.merge(comprehensive_report, return_issues, on='NAMES', how='left')
    
    # Get early departure issues
    def is_early_departure(time_str):
        if pd.isna(time_str) or time_str in ['ABSENT', 'APPOINTMENT']:
            return False
        try:
            time_obj = pd.to_datetime(time_str).time()
            return time_obj < datetime.strptime('16:40:00', '%H:%M:%S').time()
        except:
            return False
    
    early_departures = raw_df[raw_df['DEPARTURE TIME'].apply(is_early_departure)].groupby('NAMES').size().reset_index(name='Early Departure Issues')
    comprehensive_report = pd.merge(comprehensive_report, early_departures, on='NAMES', how='left')
    
    # Fill NaN values for issue counts
    comprehensive_report['Stand-up Issues'] = comprehensive_report['Stand-up Issues'].fillna(0)
    comprehensive_report['Return from Lunch Issues'] = comprehensive_report['Return from Lunch Issues'].fillna(0)
    comprehensive_report['Early Departure Issues'] = comprehensive_report['Early Departure Issues'].fillna(0)
    
    # Calculate total individual issues
    comprehensive_report['Total Individual Issues'] = (
        comprehensive_report['Stand-up Issues'] + 
        comprehensive_report['Return from Lunch Issues'] + 
        comprehensive_report['Early Departure Issues']
    )
    
    # Sort by problematic percentage (descending)
    comprehensive_report = comprehensive_report.sort_values('Problematic Percentage', ascending=False)
    
    # Reorder columns for better readability
    column_order = [
        'NAMES',
        'Total Working Days',
        'Problematic Days',
        'Problematic Percentage',
        'Non-Problematic Days',
        'Non-Problematic Percentage',
        'Stand-up Issues',
        'Return from Lunch Issues',
        'Early Departure Issues',
        'Total Individual Issues'
    ]
    comprehensive_report = comprehensive_report[column_order]
    
    # Save the comprehensive report
    comprehensive_report.to_csv(os.path.join(output_dir, 'comprehensive_attendance_report.csv'), index=False)
    print(f"Comprehensive report saved to {os.path.join(output_dir, 'comprehensive_attendance_report.csv')}")
    
    # Generate report of non-problematic employees
    all_employees_set = set(unique_employees)
    problematic_employees_set = set(results_df['NAMES'].tolist())
    non_problematic_employees = list(all_employees_set - problematic_employees_set)
    
    # Save non-problematic employees to CSV
    non_problematic_df = pd.DataFrame({'NAMES': non_problematic_employees})
    non_problematic_df.to_csv(os.path.join(output_dir, 'non_problematic_employees.csv'), index=False)
    print(f"\nNon-problematic employees: {len(non_problematic_employees)}")
    print(f"List of non-problematic employees saved to {os.path.join(output_dir, 'non_problematic_employees.csv')}")
    
    # Create visualizations
    create_visualizations_from_results(results_df, comprehensive_report)
    
    # Create HTML report with all data and visualizations
    create_html_report(comprehensive_report, results_df, non_problematic_df)
    
    # Create monthly analysis reports
    print("\n" + "="*70)
    print("CREATING MONTHLY ANALYSIS REPORTS")
    print("="*70)
    monthly_reports = analyze_monthly_attendance(raw_df)
    
    # Clean up temporary files if enabled
    if auto_cleanup:
        cleanup_temp_files()

if __name__ == "__main__":
    main() 