#!/usr/bin/env python3
import pandas as pd
import os
import configparser
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Define paths
current_dir = os.path.dirname(os.path.abspath(__file__))
final_dir = os.path.join(current_dir, config['Paths']['final'])
output_dir = os.path.join(current_dir, config['Paths']['analysis'])

# File paths
consolidated_file_path = os.path.join(final_dir, 'consolidated_data.csv')

# Column names
name_column = 'NAMES'
date_column = 'DATE'
standup_column = 'STAND-UP'
left_lunch_column = 'LEFT AT ASSIGNED LUNCH TIME'
returned_on_time_column = 'RETURNED TO WORKSTATION ON TIME AFTER LUNCH'
returned_after_lunch_column = 'RETURNED  AFTER LUNCH'
departure_column = 'DEPARTURE TIME'

# Problematic values
problematic_values = ['NO', 'ABSENT', 'APPOINTMENT']

def load_june_data():
    """Load and filter data for June 2025 only."""
    try:
        df = pd.read_csv(consolidated_file_path)
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        
        # Filter for June 2025 only
        june_df = df[df[date_column].dt.strftime('%Y-%m') == '2025-06'].copy()
        
        print(f"Loaded {len(june_df)} records for June 2025")
        print(f"Date range: {june_df[date_column].min()} to {june_df[date_column].max()}")
        print(f"Unique employees: {june_df[name_column].nunique()}")
        
        return june_df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def analyze_june_attendance(df):
    """Analyze June attendance patterns."""
    if df is None or df.empty:
        print("No June data to analyze.")
        return None
    
    # Get unique employees
    employees = df[name_column].unique()
    results = []
    
    for employee in employees:
        employee_data = df[df[name_column] == employee]
        total_days = len(employee_data)
        
        # Count problematic patterns
        late_arrivals = 0
        early_departures = 0
        absent_spot_checks = 0
        problematic_by_date = []
        
        for _, row in employee_data.iterrows():
            this_date_count = 0
            
            # Check for late arrivals/missing standup
            if standup_column in row and any(val in str(row[standup_column]) for val in problematic_values):
                late_arrivals += 1
                this_date_count += 1
            
            # Check for early departures (not leaving at assigned lunch time)
            if left_lunch_column in row and any(val in str(row[left_lunch_column]) for val in problematic_values):
                early_departures += 1
                this_date_count += 1
                
            # Check for spot-check absences
            if returned_on_time_column in row and any(val in str(row[returned_on_time_column]) for val in problematic_values):
                absent_spot_checks += 1
                this_date_count += 1
            
            # Also check if they returned after lunch (additional spot check)
            if returned_after_lunch_column in row and any(val in str(row[returned_after_lunch_column]) for val in problematic_values):
                absent_spot_checks += 1
                this_date_count += 1
            
            # Only track days with MULTIPLE issues (same as comprehensive report)
            if this_date_count > 1:
                problematic_by_date.append(this_date_count)
        
        # Calculate total problematic days and percentage
        total_problematic = late_arrivals + early_departures + absent_spot_checks
        # Calculate percentage of days with problems (same as comprehensive report)
        problematic_percentage = (len(problematic_by_date) / total_days) * 100 if total_days > 0 else 0
        
        results.append({
            'NAMES': employee,
            'Total Days Tracked': total_days,
            'Late Arrivals/Missing Stand-up Count': late_arrivals,
            'Early Departure Count': early_departures,
            'Absent During Spot-Checks Count': absent_spot_checks,
            'Total Problematic Days': total_problematic,
            'Problematic Percentage': problematic_percentage
        })
    
    # Create results DataFrame and sort by problematic percentage
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('Problematic Percentage', ascending=False)
    
    return results_df

def create_june_summary(results_df, df):
    """Create a comprehensive June summary."""
    total_employees = len(results_df)
    total_days = results_df['Total Days Tracked'].sum()
    total_issues = results_df['Total Problematic Days'].sum()
    avg_problematic = results_df['Problematic Percentage'].mean()
    
    # Get top 3 most problematic employees
    top_3 = results_df.head(3)['NAMES'].tolist()
    top_3_str = ", ".join(top_3)
    
    summary = {
        'Month': 'June 2025',
        'Total Employees': total_employees,
        'Total Days Tracked': total_days,
        'Total Issues': total_issues,
        'Average Problematic %': f"{avg_problematic:.2f}%",
        'Top 3 Most Problematic': top_3_str
    }
    
    return summary

def create_june_visualizations(results_df, df):
    """Create visualizations for June data."""
    
    # 1. Top problematic employees chart
    top_10 = results_df.head(10)
    fig1 = go.Figure(data=[
        go.Bar(
            x=top_10['NAMES'],
            y=top_10['Problematic Percentage'],
            text=[f"{val:.1f}%" for val in top_10['Problematic Percentage']],
            textposition='auto',
            marker_color='red'
        )
    ])
    fig1.update_layout(
        title='Top 10 Most Problematic Employees - June 2025',
        xaxis_title='Employees',
        yaxis_title='Problematic Percentage (%)',
        xaxis_tickangle=-45
    )
    fig1.write_html(os.path.join(output_dir, 'june_top_problematic_employees.html'))
    
    # 2. Issue breakdown chart
    issue_types = ['Late Arrivals/Missing Stand-up Count', 'Early Departure Count', 'Absent During Spot-Checks Count']
    issue_totals = [results_df[col].sum() for col in issue_types]
    
    fig2 = go.Figure(data=[
        go.Pie(
            labels=['Late Arrivals/Missing Stand-up', 'Early Departures', 'Absent During Spot-Checks'],
            values=issue_totals,
            hole=0.3
        )
    ])
    fig2.update_layout(title='June 2025 - Issue Type Breakdown')
    fig2.write_html(os.path.join(output_dir, 'june_issue_breakdown.html'))
    
    # 3. Employee distribution chart
    fig3 = go.Figure(data=[
        go.Histogram(
            x=results_df['Problematic Percentage'],
            nbinsx=20,
            marker_color='blue'
        )
    ])
    fig3.update_layout(
        title='Distribution of Problematic Percentages - June 2025',
        xaxis_title='Problematic Percentage (%)',
        yaxis_title='Number of Employees'
    )
    fig3.write_html(os.path.join(output_dir, 'june_employee_distribution.html'))
    
    print("June visualizations created successfully!")

