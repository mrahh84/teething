#!/usr/bin/env python3
"""
Generate Location Analytics Script

This script generates comprehensive analytics from the imported location tracking data,
including utilization rates, movement patterns, and performance metrics.
"""

import os
import sys
import django
from django.utils import timezone
from datetime import date, timedelta
from django.db import models
from collections import defaultdict
import json

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
django.setup()

from common.models import (
    TaskAssignment, LocationMovement, Location, Employee,
    LocationAnalytics
)

def generate_location_analytics():
    """Generate comprehensive location analytics."""
    
    print("=== Generating Location Analytics ===")
    
    # Get date range from imported data
    start_date = date(2025, 6, 20)
    end_date = date(2025, 7, 30)
    
    # Get all locations with assignments
    locations = Location.objects.filter(
        task_assignments__assigned_date__range=[start_date, end_date]
    ).distinct()
    
    analytics_created = 0
    analytics_updated = 0
    
    for location in locations:
        print(f"\nProcessing analytics for: {location.name}")
        
        # Get all dates for this location
        dates = TaskAssignment.objects.filter(
            location=location,
            assigned_date__range=[start_date, end_date]
        ).values_list('assigned_date', flat=True).distinct()
        
        for current_date in dates:
            analytics, created = LocationAnalytics.objects.get_or_create(
                location=location,
                date=current_date,
                defaults={
                    'current_occupancy': 0,
                    'peak_occupancy': 0,
                    'average_occupancy': 0,
                    'utilization_rate': 0,
                    'total_movements': 0,
                    'arrivals': 0,
                    'departures': 0,
                    'active_tasks': 0,
                    'completed_tasks': 0,
                    'average_stay_duration': 0,
                    'peak_hours': {}
                }
            )
            
            # Calculate occupancy metrics
            assignments = TaskAssignment.objects.filter(
                location=location,
                assigned_date=current_date
            )
            
            current_occupancy = assignments.filter(is_completed=False).count()
            peak_occupancy = assignments.count()
            
            # Calculate movement metrics
            movements = LocationMovement.objects.filter(
                to_location=location,
                timestamp__date=current_date
            )
            
            arrivals = movements.count()
            departures = LocationMovement.objects.filter(
                from_location=location,
                timestamp__date=current_date
            ).count()
            
            total_movements = arrivals + departures
            
            # Calculate task metrics
            active_tasks = assignments.filter(is_completed=False).count()
            completed_tasks = assignments.filter(is_completed=True).count()
            
            # Calculate utilization rate
            utilization_rate = 0
            if location.capacity > 0:
                utilization_rate = (current_occupancy / location.capacity) * 100
            
            # Calculate average stay duration
            stay_durations = []
            for movement in movements:
                if movement.duration_minutes:
                    stay_durations.append(movement.duration_minutes)
            
            average_stay_duration = sum(stay_durations) / len(stay_durations) if stay_durations else 0
            
            # Calculate peak hours (simplified - using assignment counts by hour)
            peak_hours = {}
            for assignment in assignments:
                hour = assignment.created_at.hour if assignment.created_at else 9  # Default to 9 AM
                peak_hours[str(hour)] = peak_hours.get(str(hour), 0) + 1
            
            # Update analytics
            analytics.current_occupancy = current_occupancy
            analytics.peak_occupancy = peak_occupancy
            analytics.average_occupancy = (current_occupancy + peak_occupancy) / 2
            analytics.utilization_rate = utilization_rate
            analytics.total_movements = total_movements
            analytics.arrivals = arrivals
            analytics.departures = departures
            analytics.active_tasks = active_tasks
            analytics.completed_tasks = completed_tasks
            analytics.average_stay_duration = average_stay_duration
            analytics.peak_hours = peak_hours
            analytics.save()
            
            if created:
                analytics_created += 1
            else:
                analytics_updated += 1
            
            print(f"  {current_date}: {current_occupancy} current, {peak_occupancy} peak, {utilization_rate:.1f}% utilization")
    
    print(f"\n📊 Analytics Generation Complete:")
    print(f"  Created: {analytics_created} new analytics records")
    print(f"  Updated: {analytics_updated} existing analytics records")
    print(f"  Total locations processed: {locations.count()}")
    
    return analytics_created + analytics_updated

