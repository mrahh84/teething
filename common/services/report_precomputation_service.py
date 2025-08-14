"""
Report Pre-computation Service for Phase 2 Performance Optimization

Implements background report generation and scheduled pre-computation
to improve report loading performance.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Q, Avg
from django.core.cache import cache

from ..models import (
    Employee, Event, AttendanceRecord, Department, 
    Location, AnalyticsCache, SystemPerformance
)
from django.contrib.auth.models import User
from .caching_service import enhanced_cache

logger = logging.getLogger(__name__)


class ReportPrecomputationService:
    """Service for pre-computing reports to improve performance."""
    
    def __init__(self):
        self.cache_timeouts = {
            'daily_summary': 86400,      # 24 hours
            'department_stats': 1800,     # 30 minutes
            'employee_status': 300,       # 5 minutes
            'attendance_heatmap': 1800,   # 30 minutes
            'system_performance': 300,    # 5 minutes
        }
    
    def precompute_daily_reports(self, target_date: date = None) -> Dict[str, int]:
        """
        Pre-compute daily reports for a specific date.
        
        Args:
            target_date: Date to pre-compute (defaults to today)
            
        Returns:
            Dictionary with counts of pre-computed reports
        """
        if target_date is None:
            target_date = timezone.now().date()
        
        results = {
            'department_summaries': 0,
            'employee_statuses': 0,
            'attendance_records': 0,
            'system_metrics': 0
        }
        
        try:
            # Pre-compute department summaries
            results['department_summaries'] = self._precompute_department_summaries(target_date)
            
            # Pre-compute employee statuses
            results['employee_statuses'] = self._precompute_employee_statuses(target_date)
            
            # Pre-compute attendance records
            results['attendance_records'] = self._precompute_attendance_records(target_date)
            
            # Pre-compute system performance metrics
            results['system_metrics'] = self._precompute_system_metrics(target_date)
            
            logger.info(f"Successfully pre-computed {sum(results.values())} daily reports for {target_date}")
            
        except Exception as e:
            logger.error(f"Failed to pre-compute daily reports for {target_date}: {e}")
        
        return results
    
    def _precompute_department_summaries(self, target_date: date) -> int:
        """Pre-compute department summary statistics."""
        try:
            # Get department statistics
            dept_stats = Employee.objects.filter(
                is_active=True
            ).values('department__name').annotate(
                employee_count=Count('id'),
                event_count=Count(
                    'employee_events',
                    filter=Q(employee_events__timestamp__date=target_date)
                ),
                clock_in_count=Count(
                    'employee_events',
                    filter=Q(
                        employee_events__event_type__name='Clock In',
                        employee_events__timestamp__date=target_date
                    )
                )
            ).filter(department__isnull=False)
            
            # Cache each department's summary
            cached_count = 0
            for stat in dept_stats:
                dept_name = stat['department__name']
                cache_key = f"dept_summary:{dept_name}:{target_date}"
                
                data = {
                    'department_name': dept_name,
                    'employee_count': stat['employee_count'],
                    'event_count': stat['event_count'],
                    'clock_in_count': stat['clock_in_count'],
                    'attendance_rate': round(
                        (stat['clock_in_count'] / stat['employee_count'] * 100) 
                        if stat['employee_count'] > 0 else 0, 1
                    ),
                    'date': target_date.isoformat(),
                    'precomputed_at': timezone.now().isoformat()
                }
                
                if enhanced_cache.cache_report(
                    cache_key, data, cache_type='department_stats'
                ):
                    cached_count += 1
            
            return cached_count
            
        except Exception as e:
            logger.error(f"Failed to pre-compute department summaries: {e}")
            return 0
    
    def _precompute_employee_statuses(self, target_date: date) -> int:
        """Pre-compute employee status information."""
        try:
            # Get employees with their current status
            employees = Employee.objects.filter(is_active=True).select_related('department')
            
            cached_count = 0
            for employee in employees:
                # Get employee's clock status for the target date
                clock_in_event = Event.objects.filter(
                    employee=employee,
                    event_type__name='Clock In',
                    timestamp__date=target_date
                ).first()
                
                clock_out_event = Event.objects.filter(
                    employee=employee,
                    event_type__name='Clock Out',
                    timestamp__date=target_date
                ).last()
                
                # Get attendance record if it exists
                attendance_record = AttendanceRecord.objects.filter(
                    employee=employee,
                    date=target_date
                ).first()
                
                data = {
                    'employee_id': employee.id,
                    'employee_name': f"{employee.given_name} {employee.surname}",
                    'department': employee.department.name if employee.department else 'Unknown',
                    'is_clocked_in': clock_in_event is not None and (
                        clock_out_event is None or clock_in_event.timestamp > clock_out_event.timestamp
                    ),
                    'clock_in_time': clock_in_event.timestamp.isoformat() if clock_in_event else None,
                    'clock_out_time': clock_out_event.timestamp.isoformat() if clock_out_event else None,
                    'attendance_status': attendance_record.status if attendance_record else 'DRAFT',
                    'date': target_date.isoformat(),
                    'precomputed_at': timezone.now().isoformat()
                }
                
                cache_key = f"employee_status:{employee.id}:{target_date}"
                if enhanced_cache.cache_report(
                    cache_key, data, cache_type='employee_status'
                ):
                    cached_count += 1
            
            return cached_count
            
        except Exception as e:
            logger.error(f"Failed to pre-compute employee statuses: {e}")
            return 0
    
    def _precompute_attendance_records(self, target_date: date) -> int:
        """Pre-compute attendance record summaries."""
        try:
            # Get attendance records for the date
            records = AttendanceRecord.objects.filter(
                date=target_date
            ).select_related('employee', 'employee__department')
            
            # Calculate summary statistics
            total_records = records.count()
            on_time_count = sum(1 for r in records if r.status == 'On Time')
            late_count = sum(1 for r in records if r.status == 'Late')
            absent_count = sum(1 for r in records if r.status == 'Absent')
            
            data = {
                'date': target_date.isoformat(),
                'total_records': total_records,
                'on_time_count': on_time_count,
                'late_count': late_count,
                'absent_count': absent_count,
                'on_time_percentage': round((on_time_count / total_records * 100) if total_records > 0 else 0, 1),
                'late_percentage': round((late_count / total_records * 100) if total_records > 0 else 0, 1),
                'absent_percentage': round((absent_count / total_records * 100) if total_records > 0 else 0, 1),
                'precomputed_at': timezone.now().isoformat()
            }
            
            cache_key = f"attendance_summary:{target_date}"
            if enhanced_cache.cache_report(
                cache_key, data, cache_type='daily_summary'
            ):
                return 1
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to pre-compute attendance records: {e}")
            return 0
    
    def _precompute_system_metrics(self, target_date: date) -> int:
        """Pre-compute system performance metrics."""
        try:
            # Calculate system metrics for the date
            total_events = Event.objects.filter(
                timestamp__date=target_date
            ).count()
            
            active_users = User.objects.filter(
                last_login__date=target_date
            ).count()
            
            # Get cache hit rate from cache service
            cache_stats = enhanced_cache.get_cache_stats()
            cache_hit_rate = cache_stats.get('cache_hit_rate', 0)
            
            data = {
                'date': target_date.isoformat(),
                'total_events_processed': total_events,
                'active_users': active_users,
                'cache_hit_rate': cache_hit_rate,
                'precomputed_at': timezone.now().isoformat()
            }
            
            cache_key = f"system_metrics:{target_date}"
            if enhanced_cache.cache_report(
                cache_key, data, cache_type='system_performance'
            ):
                return 1
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to pre-compute system metrics: {e}")
            return 0
    
    def precompute_weekly_reports(self, target_date: date = None) -> Dict[str, int]:
        """
        Pre-compute weekly reports for the week containing target_date.
        
        Args:
            target_date: Date within the target week (defaults to today)
            
        Returns:
            Dictionary with counts of pre-computed reports
        """
        if target_date is None:
            target_date = timezone.now().date()
        
        # Calculate week boundaries
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        results = {
            'weekly_summaries': 0,
            'trend_analysis': 0
        }
        
        try:
            # Pre-compute weekly summaries
            results['weekly_summaries'] = self._precompute_weekly_summaries(start_of_week, end_of_week)
            
            # Pre-compute trend analysis
            results['trend_analysis'] = self._precompute_trend_analysis(start_of_week, end_of_week)
            
            logger.info(f"Successfully pre-computed {sum(results.values())} weekly reports for week of {start_of_week}")
            
        except Exception as e:
            logger.error(f"Failed to pre-compute weekly reports for week of {start_of_week}: {e}")
        
        return results
    
    def _precompute_weekly_summaries(self, start_date: date, end_date: date) -> int:
        """Pre-compute weekly summary statistics."""
        try:
            # Get weekly statistics
            weekly_stats = AttendanceRecord.objects.filter(
                date__gte=start_date,
                date__lte=end_date
            ).values('employee__department__name').annotate(
                total_days=Count('date', distinct=True),
                on_time_days=Count('id', filter=Q(status='On Time')),
                late_days=Count('id', filter=Q(status='Late')),
                absent_days=Count('id', filter=Q(status='Absent'))
            ).filter(employee__department__isnull=False)
            
            # Cache weekly summary
            data = {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'department_stats': list(weekly_stats),
                'precomputed_at': timezone.now().isoformat()
            }
            
            cache_key = f"weekly_summary:{start_date}:{end_date}"
            if enhanced_cache.cache_report(
                cache_key, data, cache_type='comprehensive_report'
            ):
                return 1
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to pre-compute weekly summaries: {e}")
            return 0
    
    def _precompute_trend_analysis(self, start_date: date, end_date: date) -> int:
        """Pre-compute trend analysis for the week."""
        try:
            # Calculate attendance trends
            daily_attendance = []
            current_date = start_date
            
            while current_date <= end_date:
                day_records = AttendanceRecord.objects.filter(date=current_date)
                total = day_records.count()
                on_time = day_records.filter(status='On Time').count()
                
                daily_attendance.append({
                    'date': current_date.isoformat(),
                    'total': total,
                    'on_time': on_time,
                    'attendance_rate': round((on_time / total * 100) if total > 0 else 0, 1)
                })
                
                current_date += timedelta(days=1)
            
            data = {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'daily_attendance': daily_attendance,
                'avg_attendance_rate': round(
                    sum(day['attendance_rate'] for day in daily_attendance) / len(daily_attendance), 1
                ) if daily_attendance else 0,
                'precomputed_at': timezone.now().isoformat()
            }
            
            cache_key = f"trend_analysis:{start_date}:{end_date}"
            if enhanced_cache.cache_report(
                cache_key, data, cache_type='comprehensive_report'
            ):
                return 1
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to pre-compute trend analysis: {e}")
            return 0
    
    def get_precomputation_status(self) -> Dict[str, Any]:
        """Get status of pre-computed reports."""
        try:
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            
            # Check what's been pre-computed
            daily_reports = enhanced_cache.get_cached_report(f"attendance_summary:{today}")
            weekly_reports = enhanced_cache.get_cached_report(f"weekly_summary:{today - timedelta(days=today.weekday())}:{today + timedelta(days=6-today.weekday())}")
            
            return {
                'daily_reports': {
                    'today': daily_reports is not None,
                    'yesterday': enhanced_cache.get_cached_report(f"attendance_summary:{yesterday}") is not None
                },
                'weekly_reports': {
                    'current_week': weekly_reports is not None
                },
                'last_updated': timezone.now().isoformat(),
                'cache_health': enhanced_cache.get_cache_stats().get('cache_health', 'UNKNOWN')
            }
            
        except Exception as e:
            logger.error(f"Failed to get precomputation status: {e}")
            return {}


# Global instance
report_precomputer = ReportPrecomputationService()
