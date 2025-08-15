"""
Dashboard Analytics Service

This service provides data aggregation and analytics for the performance dashboard,
including attendance trends, department performance, and employee analytics.
"""

from django.db.models import Q, Count, Avg, Min, Max, F
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Any, Optional
import json

from ..models import (
    Employee, Event, EventType, Location, AttendanceRecord, 
    Department, SystemPerformance
)


class DashboardAnalyticsService:
    """Service for dashboard analytics and data aggregation"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def get_attendance_trends_data(self, days: int = 90) -> Dict[str, Any]:
        """
        Get attendance trends data for the specified number of days.
        
        Args:
            days: Number of days to analyze (default: 90)
            
        Returns:
            Dictionary containing trend data for charts
        """
        cache_key = f"attendance_trends_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get daily attendance data
        daily_data = []
        current_date = start_date
        
        while current_date <= end_date:
            # Use opening hours service to check if it's a working day
            from .opening_hours_service import OpeningHoursService
            opening_hours_service = OpeningHoursService()
            is_working_day, reason = opening_hours_service.is_working_day(current_date)
            
            if is_working_day:
                # Count employees who clocked in on this date
                clock_in_count = Event.objects.filter(
                    event_type__name='Clock In',
                    timestamp__date=current_date
                ).values('employee').distinct().count()
                
                # Get total active employees for this date
                total_employees = Employee.objects.filter(is_active=True).count()
                
                # Calculate attendance rate
                attendance_rate = (clock_in_count / total_employees * 100) if total_employees > 0 else 0
                
                daily_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'attendance_count': clock_in_count,
                    'total_employees': total_employees,
                    'attendance_rate': round(attendance_rate, 1),
                    'is_working_day': True,
                    'working_day_reason': reason
                })
            
            current_date += timedelta(days=1)
        
        # Get weekly aggregated data
        weekly_data = self._aggregate_weekly_data(daily_data)
        
        # Get department comparison data
        department_data = self._get_department_attendance_comparison(start_date, end_date)
        
        result = {
            'daily_data': daily_data,
            'weekly_data': weekly_data,
            'department_comparison': department_data,
            'summary': {
                'total_days': len(daily_data),
                'avg_attendance_rate': round(sum(d['attendance_rate'] for d in daily_data) / len(daily_data), 1),
                'best_day': max(daily_data, key=lambda x: x['attendance_rate']),
                'worst_day': min(daily_data, key=lambda x: x['attendance_rate'])
            }
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def _aggregate_weekly_data(self, daily_data: List[Dict]) -> List[Dict]:
        """Aggregate daily data into weekly summaries"""
        weekly_data = []
        
        for i in range(0, len(daily_data), 7):
            week_data = daily_data[i:i+7]
            if week_data:
                week_start = week_data[0]['date']
                week_end = week_data[-1]['date']
                avg_rate = sum(d['attendance_rate'] for d in week_data) / len(week_data)
                
                weekly_data.append({
                    'week_start': week_start,
                    'week_end': week_end,
                    'avg_attendance_rate': round(avg_rate, 1),
                    'total_attendance': sum(d['attendance_count'] for d in week_data),
                    'days_counted': len(week_data)
                })
        
        return weekly_data
    
    def _get_department_attendance_comparison(self, start_date: date, end_date: date) -> List[Dict]:
        """Get attendance comparison data by department"""
        departments = Department.objects.filter(is_active=True)
        comparison_data = []
        
        for dept in departments:
            # Count employees in this department
            dept_employees = Employee.objects.filter(
                department=dept,
                is_active=True
            ).count()
            
            if dept_employees == 0:
                continue
            
            # Count clock-ins for this department in the date range
            clock_ins = Event.objects.filter(
                event_type__name='Clock In',
                employee__department=dept,
                timestamp__date__gte=start_date,
                timestamp__date__lte=end_date
            ).values('employee', 'timestamp__date').distinct().count()
            
            # Calculate average daily attendance rate
            days_in_range = (end_date - start_date).days + 1
            avg_daily_attendance = clock_ins / days_in_range if days_in_range > 0 else 0
            attendance_rate = (avg_daily_attendance / dept_employees * 100) if dept_employees > 0 else 0
            
            comparison_data.append({
                'department_name': dept.name,
                'department_code': dept.code,
                'employee_count': dept_employees,
                'avg_daily_attendance': round(avg_daily_attendance, 1),
                'attendance_rate': round(attendance_rate, 1),
                'total_clock_ins': clock_ins
            })
        
        # Sort by attendance rate descending
        comparison_data.sort(key=lambda x: x['attendance_rate'], reverse=True)
        return comparison_data
    
    def get_department_performance_heatmap_data(self, days: int = 30) -> Dict[str, Any]:
        """
        Get department performance heatmap data.
        
        Args:
            days: Number of days to analyze (default: 30)
            
        Returns:
            Dictionary containing heatmap data
        """
        cache_key = f"dept_heatmap_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        departments = Department.objects.filter(is_active=True)
        heatmap_data = []
        
        for dept in departments:
            dept_data = {
                'department': dept.name,
                'daily_performance': []
            }
            
            current_date = start_date
            total_performance = 0
            days_counted = 0
            
            while current_date <= end_date:
                # Count employees who clocked in on this date
                clock_in_count = Event.objects.filter(
                    event_type__name='Clock In',
                    employee__department=dept,
                    timestamp__date=current_date
                ).values('employee').distinct().count()
                
                # Get total employees in this department
                total_dept_employees = Employee.objects.filter(
                    department=dept,
                    is_active=True
                ).count()
                
                # Calculate performance score (0-100)
                if total_dept_employees > 0:
                    performance_score = (clock_in_count / total_dept_employees) * 100
                    total_performance += performance_score
                    days_counted += 1
                else:
                    performance_score = 0
                
                dept_data['daily_performance'].append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'performance_score': round(performance_score, 1),
                    'attendance_count': clock_in_count,
                    'total_employees': total_dept_employees
                })
                
                current_date += timedelta(days=1)
            
            # Calculate average performance for the department
            dept_data['average_performance'] = round(total_performance / days_counted, 1) if days_counted > 0 else 0
            
            heatmap_data.append(dept_data)
        
        result = {
            'departments': heatmap_data,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'days': days
            }
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def get_employee_performance_distribution(self, days: int = 30) -> Dict[str, Any]:
        """
        Get employee performance distribution data.
        
        Args:
            days: Number of days to analyze (default: 30)
            
        Returns:
            Dictionary containing distribution data
        """
        cache_key = f"employee_distribution_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get all active employees
        employees = Employee.objects.filter(is_active=True).select_related('department')
        employee_performance = []
        
        for employee in employees:
            # Count days employee clocked in during the period
            clock_in_days = Event.objects.filter(
                event_type__name='Clock In',
                employee=employee,
                timestamp__date__gte=start_date,
                timestamp__date__lte=end_date
            ).values('timestamp__date').distinct().count()
            
            # Calculate attendance rate for this period
            days_in_period = (end_date - start_date).days + 1
            attendance_rate = (clock_in_days / days_in_period * 100) if days_in_period > 0 else 0
            
            employee_performance.append({
                'employee_id': employee.id,
                'employee_name': f"{employee.given_name} {employee.surname}",
                'department': employee.department.name if employee.department else 'Unassigned',
                'attendance_rate': round(attendance_rate, 1),
                'days_clocked_in': clock_in_days,
                'total_days': days_in_period
            })
        
        # Sort by attendance rate
        employee_performance.sort(key=lambda x: x['attendance_rate'], reverse=True)
        
        # Calculate distribution statistics
        rates = [e['attendance_rate'] for e in employee_performance]
        if rates:
            avg_rate = sum(rates) / len(rates)
            min_rate = min(rates)
            max_rate = max(rates)
            
            # Categorize employees into performance tiers
            performance_tiers = {
                'excellent': len([r for r in rates if r >= 90]),
                'good': len([r for r in rates if 80 <= r < 90]),
                'average': len([r for r in rates if 70 <= r < 80]),
                'below_average': len([r for r in rates if 60 <= r < 70]),
                'poor': len([r for r in rates if r < 60])
            }
        else:
            avg_rate = min_rate = max_rate = 0
            performance_tiers = {'excellent': 0, 'good': 0, 'average': 0, 'below_average': 0, 'poor': 0}
        
        # Identify outliers (employees significantly above/below average)
        if rates:
            std_dev = (sum((r - avg_rate) ** 2 for r in rates) / len(rates)) ** 0.5
            outlier_threshold = 2 * std_dev
            
            outliers = [
                e for e in employee_performance 
                if abs(e['attendance_rate'] - avg_rate) > outlier_threshold
            ]
        else:
            outliers = []
        
        result = {
            'employee_performance': employee_performance,
            'statistics': {
                'total_employees': len(employee_performance),
                'average_rate': round(avg_rate, 1),
                'min_rate': round(min_rate, 1),
                'max_rate': round(max_rate, 1),
                'performance_tiers': performance_tiers
            },
            'outliers': outliers,
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'days': days
            }
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def get_real_time_attendance_status(self) -> Dict[str, Any]:
        """
        Get real-time attendance status with comprehensive working hours logic.
        Uses OpeningHoursService for bank holidays, department schedules, and special periods.
        
        Returns:
            Dictionary containing current attendance status
        """
        cache_key = "real_time_attendance"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Import and initialize opening hours service
        from .opening_hours_service import OpeningHoursService
        opening_hours_service = OpeningHoursService()
        
        now = timezone.now()
        today = now.date()
        
        # Get comprehensive working hours information
        working_hours_info = opening_hours_service.get_working_hours_info(now)
        
        # If it's not a working day or working hours, return appropriate status
        if not working_hours_info['is_working_day']:
            result = {
                'current_time': now.strftime('%H:%M:%S'),
                'current_date': today.strftime('%Y-%m-%d'),
                'current_clocked_in': 0,
                'total_employees': Employee.objects.filter(is_active=True).count(),
                'current_percentage': 0,
                'expected_percentage': 0,
                'expected_attendance': 0,
                'attendance_status': working_hours_info['status'],
                'working_status': working_hours_info['message'],
                'working_hours_info': working_hours_info,
                'department_breakdown': []
            }
            cache.set(cache_key, result, 300)  # Cache for 5 minutes on non-working days
            return result
        
        if not working_hours_info['is_working_hours']:
            result = {
                'current_time': now.strftime('%H:%M:%S'),
                'current_date': today.strftime('%Y-%m-%d'),
                'current_clocked_in': 0,
                'total_employees': Employee.objects.filter(is_active=True).count(),
                'current_percentage': 0,
                'expected_percentage': 0,
                'expected_attendance': 0,
                'attendance_status': working_hours_info['status'],
                'working_status': working_hours_info['message'],
                'working_hours_info': working_hours_info,
                'department_breakdown': []
            }
            cache.set(cache_key, result, 300)  # Cache for 5 minutes outside hours
            return result
        
        # Get current clocked-in employees (only count those who haven't clocked out)
        current_clocked_in = Event.objects.filter(
            event_type__name='Clock In',
            timestamp__date=today
        ).exclude(
            # Exclude if there's a clock out after this clock in
            id__in=Event.objects.filter(
                event_type__name='Clock Out',
                timestamp__date=today,
                timestamp__time__gt=F('timestamp__time')
            ).values('id')
        ).values('employee').distinct().count()
        
        # Get total active employees
        total_employees = Employee.objects.filter(is_active=True).count()
        
        # Get department breakdown
        dept_breakdown = []
        departments = Department.objects.filter(is_active=True)
        
        for dept in departments:
            dept_clocked_in = Event.objects.filter(
                event_type__name='Clock In',
                employee__department=dept,
                timestamp__date=today
            ).exclude(
                id__in=Event.objects.filter(
                    event_type__name='Clock Out',
                    timestamp__date=today,
                    timestamp__time__gt=F('timestamp__time')
                ).values('id')
            ).values('employee').distinct().count()
            
            dept_total = Employee.objects.filter(
                department=dept,
                is_active=True
            ).count()
            
            if dept_total > 0:
                dept_breakdown.append({
                    'department': dept.name,
                    'clocked_in': dept_clocked_in,
                    'total': dept_total,
                    'percentage': round((dept_clocked_in / dept_total) * 100, 1)
                })
        
        # Calculate expected attendance based on time of day
        if now.hour < 10:  # Before 10 AM - early arrival period
            expected_percentage = 70
        elif now.hour < 12:  # 10 AM - 12 PM - core working hours
            expected_percentage = 95
        elif now.hour < 14:  # 12 PM - 2 PM - lunch period
            expected_percentage = 85
        elif now.hour < 17:  # 2 PM - 5 PM - afternoon working hours
            expected_percentage = 95
        else:  # After 5 PM - end of day
            expected_percentage = 60
        
        expected_attendance = int((expected_percentage / 100) * total_employees)
        actual_percentage = (current_clocked_in / total_employees * 100) if total_employees > 0 else 0
        
        # Determine working status message
        if now.hour < 10:
            working_status = "Early arrival period (9 AM - 10 AM)"
        elif now.hour < 12:
            working_status = "Core working hours (10 AM - 12 PM)"
        elif now.hour < 14:
            working_status = "Lunch period (12 PM - 2 PM)"
        elif now.hour < 17:
            working_status = "Afternoon working hours (2 PM - 5 PM)"
        else:
            working_status = "End of day (after 5 PM)"
        
        result = {
            'current_time': now.strftime('%H:%M:%S'),
            'current_date': today.strftime('%Y-%m-%d'),
            'current_clocked_in': current_clocked_in,
            'total_employees': total_employees,
            'current_percentage': round(actual_percentage, 1),
            'expected_percentage': expected_percentage,
            'expected_attendance': expected_attendance,
            'attendance_status': 'above_expectation' if actual_percentage >= expected_percentage else 'below_expectation',
            'working_status': working_status,
            'is_working_day': is_working_day,
            'is_working_hours': is_working_hours,
            'department_breakdown': dept_breakdown
        }
        
        cache.set(cache_key, result, 60)  # Cache for 1 minute for real-time data
        return result
    
    def get_system_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get enhanced system performance metrics.
        
        Args:
            days: Number of days to analyze (default: 7)
            
        Returns:
            Dictionary containing system performance data
        """
        cache_key = f"system_performance_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get system performance records
        system_metrics = SystemPerformance.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        # Get event processing metrics
        event_metrics = []
        current_date = start_date
        
        while current_date <= end_date:
            daily_events = Event.objects.filter(timestamp__date=current_date)
            event_count = daily_events.count()
            
            # Get unique users who created events
            unique_users = daily_events.values('created_by').distinct().count()
            
            event_metrics.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'total_events': event_count,
                'unique_users': unique_users,
                'clock_in_events': daily_events.filter(event_type__name='Clock In').count(),
                'clock_out_events': daily_events.filter(event_type__name='Clock Out').count()
            })
            
            current_date += timedelta(days=1)
        
        result = {
            'system_metrics': list(system_metrics.values()),
            'event_metrics': event_metrics,
            'summary': {
                'total_days': len(event_metrics),
                'avg_daily_events': round(sum(m['total_events'] for m in event_metrics) / len(event_metrics), 1),
                'total_events_period': sum(m['total_events'] for m in event_metrics)
            }
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def get_opening_hours_info(self, department_name: str = None) -> Dict[str, Any]:
        """
        Get opening hours information including bank holidays and department schedules.
        
        Args:
            department_name: Name of the department to check
            
        Returns:
            Dictionary containing opening hours information
        """
        from .opening_hours_service import OpeningHoursService
        opening_hours_service = OpeningHoursService()
        
        now = timezone.now()
        
        # Get current working hours info
        current_info = opening_hours_service.get_working_hours_info(now, department_name)
        
        # Get upcoming holidays
        upcoming_holidays = opening_hours_service.get_upcoming_holidays(days_ahead=30)
        
        # Get working hours summary for the department
        working_hours_summary = opening_hours_service.get_working_hours_summary(department_name)
        
        return {
            'current_status': current_info,
            'upcoming_holidays': upcoming_holidays,
            'working_hours_summary': working_hours_summary,
            'next_working_day': current_info.get('next_working_day'),
            'next_working_hours': current_info.get('next_working_hours')
        }
    
    def get_department_working_hours(self, department_name: str) -> Dict[str, Any]:
        """
        Get working hours information for a specific department.
        
        Args:
            department_name: Name of the department
            
        Returns:
            Dictionary containing department working hours
        """
        from .opening_hours_service import OpeningHoursService
        opening_hours_service = OpeningHoursService()
        
        return opening_hours_service.get_working_hours_summary(department_name)
    
    def get_all_departments_working_hours(self) -> Dict[str, Any]:
        """
        Get working hours information for all departments.
        
        Returns:
            Dictionary containing working hours for all departments
        """
        from .opening_hours_service import OpeningHoursService
        opening_hours_service = OpeningHoursService()
        
        return opening_hours_service.get_all_departments_working_hours()
