#!/usr/bin/env python3
"""
Excel Location Data Analysis Script

This script analyzes the "Task Splitting Sheet June 2025.xlsx" file to understand
its structure and extract location tracking data for integration with the Django
attendance system.
"""

import pandas as pd
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
import django
django.setup()

from common.models import Employee, Location

def analyze_excel_structure(file_path):
    """Analyze the structure of the Excel file."""
    print(f"Analyzing Excel file: {file_path}")
    
    try:
        # Read all sheets
        excel_file = pd.ExcelFile(file_path)
        print(f"Found {len(excel_file.sheet_names)} sheets: {excel_file.sheet_names}")
        
        analysis_results = {
            'file_path': file_path,
            'total_sheets': len(excel_file.sheet_names),
            'sheet_names': excel_file.sheet_names,
            'sheets_analysis': {}
        }
        
        for sheet_name in excel_file.sheet_names:
            print(f"\nAnalyzing sheet: {sheet_name}")
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            sheet_analysis = {
                'shape': df.shape,
                'columns': df.columns.tolist(),
                'data_types': df.dtypes.to_dict(),
                'null_counts': df.isnull().sum().to_dict(),
                'sample_data': df.head(3).to_dict('records'),
                'unique_values_per_column': {}
            }
            
            # Analyze unique values for key columns
            for col in df.columns:
                if df[col].dtype == 'object':  # String columns
                    unique_vals = df[col].dropna().unique()
                    sheet_analysis['unique_values_per_column'][col] = {
                        'count': len(unique_vals),
                        'sample_values': unique_vals[:10].tolist()
                    }
            
            analysis_results['sheets_analysis'][sheet_name] = sheet_analysis
            
            print(f"  Shape: {df.shape}")
            print(f"  Columns: {df.columns.tolist()}")
            print(f"  Null counts: {df.isnull().sum().sum()} total null values")
        
        return analysis_results
        
    except Exception as e:
        print(f"Error analyzing Excel file: {e}")
        return None

def identify_location_columns(analysis_results):
    """Identify columns that might contain location data."""
    location_keywords = [
        'location', 'area', 'zone', 'section', 'department', 'workstation',
        'station', 'post', 'checkpoint', 'room', 'floor', 'building',
        'task', 'assignment', 'work', 'duty', 'responsibility'
    ]
    
    location_columns = {}
    
    for sheet_name, sheet_data in analysis_results['sheets_analysis'].items():
        sheet_location_cols = []
        
        for col in sheet_data['columns']:
            col_lower = str(col).lower()
            
            # Check for location-related keywords
            for keyword in location_keywords:
                if keyword in col_lower:
                    sheet_location_cols.append({
                        'column': col,
                        'keyword_match': keyword,
                        'unique_values': sheet_data['unique_values_per_column'].get(col, {})
                    })
                    break
        
        if sheet_location_cols:
            location_columns[sheet_name] = sheet_location_cols
    
    return location_columns

def identify_employee_columns(analysis_results):
    """Identify columns that might contain employee data."""
    employee_keywords = [
        'name', 'employee', 'staff', 'person', 'worker', 'user',
        'first', 'last', 'given', 'surname', 'full'
    ]
    
    employee_columns = {}
    
    for sheet_name, sheet_data in analysis_results['sheets_analysis'].items():
        sheet_employee_cols = []
        
        for col in sheet_data['columns']:
            col_lower = str(col).lower()
            
            # Check for employee-related keywords
            for keyword in employee_keywords:
                if keyword in col_lower:
                    sheet_employee_cols.append({
                        'column': col,
                        'keyword_match': keyword,
                        'unique_values': sheet_data['unique_values_per_column'].get(col, {})
                    })
                    break
        
        if sheet_employee_cols:
            employee_columns[sheet_name] = sheet_employee_cols
    
    return employee_columns

def extract_sample_location_data(file_path, location_columns):
    """Extract sample location data from identified columns."""
    sample_data = {}
    
    for sheet_name, cols in location_columns.items():
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            sheet_data = []
            
            for col_info in cols:
                col_name = col_info['column']
                if col_name in df.columns:
                    # Get unique values and their counts
                    value_counts = df[col_name].value_counts().head(10)
                    sheet_data.append({
                        'column': col_name,
                        'keyword_match': col_info['keyword_match'],
                        'top_values': value_counts.to_dict(),
                        'total_unique': df[col_name].nunique()
                    })
            
            sample_data[sheet_name] = sheet_data
            
        except Exception as e:
            print(f"Error extracting data from sheet {sheet_name}: {e}")
    
    return sample_data

