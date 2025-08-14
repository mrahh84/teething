"""
Async Report Generation Service for Phase 4 Performance Optimization

Implements asynchronous report generation, database connection pooling,
and advanced performance monitoring to improve system scalability.
"""

import logging
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import connection
from django.conf import settings
from django.contrib.auth.models import User

from ..models import (
    Employee, Event, AttendanceRecord, Department, 
    Location, AnalyticsCache, SystemPerformance
)

logger = logging.getLogger(__name__)


class AsyncReportService:
    """Service for asynchronous report generation."""
    
    def __init__(self):
        self.report_queue = []
        self.processing_reports = {}
    
    def queue_report_generation(self, user_id: int, report_type: str, 
                               report_params: Dict[str, Any]) -> str:
        """Queue a report for asynchronous generation."""
        
        # Generate unique report ID
        report_id = self._generate_report_id(user_id, report_type, report_params)
        
        # Check if report is already cached
        cached_report = cache.get(f"async_report:{report_id}")
        if cached_report:
            return report_id
        
        # Add to queue
        report_task = {
            'report_id': report_id,
            'user_id': user_id,
            'report_type': report_type,
            'report_params': report_params,
            'status': 'queued',
            'queued_at': timezone.now(),
            'priority': self._calculate_priority(report_type)
        }
        
        self.report_queue.append(report_task)
        self.report_queue.sort(key=lambda x: x['priority'])
        
        # Store in cache for tracking
        cache.set(f"report_queue:{report_id}", report_task, 3600)
        
        logger.info(f"Queued report {report_id} for user {user_id}")
        return report_id
    
    def get_report_status(self, report_id: str) -> Dict[str, Any]:
        """Get the status of a queued or processing report."""
        
        # Check if report is ready
        cached_report = cache.get(f"async_report:{report_id}")
        if cached_report:
            return {
                'status': 'ready',
                'report_id': report_id,
                'data': cached_report,
                'completed_at': cache.get(f"report_completed:{report_id}")
            }
        
        # Check if report is in queue
        queued_report = cache.get(f"report_queue:{report_id}")
        if queued_report:
            return {
                'status': 'queued',
                'report_id': report_id,
                'position': self._get_queue_position(report_id),
                'queued_at': queued_report['queued_at']
            }
        
        # Check if report is processing
        processing_report = cache.get(f"report_processing:{report_id}")
        if processing_report:
            return {
                'status': 'processing',
                'report_id': report_id,
                'started_at': processing_report['started_at'],
                'progress': processing_report.get('progress', 0)
            }
        
        return {'status': 'not_found', 'report_id': report_id}
    
    def process_report_queue(self):
        """Process the report queue (called by background worker)."""
        
        while self.report_queue:
            # Get next report from queue
            report_task = self.report_queue.pop(0)
            report_id = report_task['report_id']
            
            try:
                # Mark as processing
                processing_info = {
                    'started_at': timezone.now(),
                    'progress': 0
                }
                cache.set(f"report_processing:{report_id}", processing_info, 3600)
                
                # Remove from queue cache
                cache.delete(f"report_queue:{report_id}")
                
                # Generate report
                report_data = self._generate_report(
                    report_task['report_type'], 
                    report_task['report_params']
                )
                
                # Cache the result
                cache.set(f"async_report:{report_id}", report_data, 7200)  # 2 hours
                cache.set(f"report_completed:{report_id}", timezone.now(), 7200)
                
                # Remove from processing cache
                cache.delete(f"report_processing:{report_id}")
                
                # Notify user (optional)
                self._notify_user_completion(
                    report_task['user_id'], 
                    report_id, 
                    report_task['report_type']
                )
                
                logger.info(f"Completed report {report_id}")
                
            except Exception as e:
                logger.error(f"Failed to generate report {report_id}: {e}")
                
                # Mark as failed
                cache.set(f"report_failed:{report_id}", {
                    'error': str(e),
                    'failed_at': timezone.now()
                }, 3600)
                
                # Remove from processing cache
                cache.delete(f"report_processing:{report_id}")
    
    def _generate_report(self, report_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate the actual report based on type."""
        
        if report_type == 'attendance_summary':
            return self._generate_attendance_summary(params)
        elif report_type == 'department_performance':
            return self._generate_department_performance(params)
        elif report_type == 'employee_analytics':
            return self._generate_employee_analytics(params)
        elif report_type == 'comprehensive_report':
            return self._generate_comprehensive_report(params)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
    
    def _generate_attendance_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate attendance summary report."""
        
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        department = params.get('department')
        
        # Use optimized service for better performance
        from .optimized_reporting_service import OptimizedReportingService
        service = OptimizedReportingService()
        
        if department:
            dept_obj = Department.objects.filter(name=department).first()
            dept_id = dept_obj.id if dept_obj else None
        else:
            dept_id = None
        
        attendance_data = service.get_attendance_summary_sql(
            start_date, end_date, dept_id
        )
        
        return {
            'report_type': 'attendance_summary',
            'generated_at': timezone.now(),
            'parameters': params,
            'data': attendance_data,
            'summary': {
                'total_employees': len(attendance_data),
                'total_days': sum(d['total_days'] for d in attendance_data),
                'avg_attendance_rate': sum(d.get('on_time_days', 0) for d in attendance_data) / len(attendance_data) if attendance_data else 0
            }
        }
    
    def _generate_department_performance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate department performance report."""
        
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        from .optimized_reporting_service import OptimizedReportingService
        service = OptimizedReportingService()
        
        dept_data = service.get_department_performance_sql(start_date, end_date)
        
        return {
            'report_type': 'department_performance',
            'generated_at': timezone.now(),
            'parameters': params,
            'data': dept_data,
            'summary': {
                'total_departments': len(dept_data),
                'best_performing_dept': dept_data[0]['department_name'] if dept_data else None,
                'avg_attendance_rate': sum(d['attendance_rate'] for d in dept_data) / len(dept_data) if dept_data else 0
            }
        }
    
    def _generate_employee_analytics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate employee analytics report."""
        
        employee_id = params.get('employee_id')
        days = params.get('days', 30)
        
        from .optimized_reporting_service import OptimizedReportingService
        service = OptimizedReportingService()
        
        trends_data = service.get_employee_attendance_trends_sql(employee_id, days)
        
        return {
            'report_type': 'employee_analytics',
            'generated_at': timezone.now(),
            'parameters': params,
            'data': trends_data,
            'summary': {
                'total_days': len(trends_data),
                'late_days': sum(d['is_late'] for d in trends_data),
                'early_departure_days': sum(d['is_early_departure'] for d in trends_data)
            }
        }
    
    def _generate_comprehensive_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive report combining multiple data sources."""
        
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        department = params.get('department')
        
        # Get multiple data sources
        from .optimized_reporting_service import OptimizedReportingService
        service = OptimizedReportingService()
        
        # Attendance summary
        if department:
            dept_obj = Department.objects.filter(name=department).first()
            dept_id = dept_obj.id if dept_obj else None
        else:
            dept_id = None
        
        attendance_data = service.get_attendance_summary_sql(start_date, end_date, dept_id)
        dept_data = service.get_department_performance_sql(start_date, end_date)
        
        # Employee count
        employee_count = Employee.objects.filter(is_active=True).count()
        if department:
            employee_count = Employee.objects.filter(
                is_active=True, 
                department__name=department
            ).count()
        
        # Event count
        event_count = Event.objects.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).count()
        
        return {
            'report_type': 'comprehensive_report',
            'generated_at': timezone.now(),
            'parameters': params,
            'data': {
                'attendance_summary': attendance_data,
                'department_performance': dept_data,
                'employee_count': employee_count,
                'event_count': event_count
            },
            'summary': {
                'total_employees': employee_count,
                'total_events': event_count,
                'total_departments': len(dept_data),
                'report_period': f"{start_date} to {end_date}"
            }
        }
    
    def _generate_report_id(self, user_id: int, report_type: str, 
                           params: Dict[str, Any]) -> str:
        """Generate unique report ID."""
        
        param_string = json.dumps(params, sort_keys=True)
        hash_input = f"{user_id}:{report_type}:{param_string}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    def _calculate_priority(self, report_type: str) -> int:
        """Calculate report priority (lower = higher priority)."""
        
        priorities = {
            'attendance_summary': 1,
            'department_performance': 2,
            'employee_analytics': 3,
            'comprehensive_report': 4
        }
        
        return priorities.get(report_type, 5)
    
    def _get_queue_position(self, report_id: str) -> int:
        """Get position of report in queue."""
        
        for i, task in enumerate(self.report_queue):
            if task['report_id'] == report_id:
                return i + 1
        return -1
    
    def _notify_user_completion(self, user_id: int, report_id: str, report_type: str):
        """Notify user that report is ready (optional)."""
        
        try:
            user = User.objects.get(id=user_id)
            
            # Store notification in cache
            notification = {
                'type': 'report_ready',
                'report_id': report_id,
                'report_type': report_type,
                'message': f'Your {report_type.replace("_", " ").title()} report is ready.',
                'timestamp': timezone.now()
            }
            
            cache.set(f"user_notification:{user_id}:{report_id}", notification, 86400)
            
            # Could also send email here if configured
            # send_mail(
            #     'Report Ready',
            #     f'Your {report_type} report is ready. Report ID: {report_id}',
            #     'noreply@company.com',
            #     [user.email]
            # )
            
        except User.DoesNotExist:
            logger.warning(f"User {user_id} not found for notification")


class DatabaseConnectionPoolService:
    """Service for managing database connection pooling."""
    
    def __init__(self):
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'connection_errors': 0,
            'last_optimization': timezone.now()
        }
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get current database connection information."""
        
        try:
            with connection.cursor() as cursor:
                # Get connection info (PostgreSQL specific)
                cursor.execute("""
                    SELECT 
                        count(*) as total_connections,
                        count(*) FILTER (WHERE state = 'active') as active_connections
                    FROM pg_stat_activity 
                    WHERE datname = current_database()
                """)
                
                result = cursor.fetchone()
                if result:
                    self.connection_stats['total_connections'] = result[0]
                    self.connection_stats['active_connections'] = result[1]
                
                # Get connection pool settings
                cursor.execute("SHOW max_connections")
                max_connections = cursor.fetchone()[0]
                
                return {
                    'current_connections': self.connection_stats['total_connections'],
                    'active_connections': self.connection_stats['active_connections'],
                    'max_connections': max_connections,
                    'connection_utilization': (
                        self.connection_stats['total_connections'] / int(max_connections) * 100
                        if max_connections else 0
                    ),
                    'last_optimization': self.connection_stats['last_optimization']
                }
                
        except Exception as e:
            logger.error(f"Error getting connection info: {e}")
            self.connection_stats['connection_errors'] += 1
            return {
                'error': str(e),
                'connection_errors': self.connection_stats['connection_errors']
            }
    
    def optimize_connections(self):
        """Optimize database connections."""
        
        try:
            with connection.cursor() as cursor:
                # Close idle connections (PostgreSQL specific)
                cursor.execute("""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    AND pid <> pg_backend_pid()
                    AND state = 'idle'
                    AND state_change < current_timestamp - INTERVAL '10 minutes'
                """)
                
                terminated_count = cursor.rowcount
                
                # Update stats
                self.connection_stats['last_optimization'] = timezone.now()
                
                logger.info(f"Terminated {terminated_count} idle connections")
                
                return {
                    'terminated_connections': terminated_count,
                    'optimization_time': self.connection_stats['last_optimization']
                }
                
        except Exception as e:
            logger.error(f"Error optimizing connections: {e}")
            return {'error': str(e)}
    
    def get_connection_recommendations(self) -> List[str]:
        """Get recommendations for database connection optimization."""
        
        recommendations = []
        
        try:
            with connection.cursor() as cursor:
                # Check for long-running queries
                cursor.execute("""
                    SELECT 
                        pid, 
                        now() - pg_stat_activity.query_start AS duration,
                        query
                    FROM pg_stat_activity
                    WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
                    AND state = 'active'
                """)
                
                long_running = cursor.fetchall()
                if long_running:
                    recommendations.append(
                        f"Found {len(long_running)} long-running queries (>5 minutes)"
                    )
                
                # Check for connection utilization
                cursor.execute("SHOW max_connections")
                max_connections = int(cursor.fetchone()[0])
                
                if self.connection_stats['total_connections'] > max_connections * 0.8:
                    recommendations.append(
                        "High connection utilization - consider increasing max_connections"
                    )
                
                # Check for idle connections
                cursor.execute("""
                    SELECT count(*) 
                    FROM pg_stat_activity 
                    WHERE state = 'idle' 
                    AND state_change < current_timestamp - INTERVAL '5 minutes'
                """)
                
                idle_count = cursor.fetchone()[0]
                if idle_count > 10:
                    recommendations.append(
                        f"Many idle connections ({idle_count}) - consider connection pooling"
                    )
                
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            recommendations.append(f"Error analyzing connections: {e}")
        
        return recommendations


class AdvancedPerformanceMonitoringService:
    """Advanced performance monitoring service for Phase 4."""
    
    def __init__(self):
        self.metrics = {}
        self.alerts = []
        self.performance_thresholds = {
            'max_query_count': 10,
            'max_execution_time': 2.0,  # seconds
            'min_cache_hit_rate': 80,   # percentage
            'max_memory_usage': 80      # percentage
        }
    
    def track_view_performance(self, view_name: str, query_count: int, 
                              execution_time: float, memory_usage: float = None):
        """Track comprehensive performance metrics for a view."""
        
        if view_name not in self.metrics:
            self.metrics[view_name] = {
                'total_requests': 0,
                'total_queries': 0,
                'total_time': 0,
                'total_memory': 0,
                'avg_queries': 0,
                'avg_time': 0,
                'avg_memory': 0,
                'performance_score': 0,
                'last_updated': timezone.now(),
                'performance_history': []
            }
        
        metrics = self.metrics[view_name]
        metrics['total_requests'] += 1
        metrics['total_queries'] += query_count
        metrics['total_time'] += execution_time
        
        if memory_usage:
            metrics['total_memory'] += memory_usage
        
        # Calculate averages
        metrics['avg_queries'] = metrics['total_queries'] / metrics['total_requests']
        metrics['avg_time'] = metrics['total_time'] / metrics['total_requests']
        
        if memory_usage:
            metrics['avg_memory'] = metrics['total_memory'] / metrics['total_requests']
        
        # Calculate performance score (lower is better)
        metrics['performance_score'] = (
            metrics['avg_queries'] * 0.4 + 
            metrics['avg_time'] * 0.4 + 
            (metrics['avg_memory'] * 0.2 if memory_usage else 0)
        )
        
        # Store performance history
        history_entry = {
            'timestamp': timezone.now(),
            'query_count': query_count,
            'execution_time': execution_time,
            'memory_usage': memory_usage,
            'performance_score': metrics['performance_score']
        }
        
        metrics['performance_history'].append(history_entry)
        
        # Keep only last 100 entries
        if len(metrics['performance_history']) > 100:
            metrics['performance_history'] = metrics['performance_history'][-100:]
        
        # Check for performance alerts
        self._check_performance_alerts(view_name, metrics)
        
        # Cache the metrics
        cache.set(f"advanced_performance_metrics:{view_name}", metrics, 3600)
    
    def _check_performance_alerts(self, view_name: str, metrics: Dict[str, Any]):
        """Check if performance metrics exceed thresholds."""
        
        alerts = []
        
        if metrics['avg_queries'] > self.performance_thresholds['max_query_count']:
            alerts.append({
                'type': 'high_query_count',
                'view': view_name,
                'value': metrics['avg_queries'],
                'threshold': self.performance_thresholds['max_query_count'],
                'severity': 'warning'
            })
        
        if metrics['avg_time'] > self.performance_thresholds['max_execution_time']:
            alerts.append({
                'type': 'slow_execution',
                'view': view_name,
                'value': metrics['avg_time'],
                'threshold': self.performance_thresholds['max_execution_time'],
                'severity': 'critical'
            })
        
        if alerts:
            self.alerts.extend(alerts)
            
            # Store alerts in cache
            cache.set(f"performance_alerts:{view_name}", alerts, 7200)
            
            # Log critical alerts
            for alert in alerts:
                if alert['severity'] == 'critical':
                    logger.warning(
                        f"Performance alert: {alert['type']} for {view_name} - "
                        f"Value: {alert['value']}, Threshold: {alert['threshold']}"
                    )
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        
        return {
            'views': self.metrics,
            'alerts': self.alerts,
            'recommendations': self.generate_recommendations(),
            'summary': self.generate_summary(),
            'thresholds': self.performance_thresholds
        }
    
    def generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate performance improvement recommendations."""
        
        recommendations = []
        
        for view_name, metrics in self.metrics.items():
            if metrics['avg_queries'] > self.performance_thresholds['max_query_count']:
                recommendations.append({
                    'view': view_name,
                    'issue': 'High query count',
                    'suggestion': 'Implement select_related/prefetch_related',
                    'priority': 'high',
                    'impact': 'Query count: ' + str(round(metrics['avg_queries'], 1))
                })
            
            if metrics['avg_time'] > self.performance_thresholds['max_execution_time']:
                recommendations.append({
                    'view': view_name,
                    'issue': 'Slow execution',
                    'suggestion': 'Add database indexes or optimize queries',
                    'priority': 'critical',
                    'impact': 'Execution time: ' + str(round(metrics['avg_time'], 2)) + 's'
                })
            
            if metrics['avg_memory'] and metrics['avg_memory'] > 100:  # MB
                recommendations.append({
                    'view': view_name,
                    'issue': 'High memory usage',
                    'suggestion': 'Optimize data structures and implement pagination',
                    'priority': 'medium',
                    'impact': 'Memory usage: ' + str(round(metrics['avg_memory'], 1)) + 'MB'
                })
        
        # Sort by priority
        priority_order = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 5))
        
        return recommendations
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate performance summary."""
        
        if not self.metrics:
            return {}
        
        total_views = len(self.metrics)
        avg_performance_score = sum(m['performance_score'] for m in self.metrics.values()) / total_views
        
        # Count views by performance category
        excellent_views = sum(1 for m in self.metrics.values() if m['performance_score'] < 5)
        good_views = sum(1 for m in self.metrics.values() if 5 <= m['performance_score'] < 10)
        poor_views = sum(1 for m in self.metrics.values() if m['performance_score'] >= 10)
        
        return {
            'total_views': total_views,
            'avg_performance_score': round(avg_performance_score, 2),
            'excellent_views': excellent_views,
            'good_views': good_views,
            'poor_views': poor_views,
            'total_alerts': len(self.alerts),
            'critical_alerts': len([a for a in self.alerts if a['severity'] == 'critical']),
            'last_updated': timezone.now()
        }
    
    def clear_old_metrics(self, days: int = 30):
        """Clear metrics older than specified days."""
        
        cutoff_date = timezone.now() - timedelta(days=days)
        cleared_count = 0
        
        for view_name, metrics in self.metrics.items():
            # Clear old performance history
            original_count = len(metrics['performance_history'])
            metrics['performance_history'] = [
                entry for entry in metrics['performance_history']
                if entry['timestamp'] > cutoff_date
            ]
            cleared_count += original_count - len(metrics['performance_history'])
        
        logger.info(f"Cleared {cleared_count} old performance metrics")
        return cleared_count
