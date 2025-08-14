"""
Optimized Reporting Service for Phase 3 Performance Optimization

Implements raw SQL for complex aggregations, pagination for large reports,
and template rendering optimization to improve performance.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db import connection
from django.db.models import Count, Q, Avg, Prefetch
from django.core.paginator import Paginator
from django.core.cache import cache

from ..models import (
    Employee, Event, AttendanceRecord, Department, 
    Location, AnalyticsCache, SystemPerformance
)

logger = logging.getLogger(__name__)


class OptimizedReportingService:
    """Service for optimized reporting using raw SQL and advanced query patterns."""
    
    def __init__(self, page_size: int = 50):
        self.page_size = page_size
    
    def get_attendance_summary_sql(self, start_date: date, end_date: date, 
                                  department_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Use raw SQL for complex attendance aggregations."""
        
        base_query = """
        SELECT 
            e.id as employee_id,
            e.given_name,
            e.surname,
            d.name as department_name,
            COUNT(ar.id) as total_days,
            SUM(CASE WHEN ar.status = 'On Time' THEN 1 ELSE 0 END) as on_time_days,
            SUM(CASE WHEN ar.status = 'Late' THEN 1 ELSE 0 END) as late_days,
            SUM(CASE WHEN ar.status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
            AVG(CAST(ar.arrival_time AS FLOAT)) as avg_arrival_time
        FROM common_employee e
        LEFT JOIN common_department d ON e.department_id = d.id
        LEFT JOIN common_attendancerecord ar ON e.id = ar.employee_id 
            AND ar.date BETWEEN %s AND %s
        WHERE e.is_active = 1
        """
        
        params = [start_date, end_date]
        
        if department_id:
            base_query += " AND e.department_id = %s"
            params.append(department_id)
        
        base_query += " GROUP BY e.id, e.given_name, e.surname, d.name"
        base_query += " ORDER BY e.surname, e.given_name"
        
        with connection.cursor() as cursor:
            cursor.execute(base_query, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_department_performance_sql(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get department performance using raw SQL for better performance."""
        
        query = """
        SELECT 
            d.id as department_id,
            d.name as department_name,
            COUNT(DISTINCT e.id) as total_employees,
            COUNT(ar.id) as total_attendance_records,
            SUM(CASE WHEN ar.status = 'On Time' THEN 1 ELSE 0 END) as on_time_count,
            SUM(CASE WHEN ar.status = 'Late' THEN 1 ELSE 0 END) as late_count,
            SUM(CASE WHEN ar.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
            AVG(CASE WHEN ar.status = 'On Time' THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate
        FROM common_department d
        LEFT JOIN common_employee e ON d.id = e.department_id AND e.is_active = 1
        LEFT JOIN common_attendancerecord ar ON e.id = ar.employee_id 
            AND ar.date BETWEEN %s AND %s
        WHERE d.is_active = 1
        GROUP BY d.id, d.name
        ORDER BY attendance_rate DESC
        """
        
        with connection.cursor() as cursor:
            cursor.execute(query, [start_date, end_date])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_employee_attendance_trends_sql(self, employee_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get employee attendance trends using raw SQL."""
        
        query = """
        SELECT 
            DATE(ar.date) as attendance_date,
            ar.status,
            ar.arrival_time,
            ar.departure_time,
            CASE 
                WHEN ar.arrival_time > '09:00:00' THEN 1 
                ELSE 0 
            END as is_late,
            CASE 
                WHEN ar.departure_time < '17:00:00' THEN 1 
                ELSE 0 
            END as is_early_departure
        FROM common_attendancerecord ar
        WHERE ar.employee_id = %s 
            AND ar.date >= %s
        ORDER BY ar.date DESC
        """
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        with connection.cursor() as cursor:
            cursor.execute(query, [employee_id, start_date])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


class PaginatedReportService:
    """Service for paginated report generation."""
    
    def __init__(self, page_size: int = 50):
        self.page_size = page_size
    
    def get_paginated_attendance_data(self, date: date, department: Optional[str] = None, 
                                     page: int = 1) -> Dict[str, Any]:
        """Get paginated attendance data."""
        
        # Get total count first
        base_query = AttendanceRecord.objects.filter(date=date)
        if department:
            base_query = base_query.filter(employee__department__name=department)
        
        total_count = base_query.count()
        
        # Get paginated data
        start = (page - 1) * self.page_size
        end = start + self.page_size
        
        records = base_query.select_related(
            'employee', 'employee__department', 'employee__card_number'
        )[start:end]
        
        return {
            'records': records,
            'pagination': {
                'current_page': page,
                'total_pages': (total_count + self.page_size - 1) // self.page_size,
                'total_count': total_count,
                'has_next': end < total_count,
                'has_previous': page > 1
            }
        }
    
    def get_paginated_employee_list(self, department: Optional[str] = None, 
                                   page: int = 1) -> Dict[str, Any]:
        """Get paginated employee list."""
        
        base_query = Employee.objects.filter(is_active=True)
        if department:
            base_query = base_query.filter(department__name=department)
        
        total_count = base_query.count()
        
        # Get paginated data
        start = (page - 1) * self.page_size
        end = start + self.page_size
        
        employees = base_query.select_related(
            'department', 'card_number'
        ).prefetch_related(
            Prefetch(
                'employee_events',
                queryset=Event.objects.filter(
                    timestamp__gte=timezone.now() - timedelta(days=7)
                ).select_related('event_type').order_by('-timestamp'),
                to_attr='recent_events'
            )
        )[start:end]
        
        return {
            'employees': employees,
            'pagination': {
                'current_page': page,
                'total_pages': (total_count + self.page_size - 1) // self.page_size,
                'total_count': total_count,
                'has_next': end < total_count,
                'has_previous': page > 1
            }
        }
    
    def get_paginated_event_history(self, employee_id: Optional[int] = None, 
                                   location_id: Optional[int] = None, 
                                   page: int = 1) -> Dict[str, Any]:
        """Get paginated event history."""
        
        base_query = Event.objects.all()
        if employee_id:
            base_query = base_query.filter(employee_id=employee_id)
        if location_id:
            base_query = base_query.filter(location_id=location_id)
        
        total_count = base_query.count()
        
        # Get paginated data
        start = (page - 1) * self.page_size
        end = start + self.page_size
        
        events = base_query.select_related(
            'employee', 'employee__department', 'event_type', 'location'
        )[start:end]
        
        return {
            'events': events,
            'pagination': {
                'current_page': page,
                'total_pages': (total_count + self.page_size - 1) // self.page_size,
                'total_count': total_count,
                'has_next': end < total_count,
                'has_previous': page > 1
            }
        }


class TemplateOptimizationService:
    """Service for optimizing template rendering performance."""
    
    @staticmethod
    def optimize_queryset_for_template(queryset, template_fields: List[str]):
        """Optimize queryset based on template field usage."""
        
        select_related_fields = []
        prefetch_related_fields = []
        
        for field in template_fields:
            if '__' in field:
                # Many-to-many or reverse foreign key
                prefetch_related_fields.append(field)
            else:
                # Foreign key
                select_related_fields.append(field)
        
        if select_related_fields:
            queryset = queryset.select_related(*select_related_fields)
        
        if prefetch_related_fields:
            queryset = queryset.prefetch_related(*prefetch_related_fields)
        
        return queryset
    
    @staticmethod
    def get_optimized_employee_data(department: Optional[str] = None) -> List[Employee]:
        """Get optimized employee data for templates."""
        
        employees = Employee.objects.filter(is_active=True)
        
        if department:
            employees = employees.filter(department__name=department)
        
        return employees.select_related(
            'department', 'card_number'
        ).prefetch_related(
            Prefetch(
                'employee_events',
                queryset=Event.objects.filter(
                    timestamp__gte=timezone.now() - timedelta(days=30)
                ).select_related('event_type').order_by('-timestamp'),
                to_attr='recent_events'
            )
        ).order_by('surname', 'given_name')
    
    @staticmethod
    def get_optimized_attendance_data(date: date, department: Optional[str] = None) -> List[AttendanceRecord]:
        """Get optimized attendance data for templates."""
        
        records = AttendanceRecord.objects.filter(date=date)
        
        if department:
            records = records.filter(employee__department__name=department)
        
        return records.select_related(
            'employee', 'employee__department', 'employee__card_number'
        ).order_by('employee__surname', 'employee__given_name')
    
    @staticmethod
    def get_optimized_event_data(days: int = 7, event_type: Optional[str] = None) -> List[Event]:
        """Get optimized event data for templates."""
        
        events = Event.objects.filter(
            timestamp__gte=timezone.now() - timedelta(days=days)
        )
        
        if event_type:
            events = events.filter(event_type__name=event_type)
        
        return events.select_related(
            'employee', 'employee__department', 'event_type', 'location'
        ).order_by('-timestamp')


class BulkDataService:
    """Service for bulk data operations to reduce database queries."""
    
    @staticmethod
    def get_employee_status_bulk(employee_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Get status for multiple employees in bulk."""
        
        if not employee_ids:
            return {}
        
        # Get all events for these employees in a single query
        events = Event.objects.filter(
            employee_id__in=employee_ids,
            timestamp__gte=timezone.now() - timedelta(days=1)
        ).select_related('event_type').order_by('employee_id', '-timestamp')
        
        # Group events by employee
        employee_events = {}
        for event in events:
            if event.employee_id not in employee_events:
                employee_events[event.employee_id] = []
            employee_events[event.employee_id].append(event)
        
        # Build status dictionary
        status_dict = {}
        for emp_id in employee_ids:
            emp_events = employee_events.get(emp_id, [])
            
            if not emp_events:
                status_dict[emp_id] = {
                    'status': 'Unknown',
                    'last_event': None,
                    'last_event_type': None,
                    'last_event_time': None
                }
                continue
            
            latest_event = emp_events[0]
            status_dict[emp_id] = {
                'status': 'Clocked In' if latest_event.event_type.name == 'Clock In' else 'Clocked Out',
                'last_event': latest_event,
                'last_event_type': latest_event.event_type.name,
                'last_event_time': latest_event.timestamp
            }
        
        return status_dict
    
    @staticmethod
    def get_attendance_summary_bulk(dates: List[date], department: Optional[str] = None) -> Dict[date, Dict[str, Any]]:
        """Get attendance summary for multiple dates in bulk."""
        
        if not dates:
            return {}
        
        # Get all records for these dates in a single query
        records = AttendanceRecord.objects.filter(
            date__in=dates
        ).select_related('employee', 'employee__department')
        
        if department:
            records = records.filter(employee__department__name=department)
        
        # Group records by date
        date_records = {}
        for record in records:
            if record.date not in date_records:
                date_records[record.date] = []
            date_records[record.date].append(record)
        
        # Build summary dictionary
        summary_dict = {}
        for date_obj in dates:
            date_records_list = date_records.get(date_obj, [])
            
            if not date_records_list:
                summary_dict[date_obj] = {
                    'total_employees': 0,
                    'present_count': 0,
                    'absent_count': 0,
                    'late_count': 0,
                    'attendance_rate': 0.0
                }
                continue
            
            total_employees = len(date_records_list)
            present_count = sum(1 for r in date_records_list if r.status == 'On Time')
            absent_count = sum(1 for r in date_records_list if r.status == 'Absent')
            late_count = sum(1 for r in date_records_list if r.status == 'Late')
            
            attendance_rate = (present_count / total_employees * 100) if total_employees > 0 else 0
            
            summary_dict[date_obj] = {
                'total_employees': total_employees,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'attendance_rate': round(attendance_rate, 1)
            }
        
        return summary_dict
