"""
Reporting and Analytics Service

Handles all reporting business logic including data aggregation,
analytics calculations, and report generation.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Count, Avg, Sum, Max, Min, QuerySet
from django.utils import timezone
from django.core.cache import cache

from ..models import (
    Employee, Event, AttendanceRecord, Department, Location,
    AnalyticsCache, ReportConfiguration, EmployeeAnalytics,
    DepartmentAnalytics, SystemPerformance
)
from .attendance_service import normalize_department_from_designation, list_available_departments

logger = logging.getLogger(__name__)


class ReportingService:
    """Service class for reporting and analytics operations."""

    @staticmethod
    def generate_attendance_summary(
        start_date: date,
        end_date: date,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive attendance summary for a date range."""
        
        # Get attendance records
        records = AttendanceRecord.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('employee', 'employee__card_number')
        
        # Filter by department if specified
        if department and department != 'all':
            employee_ids = []
            for record in records:
                if record.employee.card_number:
                    emp_dept = normalize_department_from_designation(
                        record.employee.card_number.designation
                    )
                    if emp_dept == department:
                        employee_ids.append(record.employee.id)
            records = records.filter(employee_id__in=employee_ids)
        
        total_records = records.count()
        if total_records == 0:
            return ReportingService._empty_summary(start_date, end_date, department)
        
        # Status breakdown
        status_counts = {
            'on_time': records.filter(status='On Time').count(),
            'early': records.filter(status='Early').count(),
            'late': records.filter(status='Late').count(),
            'absent': records.filter(status='Absent').count(),
        }
        
        # Calculate percentages
        percentages = {}
        for status, count in status_counts.items():
            percentages[status] = round((count / total_records) * 100, 2) if total_records > 0 else 0
        
        # Employee-level analysis
        employee_stats = {}
        for record in records:
            emp_id = record.employee.id
            if emp_id not in employee_stats:
                employee_stats[emp_id] = {
                    'employee': record.employee,
                    'total_days': 0,
                    'on_time': 0,
                    'early': 0,
                    'late': 0,
                    'absent': 0,
                    'total_completion': 0,
                    'problematic_days': 0,
                }
            
            stats = employee_stats[emp_id]
            stats['total_days'] += 1
            stats[record.status.lower().replace(' ', '_')] += 1
            stats['total_completion'] += record.completion_percentage
            
            if record.is_problematic_day:
                stats['problematic_days'] += 1
        
        # Calculate employee metrics
        employee_summaries = []
        for emp_id, stats in employee_stats.items():
            total_days = stats['total_days']
            attendance_rate = ((total_days - stats['absent']) / total_days) * 100 if total_days > 0 else 0
            punctuality_rate = ((stats['on_time'] + stats['early']) / total_days) * 100 if total_days > 0 else 0
            avg_completion = stats['total_completion'] / total_days if total_days > 0 else 0
            problematic_rate = (stats['problematic_days'] / total_days) * 100 if total_days > 0 else 0
            
            # Get department
            department_name = 'Unknown'
            if stats['employee'].card_number:
                department_name = normalize_department_from_designation(
                    stats['employee'].card_number.designation
                ) or 'Unknown'
            
            employee_summaries.append({
                'employee': stats['employee'],
                'department': department_name,
                'total_days': total_days,
                'attendance_rate': round(attendance_rate, 2),
                'punctuality_rate': round(punctuality_rate, 2),
                'average_completion': round(avg_completion, 2),
                'problematic_rate': round(problematic_rate, 2),
                'status_breakdown': {
                    'on_time': stats['on_time'],
                    'early': stats['early'],
                    'late': stats['late'],
                    'absent': stats['absent'],
                },
            })
        
        # Sort by attendance rate (descending)
        employee_summaries.sort(key=lambda x: x['attendance_rate'], reverse=True)
        
        # Daily trend analysis
        daily_stats = {}
        for record in records:
            date_str = record.date.strftime('%Y-%m-%d')
            if date_str not in daily_stats:
                daily_stats[date_str] = {
                    'date': record.date,
                    'total': 0,
                    'on_time': 0,
                    'early': 0,
                    'late': 0,
                    'absent': 0,
                }
            
            stats = daily_stats[date_str]
            stats['total'] += 1
            stats[record.status.lower().replace(' ', '_')] += 1
        
        # Department breakdown
        department_stats = {}
        for summary in employee_summaries:
            dept = summary['department']
            if dept not in department_stats:
                department_stats[dept] = {
                    'employee_count': 0,
                    'total_days': 0,
                    'average_attendance_rate': 0,
                    'average_punctuality_rate': 0,
                    'total_attendance_sum': 0,
                    'total_punctuality_sum': 0,
                }
            
            dept_stats = department_stats[dept]
            dept_stats['employee_count'] += 1
            dept_stats['total_days'] += summary['total_days']
            dept_stats['total_attendance_sum'] += summary['attendance_rate']
            dept_stats['total_punctuality_sum'] += summary['punctuality_rate']
        
        # Calculate department averages
        for dept, stats in department_stats.items():
            if stats['employee_count'] > 0:
                stats['average_attendance_rate'] = round(
                    stats['total_attendance_sum'] / stats['employee_count'], 2
                )
                stats['average_punctuality_rate'] = round(
                    stats['total_punctuality_sum'] / stats['employee_count'], 2
                )
        
        return {
            'summary': {
                'date_range': {'start': start_date, 'end': end_date},
                'department_filter': department,
                'total_records': total_records,
                'total_employees': len(employee_stats),
                'status_counts': status_counts,
                'status_percentages': percentages,
            },
            'employee_summaries': employee_summaries,
            'daily_trend': sorted(daily_stats.values(), key=lambda x: x['date']),
            'department_breakdown': department_stats,
            'generated_at': timezone.now(),
        }

    @staticmethod
    def _empty_summary(start_date: date, end_date: date, department: Optional[str]) -> Dict[str, Any]:
        """Return empty summary structure when no data is available."""
        return {
            'summary': {
                'date_range': {'start': start_date, 'end': end_date},
                'department_filter': department,
                'total_records': 0,
                'total_employees': 0,
                'status_counts': {'on_time': 0, 'early': 0, 'late': 0, 'absent': 0},
                'status_percentages': {'on_time': 0, 'early': 0, 'late': 0, 'absent': 0},
            },
            'employee_summaries': [],
            'daily_trend': [],
            'department_breakdown': {},
            'generated_at': timezone.now(),
        }

    @staticmethod
    def generate_employee_report(
        employee_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Generate detailed report for a specific employee."""
        try:
            employee = Employee.objects.get(id=employee_id, is_active=True)
        except Employee.DoesNotExist:
            return {'error': 'Employee not found or inactive'}
        
        # Get attendance records
        records = AttendanceRecord.objects.filter(
            employee=employee,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        # Get events
        events = Event.objects.filter(
            employee=employee,
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).select_related('event_type', 'location').order_by('timestamp')
        
        # Calculate metrics
        total_days = records.count()
        status_breakdown = {}
        completion_scores = []
        
        for record in records:
            status_breakdown[record.status] = status_breakdown.get(record.status, 0) + 1
            completion_scores.append(record.completion_percentage)
        
        # Calculate averages
        avg_completion = sum(completion_scores) / len(completion_scores) if completion_scores else 0
        
        # Attendance rate
        present_days = total_days - status_breakdown.get('Absent', 0)
        attendance_rate = (present_days / total_days) * 100 if total_days > 0 else 0
        
        # Punctuality rate
        punctual_days = status_breakdown.get('On Time', 0) + status_breakdown.get('Early', 0)
        punctuality_rate = (punctual_days / total_days) * 100 if total_days > 0 else 0
        
        # Department info
        department = 'Unknown'
        if employee.card_number:
            department = normalize_department_from_designation(
                employee.card_number.designation
            ) or 'Unknown'
        
        # Time analysis
        arrival_times = []
        departure_times = []
        
        for record in records:
            if record.arrival_time:
                arrival_times.append(record.arrival_time)
            if record.departure_time:
                departure_times.append(record.departure_time)
        
        # Calculate average times
        avg_arrival = None
        avg_departure = None
        
        if arrival_times:
            total_minutes = sum(
                t.hour * 60 + t.minute for t in arrival_times
            )
            avg_minutes = total_minutes // len(arrival_times)
            avg_arrival = f"{avg_minutes // 60:02d}:{avg_minutes % 60:02d}"
        
        if departure_times:
            total_minutes = sum(
                t.hour * 60 + t.minute for t in departure_times
            )
            avg_minutes = total_minutes // len(departure_times)
            avg_departure = f"{avg_minutes // 60:02d}:{avg_minutes % 60:02d}"
        
        return {
            'employee': employee,
            'department': department,
            'date_range': {'start': start_date, 'end': end_date},
            'summary_metrics': {
                'total_days': total_days,
                'attendance_rate': round(attendance_rate, 2),
                'punctuality_rate': round(punctuality_rate, 2),
                'average_completion': round(avg_completion, 2),
                'average_arrival_time': avg_arrival,
                'average_departure_time': avg_departure,
            },
            'status_breakdown': status_breakdown,
            'records': list(records),
            'events': list(events),
            'generated_at': timezone.now(),
        }

    @staticmethod
    def generate_department_analytics(department: str, days_back: int = 30) -> Dict[str, Any]:
        """Generate analytics for a specific department."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Get employees in department
        all_employees = Employee.objects.filter(is_active=True).select_related('card_number')
        department_employees = []
        
        for employee in all_employees:
            if employee.card_number:
                emp_dept = normalize_department_from_designation(employee.card_number.designation)
                if emp_dept == department:
                    department_employees.append(employee)
        
        if not department_employees:
            return {
                'department': department,
                'error': 'No employees found in this department'
            }
        
        employee_ids = [emp.id for emp in department_employees]
        
        # Get attendance records
        records = AttendanceRecord.objects.filter(
            employee_id__in=employee_ids,
            date__gte=start_date,
            date__lte=end_date
        ).select_related('employee')
        
        # Calculate department metrics
        total_records = records.count()
        if total_records == 0:
            return {
                'department': department,
                'message': 'No attendance data found for this period'
            }
        
        # Overall statistics
        status_counts = {
            'on_time': records.filter(status='On Time').count(),
            'early': records.filter(status='Early').count(),
            'late': records.filter(status='Late').count(),
            'absent': records.filter(status='Absent').count(),
        }
        
        # Calculate department-wide metrics
        total_completion = sum(record.completion_percentage for record in records)
        avg_completion = total_completion / total_records if total_records > 0 else 0
        
        attendance_rate = ((total_records - status_counts['absent']) / total_records) * 100
        punctuality_rate = ((status_counts['on_time'] + status_counts['early']) / total_records) * 100
        
        # Employee performance within department
        employee_performance = []
        for employee in department_employees:
            emp_records = records.filter(employee=employee)
            emp_total = emp_records.count()
            
            if emp_total > 0:
                emp_on_time = emp_records.filter(status__in=['On Time', 'Early']).count()
                emp_present = emp_records.exclude(status='Absent').count()
                
                employee_performance.append({
                    'employee': employee,
                    'total_days': emp_total,
                    'attendance_rate': round((emp_present / emp_total) * 100, 2),
                    'punctuality_rate': round((emp_on_time / emp_total) * 100, 2),
                    'avg_completion': round(
                        sum(r.completion_percentage for r in emp_records) / emp_total, 2
                    ),
                })
        
        # Sort by performance
        employee_performance.sort(key=lambda x: x['attendance_rate'], reverse=True)
        
        # Trend analysis (weekly comparison)
        current_week = records.filter(date__gte=end_date - timedelta(days=7))
        previous_week = records.filter(
            date__gte=end_date - timedelta(days=14),
            date__lt=end_date - timedelta(days=7)
        )
        
        trend_analysis = ReportingService._calculate_trend_analysis(current_week, previous_week)
        
        return {
            'department': department,
            'analysis_period': {'start': start_date, 'end': end_date, 'days': days_back},
            'summary': {
                'total_employees': len(department_employees),
                'total_records': total_records,
                'attendance_rate': round(attendance_rate, 2),
                'punctuality_rate': round(punctuality_rate, 2),
                'average_completion': round(avg_completion, 2),
            },
            'status_breakdown': status_counts,
            'employee_performance': employee_performance,
            'trends': trend_analysis,
            'generated_at': timezone.now(),
        }

    @staticmethod
    def _calculate_trend_analysis(current_period: QuerySet, previous_period: QuerySet) -> Dict[str, str]:
        """Calculate trend analysis between two periods."""
        if not current_period.exists() or not previous_period.exists():
            return {
                'attendance': 'insufficient_data',
                'punctuality': 'insufficient_data',
                'completion': 'insufficient_data'
            }
        
        # Current period metrics
        current_total = current_period.count()
        current_present = current_period.exclude(status='Absent').count()
        current_punctual = current_period.filter(status__in=['On Time', 'Early']).count()
        current_completion = sum(r.completion_percentage for r in current_period) / current_total
        
        # Previous period metrics
        previous_total = previous_period.count()
        previous_present = previous_period.exclude(status='Absent').count()
        previous_punctual = previous_period.filter(status__in=['On Time', 'Early']).count()
        previous_completion = sum(r.completion_percentage for r in previous_period) / previous_total
        
        # Calculate rates
        current_attendance_rate = (current_present / current_total) * 100
        previous_attendance_rate = (previous_present / previous_total) * 100
        
        current_punctuality_rate = (current_punctual / current_total) * 100
        previous_punctuality_rate = (previous_punctual / previous_total) * 100
        
        # Determine trends
        def get_trend(current, previous, threshold=5):
            diff = current - previous
            if diff > threshold:
                return 'improving'
            elif diff < -threshold:
                return 'declining'
            else:
                return 'stable'
        
        return {
            'attendance': get_trend(current_attendance_rate, previous_attendance_rate),
            'punctuality': get_trend(current_punctuality_rate, previous_punctuality_rate),
            'completion': get_trend(current_completion, previous_completion),
        }

    @staticmethod
    def get_system_performance_metrics() -> Dict[str, Any]:
        """Get system performance metrics for reporting."""
        # Get recent performance data
        recent_performance = SystemPerformance.objects.filter(
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-timestamp')[:100]
        
        if not recent_performance:
            return {'message': 'No performance data available'}
        
        # Calculate averages
        total_response_time = sum(
            p.response_time_ms for p in recent_performance if p.response_time_ms
        )
        avg_response_time = total_response_time / len(recent_performance) if recent_performance else 0
        
        # Database query stats
        total_queries = sum(p.db_queries for p in recent_performance if p.db_queries)
        avg_queries = total_queries / len(recent_performance) if recent_performance else 0
        
        # Memory usage
        memory_usage = [p.memory_usage_mb for p in recent_performance if p.memory_usage_mb]
        avg_memory = sum(memory_usage) / len(memory_usage) if memory_usage else 0
        max_memory = max(memory_usage) if memory_usage else 0
        
        return {
            'period': '24 hours',
            'sample_count': len(recent_performance),
            'response_time': {
                'average_ms': round(avg_response_time, 2),
                'max_ms': max(p.response_time_ms for p in recent_performance if p.response_time_ms) if recent_performance else 0,
            },
            'database': {
                'average_queries': round(avg_queries, 2),
                'max_queries': max(p.db_queries for p in recent_performance if p.db_queries) if recent_performance else 0,
            },
            'memory': {
                'average_mb': round(avg_memory, 2),
                'max_mb': round(max_memory, 2),
            },
            'last_updated': timezone.now(),
        }

    @staticmethod
    def cache_report_data(report_key: str, data: Dict[str, Any], timeout: int = 3600) -> bool:
        """Cache report data for performance optimization."""
        try:
            cache.set(f"report_{report_key}", data, timeout)
            
            # Also store in AnalyticsCache model for persistence
            AnalyticsCache.objects.update_or_create(
                cache_key=report_key,
                defaults={
                    'data': data,
                    'expires_at': timezone.now() + timedelta(seconds=timeout)
                }
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to cache report data for key {report_key}: {e}")
            return False

    @staticmethod
    def get_cached_report_data(report_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached report data."""
        # Try cache first
        cached_data = cache.get(f"report_{report_key}")
        if cached_data:
            return cached_data
        
        # Fallback to database
        try:
            cache_obj = AnalyticsCache.objects.get(
                cache_key=report_key,
                expires_at__gt=timezone.now()
            )
            return cache_obj.data
        except AnalyticsCache.DoesNotExist:
            return None

    @staticmethod
    def generate_executive_summary(days_back: int = 30) -> Dict[str, Any]:
        """Generate executive summary for management dashboard."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Overall statistics
        total_employees = Employee.objects.filter(is_active=True).count()
        total_records = AttendanceRecord.objects.filter(
            date__gte=start_date, date__lte=end_date
        ).count()
        
        # Key metrics
        records = AttendanceRecord.objects.filter(
            date__gte=start_date, date__lte=end_date
        )
        
        overall_attendance_rate = 0
        overall_punctuality_rate = 0
        overall_completion_rate = 0
        
        if records.exists():
            present_records = records.exclude(status='Absent').count()
            punctual_records = records.filter(status__in=['On Time', 'Early']).count()
            total_completion = sum(r.completion_percentage for r in records)
            
            overall_attendance_rate = (present_records / total_records) * 100
            overall_punctuality_rate = (punctual_records / total_records) * 100
            overall_completion_rate = total_completion / total_records
        
        # Department performance
        departments = list_available_departments()
        department_performance = []
        
        for dept in departments[:5]:  # Top 5 departments
            dept_summary = ReportingService.generate_department_analytics(dept, days_back)
            if 'summary' in dept_summary:
                department_performance.append({
                    'department': dept,
                    'attendance_rate': dept_summary['summary']['attendance_rate'],
                    'employee_count': dept_summary['summary']['total_employees'],
                })
        
        # Sort departments by performance
        department_performance.sort(key=lambda x: x['attendance_rate'], reverse=True)
        
        # Alerts and concerns
        alerts = []
        if overall_attendance_rate < 85:
            alerts.append("Overall attendance rate below 85%")
        if overall_punctuality_rate < 75:
            alerts.append("Overall punctuality rate below 75%")
        if overall_completion_rate < 80:
            alerts.append("Overall completion rate below 80%")
        
        return {
            'period': {'start': start_date, 'end': end_date, 'days': days_back},
            'key_metrics': {
                'total_employees': total_employees,
                'total_records': total_records,
                'attendance_rate': round(overall_attendance_rate, 2),
                'punctuality_rate': round(overall_punctuality_rate, 2),
                'completion_rate': round(overall_completion_rate, 2),
            },
            'department_performance': department_performance,
            'alerts': alerts,
            'generated_at': timezone.now(),
        }