def create_june_html_report(results_df, summary):
    """Create a comprehensive HTML report for June."""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>June 2025 Attendance Analysis Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
            .summary {{ background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            .table th {{ background-color: #f2f2f2; }}
            .high {{ background-color: #ffebee; }}
            .medium {{ background-color: #fff3e0; }}
            .low {{ background-color: #e8f5e8; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>June 2025 Attendance Analysis Report</h1>
            <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="summary">
            <h2>June 2025 Summary</h2>
            <ul>
                <li><strong>Total Employees:</strong> {summary['Total Employees']}</li>
                <li><strong>Total Days Tracked:</strong> {summary['Total Days Tracked']}</li>
                <li><strong>Total Issues:</strong> {summary['Total Issues']}</li>
                <li><strong>Average Problematic %:</strong> {summary['Average Problematic %']}</li>
                <li><strong>Top 3 Most Problematic:</strong> {summary['Top 3 Most Problematic']}</li>
            </ul>
        </div>
        
        <h2>Detailed Employee Analysis</h2>
        <table class="table">
            <tr>
                <th>Employee Name</th>
                <th>Total Days</th>
                <th>Late Arrivals</th>
                <th>Early Departures</th>
                <th>Spot-Check Absences</th>
                <th>Total Issues</th>
                <th>Problematic %</th>
            </tr>
    """
    
    for _, row in results_df.iterrows():
        # Determine row class based on problematic percentage
        if row['Problematic Percentage'] > 50:
            row_class = "high"
        elif row['Problematic Percentage'] > 20:
            row_class = "medium"
        else:
            row_class = "low"
        
        html_content += f"""
            <tr class="{row_class}">
                <td>{row['NAMES']}</td>
                <td>{row['Total Days Tracked']}</td>
                <td>{row['Late Arrivals/Missing Stand-up Count']}</td>
                <td>{row['Early Departure Count']}</td>
                <td>{row['Absent During Spot-Checks Count']}</td>
                <td>{row['Total Problematic Days']}</td>
                <td>{row['Problematic Percentage']:.2f}%</td>
            </tr>
        """
    
    html_content += """
        </table>
        
        <h2>Key Insights</h2>
        <ul>
            <li>This report shows attendance patterns for June 2025 only</li>
            <li>Employees are ranked by their problematic percentage</li>
            <li>High problematic percentages indicate multiple issues per day</li>
            <li>Green rows: Low problematic percentage (≤20%)</li>
            <li>Orange rows: Medium problematic percentage (21-50%)</li>
            <li>Red rows: High problematic percentage (>50%)</li>
        </ul>
        
        <h2>Interactive Charts</h2>
        <p>The following interactive charts are available:</p>
        <ul>
            <li><a href="june_top_problematic_employees.html">Top Problematic Employees Chart</a></li>
            <li><a href="june_issue_breakdown.html">Issue Type Breakdown</a></li>
            <li><a href="june_employee_distribution.html">Employee Distribution</a></li>
        </ul>
    </body>
    </html>
    """
    
    with open(os.path.join(output_dir, 'june_attendance_report.html'), 'w') as f:
        f.write(html_content)
    
    print("June HTML report created successfully!")

def main():
    print("="*70)
    print("JUNE 2025 ATTENDANCE ANALYSIS")
    print("="*70)
    
    # Load June data
    june_df = load_june_data()
    
    if june_df is None:
        print("Failed to load June data. Exiting.")
        return
    
    # Analyze June attendance
    results_df = analyze_june_attendance(june_df)
    
    if results_df is None:
        print("Failed to analyze June data. Exiting.")
        return
    
    # Save June results
    june_results_file = os.path.join(output_dir, 'june_attendance_analysis.csv')
    results_df.to_csv(june_results_file, index=False)
    print(f"June analysis results saved to {june_results_file}")
    
    # Create June summary
    summary = create_june_summary(results_df, june_df)
    
    # Save June summary
    june_summary_file = os.path.join(output_dir, 'june_summary.csv')
    summary_df = pd.DataFrame([summary])
    summary_df.to_csv(june_summary_file, index=False)
    print(f"June summary saved to {june_summary_file}")
    
    # Create visualizations
    create_june_visualizations(results_df, june_df)
    
    # Create HTML report
    create_june_html_report(results_df, summary)
    
    print("\n" + "="*70)
    print("JUNE 2025 ANALYSIS COMPLETED!")
    print("="*70)
    print(f"Summary: {summary['Total Employees']} employees, {summary['Total Days Tracked']} days tracked")
    print(f"Average problematic percentage: {summary['Average Problematic %']}")
    print(f"Top problematic employee: {summary['Top 3 Most Problematic'].split(',')[0]}")
    print("\nFiles created:")
    print(f"- {june_results_file}")
    print(f"- {june_summary_file}")
    print(f"- {os.path.join(output_dir, 'june_attendance_report.html')}")
    print(f"- Interactive charts in {output_dir}/")

if __name__ == "__main__":
    main() 