def map_to_existing_employees(employee_columns, analysis_results):
    """Map Excel employee names to existing database employees."""
    from common.models import Employee
    
    existing_employees = Employee.objects.all()
    existing_names = set()
    
    for emp in existing_employees:
        existing_names.add(f"{emp.given_name} {emp.surname}".lower())
        existing_names.add(f"{emp.surname} {emp.given_name}".lower())
    
    mapping_results = {}
    
    for sheet_name, cols in employee_columns.items():
        sheet_mapping = []
        
        for col_info in cols:
            col_name = col_info['column']
            unique_values = col_info['unique_values'].get('sample_values', [])
            
            matches = []
            potential_matches = []
            no_matches = []
            
            for name in unique_values:
                name_lower = str(name).lower()
                
                # Direct match
                if name_lower in existing_names:
                    matches.append(name)
                # Partial match
                elif any(existing_name in name_lower or name_lower in existing_name 
                        for existing_name in existing_names):
                    potential_matches.append(name)
                else:
                    no_matches.append(name)
            
            sheet_mapping.append({
                'column': col_name,
                'total_unique': col_info['unique_values'].get('count', 0),
                'direct_matches': len(matches),
                'potential_matches': len(potential_matches),
                'no_matches': len(no_matches),
                'match_rate': len(matches) / max(col_info['unique_values'].get('count', 1), 1) * 100,
                'sample_matches': matches[:5],
                'sample_potential': potential_matches[:5],
                'sample_no_matches': no_matches[:5]
            })
        
        mapping_results[sheet_name] = sheet_mapping
    
    return mapping_results

def generate_analysis_report(analysis_results, location_columns, employee_columns, 
                           sample_location_data, employee_mapping):
    """Generate a comprehensive analysis report."""
    
    report = {
        'analysis_timestamp': datetime.now().isoformat(),
        'file_info': {
            'path': analysis_results['file_path'],
            'total_sheets': analysis_results['total_sheets'],
            'sheet_names': analysis_results['sheet_names']
        },
        'location_analysis': {
            'identified_columns': location_columns,
            'sample_data': sample_location_data
        },
        'employee_analysis': {
            'identified_columns': employee_columns,
            'mapping_results': employee_mapping
        },
        'recommendations': []
    }
    
    # Generate recommendations
    total_employee_matches = 0
    total_employee_records = 0
    
    for sheet_name, mappings in employee_mapping.items():
        for mapping in mappings:
            total_employee_matches += mapping['direct_matches']
            total_employee_records += mapping['total_unique']
    
    if total_employee_records > 0:
        overall_match_rate = (total_employee_matches / total_employee_records) * 100
        report['recommendations'].append({
            'type': 'employee_mapping',
            'message': f"Overall employee match rate: {overall_match_rate:.1f}%",
            'priority': 'high' if overall_match_rate > 80 else 'medium'
        })
    
    # Location recommendations
    if location_columns:
        report['recommendations'].append({
            'type': 'location_data',
            'message': f"Found {len(location_columns)} sheets with potential location data",
            'priority': 'high'
        })
    
    return report

def main():
    """Main function to run the Excel analysis."""
    # Find the Excel file
    excel_file_path = "Garbage/Task Splitting Sheet June 2025.xlsx"
    
    if not os.path.exists(excel_file_path):
        print(f"Excel file not found: {excel_file_path}")
        return
    
    print("=== Excel Location Data Analysis ===")
    print(f"Analyzing file: {excel_file_path}")
    
    # Step 1: Analyze Excel structure
    analysis_results = analyze_excel_structure(excel_file_path)
    if not analysis_results:
        print("Failed to analyze Excel file")
        return
    
    # Step 2: Identify location columns
    location_columns = identify_location_columns(analysis_results)
    print(f"\nIdentified location columns in {len(location_columns)} sheets")
    
    # Step 3: Identify employee columns
    employee_columns = identify_employee_columns(analysis_results)
    print(f"Identified employee columns in {len(employee_columns)} sheets")
    
    # Step 4: Extract sample location data
    sample_location_data = extract_sample_location_data(excel_file_path, location_columns)
    
    # Step 5: Map to existing employees
    employee_mapping = map_to_existing_employees(employee_columns, analysis_results)
    
    # Step 6: Generate report
    report = generate_analysis_report(analysis_results, location_columns, employee_columns,
                                    sample_location_data, employee_mapping)
    
    # Save report
    report_file = "Implementation/excel_analysis_report.json"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\nAnalysis complete! Report saved to: {report_file}")
    
    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Total sheets analyzed: {analysis_results['total_sheets']}")
    print(f"Sheets with location data: {len(location_columns)}")
    print(f"Sheets with employee data: {len(employee_columns)}")
    
    if employee_mapping:
        total_matches = sum(
            sum(mapping['direct_matches'] for mapping in mappings)
            for mappings in employee_mapping.values()
        )
        total_records = sum(
            sum(mapping['total_unique'] for mapping in mappings)
            for mappings in employee_mapping.values()
        )
        if total_records > 0:
            match_rate = (total_matches / total_records) * 100
            print(f"Employee match rate: {match_rate:.1f}%")
    
    print("\nRecommendations:")
    for rec in report['recommendations']:
        print(f"  - {rec['message']} ({rec['priority']} priority)")

if __name__ == "__main__":
    main() 