def generate_movement_patterns():
    """Generate movement pattern analysis."""
    
    print("\n=== Generating Movement Pattern Analysis ===")
    
    # Get all movements
    movements = LocationMovement.objects.filter(
        timestamp__date__range=[date(2025, 6, 20), date(2025, 7, 30)]
    ).select_related('employee', 'from_location', 'to_location')
    
    # Analyze movement patterns
    employee_patterns = defaultdict(lambda: {
        'total_movements': 0,
        'locations_visited': set(),
        'favorite_locations': defaultdict(int),
        'movement_types': defaultdict(int),
        'average_duration': 0
    })
    
    location_patterns = defaultdict(lambda: {
        'total_arrivals': 0,
        'total_departures': 0,
        'unique_employees': set(),
        'peak_hours': defaultdict(int)
    })
    
    for movement in movements:
        # Employee patterns
        emp_pattern = employee_patterns[movement.employee.id]
        emp_pattern['total_movements'] += 1
        emp_pattern['locations_visited'].add(movement.to_location.name)
        emp_pattern['favorite_locations'][movement.to_location.name] += 1
        emp_pattern['movement_types'][movement.movement_type] += 1
        
        # Location patterns
        loc_pattern = location_patterns[movement.to_location.id]
        loc_pattern['total_arrivals'] += 1
        loc_pattern['unique_employees'].add(movement.employee.id)
        loc_pattern['peak_hours'][movement.timestamp.hour] += 1
        
        if movement.from_location:
            location_patterns[movement.from_location.id]['total_departures'] += 1
    
    # Generate summary
    print(f"  Total movements analyzed: {movements.count()}")
    print(f"  Unique employees: {len(employee_patterns)}")
    print(f"  Unique locations: {len(location_patterns)}")
    
    # Top employees by movement
    top_employees = sorted(
        employee_patterns.items(),
        key=lambda x: x[1]['total_movements'],
        reverse=True
    )[:5]
    
    print("\n  Top 5 Most Active Employees:")
    for emp_id, pattern in top_employees:
        employee = Employee.objects.get(id=emp_id)
        print(f"    - {employee.given_name} {employee.surname}: {pattern['total_movements']} movements")
    
    # Top locations by activity
    top_locations = sorted(
        location_patterns.items(),
        key=lambda x: x[1]['total_arrivals'],
        reverse=True
    )[:5]
    
    print("\n  Top 5 Most Active Locations:")
    for loc_id, pattern in top_locations:
        location = Location.objects.get(id=loc_id)
        print(f"    - {location.name}: {pattern['total_arrivals']} arrivals, {pattern['total_departures']} departures")
    
    return employee_patterns, location_patterns

def generate_utilization_reports():
    """Generate location utilization reports."""
    
    print("\n=== Generating Location Utilization Reports ===")
    
    # Get analytics for the date range
    analytics = LocationAnalytics.objects.filter(
        date__range=[date(2025, 6, 20), date(2025, 7, 30)]
    ).select_related('location')
    
    # Calculate overall utilization
    total_utilization = 0
    location_utilization = defaultdict(list)
    
    for analytic in analytics:
        total_utilization += analytic.utilization_rate
        location_utilization[analytic.location.name].append(analytic.utilization_rate)
    
    avg_utilization = total_utilization / analytics.count() if analytics.count() > 0 else 0
    
    print(f"  Average utilization across all locations: {avg_utilization:.1f}%")
    
    # Location-specific utilization
    print("\n  Location Utilization Summary:")
    for location_name, rates in location_utilization.items():
        avg_rate = sum(rates) / len(rates)
        max_rate = max(rates)
        min_rate = min(rates)
        print(f"    - {location_name}: {avg_rate:.1f}% avg (min: {min_rate:.1f}%, max: {max_rate:.1f}%)")
    
    # Peak utilization days
    peak_days = analytics.order_by('-utilization_rate')[:5]
    print("\n  Peak Utilization Days:")
    for day in peak_days:
        print(f"    - {day.date}: {day.location.name} at {day.utilization_rate:.1f}%")
    
    return avg_utilization, location_utilization

