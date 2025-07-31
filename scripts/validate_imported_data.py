#!/usr/bin/env python3
"""
Validate Imported Location Data Script

This script validates the imported location tracking data to ensure
data integrity and completeness.
"""

import os
import sys
import django
from django.utils import timezone
from datetime import date, timedelta
from collections import defaultdict

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
django.setup()

from django.db import models
from common.models import (
    TaskAssignment, LocationMovement, Location, Employee,
    LocationAnalytics
)

def validate_imported_data():
    """Validate the imported location tracking data."""
    
    print("=== Validating Imported Location Data ===")
    
    # Get date range
    start_date = date(2025, 6, 20)
    end_date = date(2025, 7, 31)
    
    # 1. Task Assignment Validation
    print("\n1. Task Assignment Validation...")
    assignments = TaskAssignment.objects.filter(
        assigned_date__range=[start_date, end_date]
    )
    
    print(f"   Total assignments: {assignments.count()}")
    print(f"   Date range: {assignments.aggregate(min_date=models.Min('assigned_date'), max_date=models.Max('assigned_date'))}")
    
    # Check for duplicates
    duplicate_assignments = assignments.values('employee', 'location', 'assigned_date').annotate(
        count=models.Count('id')
    ).filter(count__gt=1)
    
    if duplicate_assignments.exists():
        print(f"   ⚠️  Found {duplicate_assignments.count()} duplicate assignments")
    else:
        print("   ✅ No duplicate assignments found")
    
    # 2. Location Movement Validation
    print("\n2. Location Movement Validation...")
    movements = LocationMovement.objects.filter(
        timestamp__date__range=[start_date, end_date]
    )
    
    print(f"   Total movements: {movements.count()}")
    print(f"   Movement types: {list(movements.values_list('movement_type', flat=True).distinct())}")
    
    # Check for duplicate movements
    duplicate_movements = movements.values('employee', 'to_location', 'movement_type', 'timestamp__date').annotate(
        count=models.Count('id')
    ).filter(count__gt=1)
    
    if duplicate_movements.exists():
        print(f"   ⚠️  Found {duplicate_movements.count()} duplicate movements")
    else:
        print("   ✅ No duplicate movements found")
    
    # 3. Employee Coverage
    print("\n3. Employee Coverage Analysis...")
    employees_with_assignments = assignments.values('employee').distinct()
    employees_with_movements = movements.values('employee').distinct()
    
    print(f"   Employees with assignments: {employees_with_assignments.count()}")
    print(f"   Employees with movements: {employees_with_movements.count()}")
    
    # Check employee matching
    total_employees = Employee.objects.filter(is_active=True).count()
    print(f"   Total active employees: {total_employees}")
    
    # 4. Location Coverage
    print("\n4. Location Coverage Analysis...")
    locations_with_assignments = assignments.values('location').distinct()
    locations_with_movements = movements.values('to_location').distinct()
    
    print(f"   Locations with assignments: {locations_with_assignments.count()}")
    print(f"   Locations with movements: {locations_with_movements.count()}")
    
    # Show location breakdown
    location_assignments = assignments.values('location__name').annotate(
        count=models.Count('id')
    ).order_by('-count')
    
    print("   Top locations by assignments:")
    for loc in location_assignments[:5]:
        print(f"     - {loc['location__name']}: {loc['count']} assignments")
    
    # 5. Daily Activity Analysis
    print("\n5. Daily Activity Analysis...")
    daily_assignments = assignments.values('assigned_date').annotate(
        count=models.Count('id')
    ).order_by('assigned_date')
    
    print(f"   Days with assignments: {daily_assignments.count()}")
    print(f"   Average assignments per day: {assignments.count() / daily_assignments.count():.1f}")
    
    # Show daily breakdown
    print("   Daily assignment counts:")
    for day in daily_assignments[:10]:  # Show first 10 days
        print(f"     - {day['assigned_date']}: {day['count']} assignments")
    
    # 6. Data Quality Checks
    print("\n6. Data Quality Checks...")
    
    # Check for missing data
    assignments_without_movements = assignments.exclude(
        employee__location_movements__to_location=models.F('location'),
        employee__location_movements__movement_type='TASK_ASSIGNMENT',
        employee__location_movements__timestamp__date=models.F('assigned_date')
    )
    
    if assignments_without_movements.exists():
        print(f"   ⚠️  Found {assignments_without_movements.count()} assignments without corresponding movements")
    else:
        print("   ✅ All assignments have corresponding movements")
    
    # Check for orphaned movements
    movements_without_assignments = movements.filter(
        movement_type='TASK_ASSIGNMENT'
    ).exclude(
        employee__task_assignments__location=models.F('to_location'),
        employee__task_assignments__assigned_date=models.F('timestamp__date')
    )
    
    if movements_without_assignments.exists():
        print(f"   ⚠️  Found {movements_without_assignments.count()} movements without corresponding assignments")
    else:
        print("   ✅ All movements have corresponding assignments")
    
    # 7. Summary Statistics
    print("\n7. Summary Statistics...")
    
    # Employee activity
    most_active_employees = assignments.values('employee__given_name', 'employee__surname').annotate(
        count=models.Count('id')
    ).order_by('-count')[:5]
    
    print("   Most active employees:")
    for emp in most_active_employees:
        print(f"     - {emp['employee__given_name']} {emp['employee__surname']}: {emp['count']} assignments")
    
    # Location utilization
    most_utilized_locations = assignments.values('location__name').annotate(
        count=models.Count('id')
    ).order_by('-count')[:5]
    
    print("   Most utilized locations:")
    for loc in most_utilized_locations:
        print(f"     - {loc['location__name']}: {loc['count']} assignments")
    
    # 8. Data Completeness
    print("\n8. Data Completeness...")
    
    # Calculate expected vs actual
    expected_days = (end_date - start_date).days + 1
    actual_days = daily_assignments.count()
    
    print(f"   Expected days: {expected_days}")
    print(f"   Actual days: {actual_days}")
    print(f"   Completeness: {(actual_days / expected_days) * 100:.1f}%")
    
    # Overall assessment
    print("\n=== Overall Assessment ===")
    
    issues_found = 0
    if duplicate_assignments.exists():
        issues_found += 1
    if duplicate_movements.exists():
        issues_found += 1
    if assignments_without_movements.exists():
        issues_found += 1
    if movements_without_assignments.exists():
        issues_found += 1
    
    if issues_found == 0:
        print("✅ Data validation passed - No issues found!")
    else:
        print(f"⚠️  Data validation completed with {issues_found} issues found")
    
    print(f"\n📊 Final Summary:")
    print(f"   Total assignments imported: {assignments.count()}")
    print(f"   Total movements imported: {movements.count()}")
    print(f"   Unique employees: {employees_with_assignments.count()}")
    print(f"   Unique locations: {locations_with_assignments.count()}")
    print(f"   Date range covered: {start_date} to {end_date}")

def main():
    """Main function to run the validation."""
    validate_imported_data()

if __name__ == "__main__":
    main() 