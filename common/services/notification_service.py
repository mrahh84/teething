"""
Notification and Alert Service

Handles all notification and alert functionality for the attendance system.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from django.utils import timezone
from django.contrib.auth.models import User
from django.core.cache import cache

from ..models import Employee, AttendanceRecord, Event, TaskAssignment

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(Enum):
    ATTENDANCE_ALERT = "attendance_alert"
    ABSENCE_WARNING = "absence_warning"
    LATE_ARRIVAL = "late_arrival"
    TASK_OVERDUE = "task_overdue"
    SYSTEM_ALERT = "system_alert"
    EMPLOYEE_MILESTONE = "employee_milestone"
    PERFORMANCE_WARNING = "performance_warning"


class NotificationService:
    """Service class for notification and alert operations."""

    @staticmethod
    def create_notification(
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        employee_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new notification."""
        notification = {
            'id': NotificationService._generate_notification_id(),
            'type': notification_type.value,
            'title': title,
            'message': message,
            'priority': priority.value,
            'employee_id': employee_id,
            'metadata': metadata or {},
            'created_at': timezone.now(),
            'is_read': False,
            'is_dismissed': False,
        }
        
        # Store in cache for quick access
        cache_key = f"notification_{notification['id']}"
        cache.set(cache_key, notification, timeout=86400)  # 24 hours
        
        # Add to active notifications list
        active_notifications = cache.get('active_notifications', [])
        active_notifications.append(notification['id'])
        cache.set('active_notifications', active_notifications, timeout=86400)
        
        logger.info(f"Created notification: {notification_type.value} - {title}")
        return notification

    @staticmethod
    def _generate_notification_id() -> str:
        """Generate a unique notification ID."""
        import uuid
        return str(uuid.uuid4())

    @staticmethod
    def get_active_notifications(
        priority_filter: Optional[NotificationPriority] = None,
        type_filter: Optional[NotificationType] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get active notifications with optional filtering."""
        active_notification_ids = cache.get('active_notifications', [])
        notifications = []
        
        for notification_id in active_notification_ids[:limit]:
            cache_key = f"notification_{notification_id}"
            notification = cache.get(cache_key)
            
            if notification and not notification.get('is_dismissed'):
                # Apply filters
                if priority_filter and notification['priority'] != priority_filter.value:
                    continue
                
                if type_filter and notification['type'] != type_filter.value:
                    continue
                
                notifications.append(notification)
        
        # Sort by priority and creation time
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        notifications.sort(
            key=lambda x: (priority_order.get(x['priority'], 3), x['created_at']),
            reverse=True
        )
        
        return notifications

    @staticmethod
    def mark_notification_read(notification_id: str) -> bool:
        """Mark a notification as read."""
        cache_key = f"notification_{notification_id}"
        notification = cache.get(cache_key)
        
        if notification:
            notification['is_read'] = True
            cache.set(cache_key, notification, timeout=86400)
            return True
        
        return False

    @staticmethod
    def dismiss_notification(notification_id: str) -> bool:
        """Dismiss a notification."""
        cache_key = f"notification_{notification_id}"
        notification = cache.get(cache_key)
        
        if notification:
            notification['is_dismissed'] = True
            cache.set(cache_key, notification, timeout=86400)
            
            # Remove from active list
            active_notifications = cache.get('active_notifications', [])
            if notification_id in active_notifications:
                active_notifications.remove(notification_id)
                cache.set('active_notifications', active_notifications, timeout=86400)
            
            return True
        
        return False

    @staticmethod
    def check_attendance_alerts() -> List[Dict[str, Any]]:
        """Check for attendance-related alerts and create notifications."""
        alerts = []
        today = timezone.now().date()
        
        # Check for employees with high absence rates
        recent_date = today - timedelta(days=7)
        
        employees = Employee.objects.filter(is_active=True).select_related('card_number')
        
        for employee in employees:
            recent_records = AttendanceRecord.objects.filter(
                employee=employee,
                date__gte=recent_date,
                date__lte=today
            )
            
            if recent_records.count() >= 5:  # Need minimum data
                absent_count = recent_records.filter(status='Absent').count()
                absence_rate = (absent_count / recent_records.count()) * 100
                
                if absence_rate >= 40:  # 40% or higher absence rate
                    notification = NotificationService.create_notification(
                        NotificationType.ABSENCE_WARNING,
                        f"High Absence Rate Alert",
                        f"{employee.given_name} {employee.surname} has {absence_rate:.1f}% absence rate in the last 7 days",
                        NotificationPriority.HIGH,
                        employee_id=employee.id,
                        metadata={
                            'absence_rate': absence_rate,
                            'absent_days': absent_count,
                            'total_days': recent_records.count()
                        }
                    )
                    alerts.append(notification)
        
        return alerts

    @staticmethod
    def check_late_arrival_patterns() -> List[Dict[str, Any]]:
        """Check for chronic late arrival patterns."""
        alerts = []
        today = timezone.now().date()
        recent_date = today - timedelta(days=14)  # Check last 2 weeks
        
        employees = Employee.objects.filter(is_active=True)
        
        for employee in employees:
            recent_records = AttendanceRecord.objects.filter(
                employee=employee,
                date__gte=recent_date,
                date__lte=today
            )
            
            if recent_records.count() >= 8:  # Need minimum data
                late_count = recent_records.filter(status='Late').count()
                late_rate = (late_count / recent_records.count()) * 100
                
                if late_rate >= 50:  # 50% or higher late rate
                    notification = NotificationService.create_notification(
                        NotificationType.LATE_ARRIVAL,
                        f"Chronic Late Arrival Pattern",
                        f"{employee.given_name} {employee.surname} has been late {late_rate:.1f}% of the time in the last 2 weeks",
                        NotificationPriority.MEDIUM,
                        employee_id=employee.id,
                        metadata={
                            'late_rate': late_rate,
                            'late_days': late_count,
                            'total_days': recent_records.count()
                        }
                    )
                    alerts.append(notification)
        
        return alerts

    @staticmethod
    def check_overdue_tasks() -> List[Dict[str, Any]]:
        """Check for overdue task assignments."""
        alerts = []
        today = timezone.now().date()
        
        try:
            overdue_tasks = TaskAssignment.objects.filter(
                due_date__lt=today,
                is_completed=False
            ).select_related('employee', 'location')
            
            # Group by employee
            employee_overdue = {}
            for task in overdue_tasks:
                emp_id = task.employee.id
                if emp_id not in employee_overdue:
                    employee_overdue[emp_id] = {
                        'employee': task.employee,
                        'tasks': []
                    }
                employee_overdue[emp_id]['tasks'].append(task)
            
            # Create notifications for employees with overdue tasks
            for emp_id, data in employee_overdue.items():
                employee = data['employee']
                task_count = len(data['tasks'])
                
                # Calculate how overdue the oldest task is
                oldest_task = min(data['tasks'], key=lambda t: t.due_date)
                days_overdue = (today - oldest_task.due_date).days
                
                priority = NotificationPriority.HIGH if days_overdue > 7 else NotificationPriority.MEDIUM
                
                notification = NotificationService.create_notification(
                    NotificationType.TASK_OVERDUE,
                    f"Overdue Tasks Alert",
                    f"{employee.given_name} {employee.surname} has {task_count} overdue task(s), oldest is {days_overdue} days overdue",
                    priority,
                    employee_id=employee.id,
                    metadata={
                        'overdue_task_count': task_count,
                        'days_overdue': days_overdue,
                        'oldest_task_id': oldest_task.id
                    }
                )
                alerts.append(notification)
                
        except Exception as e:
            logger.error(f"Error checking overdue tasks: {e}")
        
        return alerts

    @staticmethod
    def check_performance_warnings() -> List[Dict[str, Any]]:
        """Check for performance-related warnings."""
        alerts = []
        today = timezone.now().date()
        recent_date = today - timedelta(days=30)  # Check last month
        
        employees = Employee.objects.filter(is_active=True)
        
        for employee in employees:
            records = AttendanceRecord.objects.filter(
                employee=employee,
                date__gte=recent_date,
                date__lte=today
            )
            
            if records.count() >= 15:  # Need reasonable sample size
                # Calculate overall performance metrics
                present_records = records.exclude(status='Absent')
                attendance_rate = (present_records.count() / records.count()) * 100
                
                punctual_records = records.filter(status__in=['On Time', 'Early'])
                punctuality_rate = (punctual_records.count() / records.count()) * 100
                
                avg_completion = sum(r.completion_percentage for r in records) / records.count()
                
                # Check for concerning patterns
                issues = []
                
                if attendance_rate < 80:
                    issues.append(f"Low attendance rate: {attendance_rate:.1f}%")
                
                if punctuality_rate < 70:
                    issues.append(f"Low punctuality rate: {punctuality_rate:.1f}%")
                
                if avg_completion < 75:
                    issues.append(f"Low completion rate: {avg_completion:.1f}%")
                
                if issues:
                    notification = NotificationService.create_notification(
                        NotificationType.PERFORMANCE_WARNING,
                        f"Performance Concerns",
                        f"{employee.given_name} {employee.surname}: {'; '.join(issues)}",
                        NotificationPriority.MEDIUM,
                        employee_id=employee.id,
                        metadata={
                            'attendance_rate': attendance_rate,
                            'punctuality_rate': punctuality_rate,
                            'completion_rate': avg_completion,
                            'period_days': records.count()
                        }
                    )
                    alerts.append(notification)
        
        return alerts

    @staticmethod
    def check_employee_milestones() -> List[Dict[str, Any]]:
        """Check for positive employee milestones to celebrate."""
        alerts = []
        today = timezone.now().date()
        
        # Check for perfect attendance streaks
        employees = Employee.objects.filter(is_active=True)
        
        for employee in employees:
            # Check for 30-day perfect attendance (no absences, mostly on time)
            recent_records = AttendanceRecord.objects.filter(
                employee=employee,
                date__gte=today - timedelta(days=30),
                date__lte=today
            ).order_by('-date')
            
            if recent_records.count() >= 20:  # At least 20 days of data
                absent_count = recent_records.filter(status='Absent').count()
                on_time_count = recent_records.filter(status__in=['On Time', 'Early']).count()
                
                attendance_rate = ((recent_records.count() - absent_count) / recent_records.count()) * 100
                punctuality_rate = (on_time_count / recent_records.count()) * 100
                
                if attendance_rate >= 95 and punctuality_rate >= 90:
                    notification = NotificationService.create_notification(
                        NotificationType.EMPLOYEE_MILESTONE,
                        f"Excellent Performance!",
                        f"{employee.given_name} {employee.surname} has maintained {attendance_rate:.1f}% attendance and {punctuality_rate:.1f}% punctuality over the last 30 days",
                        NotificationPriority.LOW,
                        employee_id=employee.id,
                        metadata={
                            'milestone_type': 'perfect_attendance_30_days',
                            'attendance_rate': attendance_rate,
                            'punctuality_rate': punctuality_rate
                        }
                    )
                    alerts.append(notification)
        
        return alerts

    @staticmethod
    def create_system_alert(title: str, message: str, priority: NotificationPriority = NotificationPriority.MEDIUM) -> Dict[str, Any]:
        """Create a system-wide alert."""
        return NotificationService.create_notification(
            NotificationType.SYSTEM_ALERT,
            title,
            message,
            priority,
            metadata={'system_wide': True}
        )

    @staticmethod
    def run_daily_checks() -> Dict[str, Any]:
        """Run all daily notification checks."""
        results = {
            'attendance_alerts': NotificationService.check_attendance_alerts(),
            'late_arrival_patterns': NotificationService.check_late_arrival_patterns(),
            'overdue_tasks': NotificationService.check_overdue_tasks(),
            'performance_warnings': NotificationService.check_performance_warnings(),
            'employee_milestones': NotificationService.check_employee_milestones(),
            'total_new_notifications': 0,
            'run_at': timezone.now()
        }
        
        # Calculate total new notifications
        for check_type, notifications in results.items():
            if isinstance(notifications, list):
                results['total_new_notifications'] += len(notifications)
        
        logger.info(f"Daily notification checks completed: {results['total_new_notifications']} new notifications")
        
        return results

    @staticmethod
    def get_notification_summary() -> Dict[str, Any]:
        """Get summary of current notifications."""
        active_notifications = NotificationService.get_active_notifications()
        
        summary = {
            'total_active': len(active_notifications),
            'unread_count': sum(1 for n in active_notifications if not n.get('is_read', False)),
            'by_priority': {
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0
            },
            'by_type': {},
            'latest_notification': None
        }
        
        for notification in active_notifications:
            # Count by priority
            priority = notification.get('priority', 'medium')
            if priority in summary['by_priority']:
                summary['by_priority'][priority] += 1
            
            # Count by type
            notification_type = notification.get('type', 'unknown')
            summary['by_type'][notification_type] = summary['by_type'].get(notification_type, 0) + 1
            
            # Track latest
            if not summary['latest_notification'] or notification['created_at'] > summary['latest_notification']['created_at']:
                summary['latest_notification'] = notification
        
        return summary

    @staticmethod
    def cleanup_old_notifications(days_old: int = 7) -> int:
        """Clean up old notifications."""
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        active_notification_ids = cache.get('active_notifications', [])
        removed_count = 0
        
        for notification_id in active_notification_ids[:]:
            cache_key = f"notification_{notification_id}"
            notification = cache.get(cache_key)
            
            if notification and notification['created_at'] < cutoff_date:
                # Remove from cache
                cache.delete(cache_key)
                active_notification_ids.remove(notification_id)
                removed_count += 1
        
        # Update active notifications list
        cache.set('active_notifications', active_notification_ids, timeout=86400)
        
        logger.info(f"Cleaned up {removed_count} old notifications")
        return removed_count