def generate_performance_metrics():
    """Generate performance metrics and KPIs."""
    
    print("\n=== Generating Performance Metrics ===")
    
    # Get date range
    start_date = date(2025, 6, 20)
    end_date = date(2025, 7, 30)
    
    # Calculate metrics
    total_assignments = TaskAssignment.objects.filter(
        assigned_date__range=[start_date, end_date]
    ).count()
    
    completed_assignments = TaskAssignment.objects.filter(
        assigned_date__range=[start_date, end_date],
        is_completed=True
    ).count()
    
    total_movements = LocationMovement.objects.filter(
        timestamp__date__range=[start_date, end_date]
    ).count()
    
    unique_employees = TaskAssignment.objects.filter(
        assigned_date__range=[start_date, end_date]
    ).values('employee').distinct().count()
    
    unique_locations = TaskAssignment.objects.filter(
        assigned_date__range=[start_date, end_date]
    ).values('location').distinct().count()
    
    # Calculate KPIs
    completion_rate = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0
    avg_assignments_per_day = total_assignments / ((end_date - start_date).days + 1)
    avg_movements_per_day = total_movements / ((end_date - start_date).days + 1)
    
    print(f"  📊 Performance Metrics:")
    print(f"    - Total assignments: {total_assignments}")
    print(f"    - Completed assignments: {completed_assignments}")
    print(f"    - Completion rate: {completion_rate:.1f}%")
    print(f"    - Total movements: {total_movements}")
    print(f"    - Unique employees: {unique_employees}")
    print(f"    - Unique locations: {unique_locations}")
    print(f"    - Average assignments per day: {avg_assignments_per_day:.1f}")
    print(f"    - Average movements per day: {avg_movements_per_day:.1f}")
    
    # Save metrics to file
    metrics = {
        'total_assignments': total_assignments,
        'completed_assignments': completed_assignments,
        'completion_rate': completion_rate,
        'total_movements': total_movements,
        'unique_employees': unique_employees,
        'unique_locations': unique_locations,
        'avg_assignments_per_day': avg_assignments_per_day,
        'avg_movements_per_day': avg_movements_per_day,
        'date_range': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        }
    }
    
    with open('Implementation/performance_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2, default=str)
    
    print(f"  📄 Metrics saved to: Implementation/performance_metrics.json")
    
    return metrics

def main():
    """Main function to generate all analytics."""
    
    print("=== Location Analytics Generation ===")
    print("Generating comprehensive analytics from imported location data...")
    
    # Generate location analytics
    analytics_count = generate_location_analytics()
    
    # Generate movement patterns
    employee_patterns, location_patterns = generate_movement_patterns()
    
    # Generate utilization reports
    avg_utilization, location_utilization = generate_utilization_reports()
    
    # Generate performance metrics
    metrics = generate_performance_metrics()
    
    print(f"\n🎉 Analytics Generation Complete!")
    print(f"  Analytics records: {analytics_count}")
    print(f"  Employee patterns: {len(employee_patterns)}")
    print(f"  Location patterns: {len(location_patterns)}")
    print(f"  Average utilization: {avg_utilization:.1f}%")
    print(f"  Performance metrics: Generated and saved")
    
    print(f"\n✅ Phase 4: Analytics Enhancement Complete!")
    print("Ready for Phase 5: Frontend Integration")

if __name__ == "__main__":
    main() 