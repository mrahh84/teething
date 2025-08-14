"""
Analytics and Pattern Recognition Service

Handles advanced analytics, pattern recognition, and predictive analytics
for the attendance system.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import statistics

from django.db.models import Q, Count, Avg, Sum, QuerySet
from django.utils import timezone

from ..models import Employee, Event, AttendanceRecord, Location
from .attendance_service import normalize_department_from_designation, filter_employees_by_department

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service class for advanced analytics and pattern recognition."""

    @staticmethod
    def detect_attendance_patterns(days_back: int = 60) -> Dict[str, Any]:
        """
        Detect patterns in attendance data using statistical analysis.
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        records = AttendanceRecord.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('employee', 'employee__card_number')
        
        if records.count() < 30:  # Need minimum data for pattern analysis
            return {
                'error': 'Insufficient data for pattern analysis',
                'minimum_required': 30,
                'available': records.count()
            }
        
        patterns = {
            'analysis_period': {'start': start_date, 'end': end_date, 'days': days_back},
            'employee_patterns': AnalyticsService._analyze_employee_patterns(records),
            'temporal_patterns': AnalyticsService._analyze_temporal_patterns(records),
            'department_patterns': AnalyticsService._analyze_department_patterns(records),
            'anomalies': AnalyticsService._detect_anomalies(records),
            'trends': AnalyticsService._analyze_trends(records),
            'generated_at': timezone.now(),
        }
        
        return patterns

    @staticmethod
    def _analyze_employee_patterns(records: QuerySet) -> Dict[str, Any]:
        """Analyze individual employee patterns."""
        employee_data = defaultdict(lambda: {
            'attendance_rates': [],
            'arrival_times': [],
            'statuses': [],
            'completion_scores': [],
            'problematic_days': 0,
            'total_days': 0
        })
        
        # Collect data by employee
        for record in records:
            emp_id = record.employee.id
            data = employee_data[emp_id]
            
            data['total_days'] += 1
            data['statuses'].append(record.status)
            data['completion_scores'].append(record.completion_percentage)
            
            if record.status != 'Absent':
                data['attendance_rates'].append(1)
            else:
                data['attendance_rates'].append(0)
            
            if record.arrival_time:
                # Convert time to minutes for analysis
                minutes = record.arrival_time.hour * 60 + record.arrival_time.minute
                data['arrival_times'].append(minutes)
            
            if record.is_problematic_day:
                data['problematic_days'] += 1
        
        patterns = {
            'consistent_performers': [],
            'at_risk_employees': [],
            'early_birds': [],
            'late_patterns': [],
            'irregular_schedules': []
        }
        
        for emp_id, data in employee_data.items():
            if data['total_days'] < 10:  # Skip employees with insufficient data
                continue
            
            try:
                employee = Employee.objects.get(id=emp_id)
                
                # Calculate metrics
                attendance_rate = (sum(data['attendance_rates']) / len(data['attendance_rates'])) * 100
                avg_completion = statistics.mean(data['completion_scores'])
                problematic_rate = (data['problematic_days'] / data['total_days']) * 100
                
                # Arrival time analysis
                avg_arrival = None
                arrival_consistency = None
                if data['arrival_times']:
                    avg_arrival = statistics.mean(data['arrival_times'])
                    arrival_consistency = statistics.stdev(data['arrival_times']) if len(data['arrival_times']) > 1 else 0
                
                employee_profile = {
                    'employee': employee,
                    'attendance_rate': round(attendance_rate, 2),
                    'avg_completion': round(avg_completion, 2),
                    'problematic_rate': round(problematic_rate, 2),
                    'avg_arrival_minutes': round(avg_arrival, 0) if avg_arrival else None,
                    'arrival_consistency': round(arrival_consistency, 2) if arrival_consistency else None,
                    'total_days': data['total_days']
                }
                
                # Classify patterns
                if attendance_rate >= 95 and avg_completion >= 85 and problematic_rate <= 5:
                    patterns['consistent_performers'].append(employee_profile)
                
                if attendance_rate <= 70 or problematic_rate >= 30:
                    patterns['at_risk_employees'].append(employee_profile)
                
                if avg_arrival and avg_arrival < 480:  # Before 8:00 AM
                    patterns['early_birds'].append(employee_profile)
                
                if avg_arrival and avg_arrival > 510:  # After 8:30 AM
                    patterns['late_patterns'].append(employee_profile)
                
                if arrival_consistency and arrival_consistency > 60:  # High variance in arrival
                    patterns['irregular_schedules'].append(employee_profile)
                    
            except Employee.DoesNotExist:
                continue
            except statistics.StatisticsError:
                continue  # Skip if insufficient data for statistics
        
        # Sort lists by severity/performance
        patterns['consistent_performers'].sort(key=lambda x: x['attendance_rate'], reverse=True)
        patterns['at_risk_employees'].sort(key=lambda x: x['attendance_rate'])
        patterns['early_birds'].sort(key=lambda x: x['avg_arrival_minutes'] or 999)
        patterns['late_patterns'].sort(key=lambda x: x['avg_arrival_minutes'] or 0, reverse=True)
        patterns['irregular_schedules'].sort(key=lambda x: x['arrival_consistency'] or 0, reverse=True)
        
        return patterns

    @staticmethod
    def _analyze_temporal_patterns(records: QuerySet) -> Dict[str, Any]:
        """Analyze temporal patterns in attendance."""
        weekday_stats = defaultdict(lambda: {'total': 0, 'on_time': 0, 'late': 0, 'absent': 0})
        monthly_trends = defaultdict(lambda: {'total': 0, 'on_time': 0, 'late': 0, 'absent': 0})
        
        for record in records:
            # Weekday analysis (0=Monday, 6=Sunday)
            weekday = record.date.weekday()
            weekday_stats[weekday]['total'] += 1
            
            if record.status == 'On Time' or record.status == 'Early':
                weekday_stats[weekday]['on_time'] += 1
            elif record.status == 'Late':
                weekday_stats[weekday]['late'] += 1
            elif record.status == 'Absent':
                weekday_stats[weekday]['absent'] += 1
            
            # Monthly trends
            month_key = record.date.strftime('%Y-%m')
            monthly_trends[month_key]['total'] += 1
            
            if record.status == 'On Time' or record.status == 'Early':
                monthly_trends[month_key]['on_time'] += 1
            elif record.status == 'Late':
                monthly_trends[month_key]['late'] += 1
            elif record.status == 'Absent':
                monthly_trends[month_key]['absent'] += 1
        
        # Calculate percentages for weekdays
        weekday_patterns = {}
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for day_num, stats in weekday_stats.items():
            if stats['total'] > 0:
                weekday_patterns[weekday_names[day_num]] = {
                    'total': stats['total'],
                    'on_time_rate': round((stats['on_time'] / stats['total']) * 100, 2),
                    'late_rate': round((stats['late'] / stats['total']) * 100, 2),
                    'absent_rate': round((stats['absent'] / stats['total']) * 100, 2),
                }
        
        # Calculate monthly trends
        monthly_analysis = {}
        for month, stats in monthly_trends.items():
            if stats['total'] > 0:
                monthly_analysis[month] = {
                    'total': stats['total'],
                    'on_time_rate': round((stats['on_time'] / stats['total']) * 100, 2),
                    'late_rate': round((stats['late'] / stats['total']) * 100, 2),
                    'absent_rate': round((stats['absent'] / stats['total']) * 100, 2),
                }
        
        # Identify patterns
        best_day = max(weekday_patterns.items(), key=lambda x: x[1]['on_time_rate'])[0] if weekday_patterns else None
        worst_day = min(weekday_patterns.items(), key=lambda x: x[1]['on_time_rate'])[0] if weekday_patterns else None
        
        return {
            'weekday_patterns': weekday_patterns,
            'monthly_trends': monthly_analysis,
            'insights': {
                'best_performance_day': best_day,
                'worst_performance_day': worst_day,
                'weekend_effect': AnalyticsService._analyze_weekend_effect(weekday_patterns),
            }
        }

    @staticmethod
    def _analyze_weekend_effect(weekday_patterns: Dict[str, Any]) -> str:
        """Analyze if there's a weekend effect on attendance."""
        if not weekday_patterns:
            return "Insufficient data"
        
        # Compare Friday vs Monday performance
        friday_rate = weekday_patterns.get('Friday', {}).get('on_time_rate', 0)
        monday_rate = weekday_patterns.get('Monday', {}).get('on_time_rate', 0)
        
        if friday_rate > monday_rate + 10:
            return "Strong Friday effect - better performance on Fridays"
        elif monday_rate > friday_rate + 10:
            return "Monday blues effect - worse performance on Fridays"
        else:
            return "No significant weekend effect detected"

    @staticmethod
    def _analyze_department_patterns(records: QuerySet) -> Dict[str, Any]:
        """Analyze patterns by department."""
        department_data = defaultdict(lambda: {
            'total_records': 0,
            'on_time': 0,
            'late': 0,
            'absent': 0,
            'completion_scores': [],
            'employees': set()
        })
        
        for record in records:
            if record.employee.card_number:
                dept = normalize_department_from_designation(
                    record.employee.card_number.designation
                ) or 'Unknown'
            else:
                dept = 'Unknown'
            
            data = department_data[dept]
            data['total_records'] += 1
            data['employees'].add(record.employee.id)
            data['completion_scores'].append(record.completion_percentage)
            
            if record.status in ['On Time', 'Early']:
                data['on_time'] += 1
            elif record.status == 'Late':
                data['late'] += 1
            elif record.status == 'Absent':
                data['absent'] += 1
        
        department_analysis = {}
        for dept, data in department_data.items():
            if data['total_records'] >= 10:  # Minimum threshold
                attendance_rate = ((data['total_records'] - data['absent']) / data['total_records']) * 100
                punctuality_rate = (data['on_time'] / data['total_records']) * 100
                avg_completion = statistics.mean(data['completion_scores']) if data['completion_scores'] else 0
                
                department_analysis[dept] = {
                    'employee_count': len(data['employees']),
                    'total_records': data['total_records'],
                    'attendance_rate': round(attendance_rate, 2),
                    'punctuality_rate': round(punctuality_rate, 2),
                    'avg_completion': round(avg_completion, 2),
                }
        
        # Rank departments
        if department_analysis:
            best_dept = max(department_analysis.items(), key=lambda x: x[1]['attendance_rate'])[0]
            worst_dept = min(department_analysis.items(), key=lambda x: x[1]['attendance_rate'])[0]
        else:
            best_dept = worst_dept = None
        
        return {
            'department_metrics': department_analysis,
            'rankings': {
                'best_performing': best_dept,
                'needs_attention': worst_dept,
            }
        }

    @staticmethod
    def _detect_anomalies(records: QuerySet) -> Dict[str, Any]:
        """Detect anomalies in attendance data."""
        anomalies = {
            'unusual_patterns': [],
            'data_quality_issues': [],
            'outliers': []
        }
        
        # Group by employee to detect individual anomalies
        employee_records = defaultdict(list)
        for record in records:
            employee_records[record.employee.id].append(record)
        
        for emp_id, emp_records in employee_records.items():
            if len(emp_records) < 10:  # Skip employees with insufficient data
                continue
            
            try:
                employee = Employee.objects.get(id=emp_id)
                
                # Analyze completion percentages for outliers
                completion_scores = [r.completion_percentage for r in emp_records]
                if len(completion_scores) > 5:
                    mean_completion = statistics.mean(completion_scores)
                    stdev_completion = statistics.stdev(completion_scores)
                    
                    # Find outliers (more than 2 standard deviations away)
                    for record in emp_records:
                        if abs(record.completion_percentage - mean_completion) > 2 * stdev_completion:
                            anomalies['outliers'].append({
                                'employee': employee,
                                'date': record.date,
                                'completion_percentage': record.completion_percentage,
                                'expected_range': f"{mean_completion - 2*stdev_completion:.1f} - {mean_completion + 2*stdev_completion:.1f}",
                                'type': 'completion_outlier'
                            })
                
                # Detect unusual patterns
                status_sequence = [r.status for r in sorted(emp_records, key=lambda x: x.date)]
                
                # Look for sudden changes in behavior
                recent_records = status_sequence[-10:]  # Last 10 records
                earlier_records = status_sequence[-20:-10] if len(status_sequence) >= 20 else []
                
                if recent_records and earlier_records:
                    recent_absent_rate = recent_records.count('Absent') / len(recent_records)
                    earlier_absent_rate = earlier_records.count('Absent') / len(earlier_records)
                    
                    if recent_absent_rate > earlier_absent_rate + 0.3:  # 30% increase in absence rate
                        anomalies['unusual_patterns'].append({
                            'employee': employee,
                            'pattern': 'sudden_increase_in_absences',
                            'recent_absent_rate': round(recent_absent_rate * 100, 1),
                            'previous_absent_rate': round(earlier_absent_rate * 100, 1),
                        })
                
            except (Employee.DoesNotExist, statistics.StatisticsError):
                continue
        
        # Data quality checks
        invalid_completions = records.filter(
            Q(completion_percentage__lt=0) | Q(completion_percentage__gt=100)
        )
        
        for record in invalid_completions:
            anomalies['data_quality_issues'].append({
                'employee': record.employee,
                'date': record.date,
                'issue': 'invalid_completion_percentage',
                'value': record.completion_percentage
            })
        
        return anomalies

    @staticmethod
    def _analyze_trends(records: QuerySet) -> Dict[str, Any]:
        """Analyze trends over time."""
        # Group records by week for trend analysis
        weekly_stats = defaultdict(lambda: {
            'total': 0, 'on_time': 0, 'late': 0, 'absent': 0, 
            'completion_sum': 0, 'problematic': 0
        })
        
        for record in records:
            # Get week start (Monday)
            week_start = record.date - timedelta(days=record.date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            
            stats = weekly_stats[week_key]
            stats['total'] += 1
            stats['completion_sum'] += record.completion_percentage
            
            if record.status in ['On Time', 'Early']:
                stats['on_time'] += 1
            elif record.status == 'Late':
                stats['late'] += 1
            elif record.status == 'Absent':
                stats['absent'] += 1
            
            if record.is_problematic_day:
                stats['problematic'] += 1
        
        # Calculate weekly rates
        weekly_trends = []
        for week, stats in sorted(weekly_stats.items()):
            if stats['total'] > 0:
                weekly_trends.append({
                    'week_start': week,
                    'attendance_rate': round(((stats['total'] - stats['absent']) / stats['total']) * 100, 2),
                    'punctuality_rate': round((stats['on_time'] / stats['total']) * 100, 2),
                    'avg_completion': round(stats['completion_sum'] / stats['total'], 2),
                    'problematic_rate': round((stats['problematic'] / stats['total']) * 100, 2),
                })
        
        # Analyze trends
        trends = {
            'weekly_data': weekly_trends,
            'overall_trend': 'stable',
            'attendance_trend': 'stable',
            'punctuality_trend': 'stable',
            'completion_trend': 'stable'
        }
        
        if len(weekly_trends) >= 4:  # Need at least 4 weeks for trend analysis
            # Compare first half vs second half
            mid_point = len(weekly_trends) // 2
            first_half = weekly_trends[:mid_point]
            second_half = weekly_trends[mid_point:]
            
            # Calculate averages
            first_attendance = statistics.mean([w['attendance_rate'] for w in first_half])
            second_attendance = statistics.mean([w['attendance_rate'] for w in second_half])
            
            first_punctuality = statistics.mean([w['punctuality_rate'] for w in first_half])
            second_punctuality = statistics.mean([w['punctuality_rate'] for w in second_half])
            
            first_completion = statistics.mean([w['avg_completion'] for w in first_half])
            second_completion = statistics.mean([w['avg_completion'] for w in second_half])
            
            # Determine trends
            threshold = 5  # 5% change threshold
            
            if second_attendance > first_attendance + threshold:
                trends['attendance_trend'] = 'improving'
                trends['overall_trend'] = 'improving'
            elif second_attendance < first_attendance - threshold:
                trends['attendance_trend'] = 'declining'
                trends['overall_trend'] = 'declining'
            
            if second_punctuality > first_punctuality + threshold:
                trends['punctuality_trend'] = 'improving'
            elif second_punctuality < first_punctuality - threshold:
                trends['punctuality_trend'] = 'declining'
            
            if second_completion > first_completion + threshold:
                trends['completion_trend'] = 'improving'
            elif second_completion < first_completion - threshold:
                trends['completion_trend'] = 'declining'
        
        return trends

    @staticmethod
    def generate_predictive_forecast(days_ahead: int = 7) -> Dict[str, Any]:
        """Generate predictive forecast based on historical patterns."""
        # Get historical data (last 60 days)
        historical_days = 60
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=historical_days)
        
        records = AttendanceRecord.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        )
        
        if records.count() < 30:
            return {
                'error': 'Insufficient historical data for forecasting',
                'required': 30,
                'available': records.count()
            }
        
        # Analyze historical patterns
        daily_stats = defaultdict(lambda: {'total': 0, 'present': 0, 'on_time': 0})
        
        for record in records:
            date_key = record.date.strftime('%Y-%m-%d')
            daily_stats[date_key]['total'] += 1
            
            if record.status != 'Absent':
                daily_stats[date_key]['present'] += 1
                
            if record.status in ['On Time', 'Early']:
                daily_stats[date_key]['on_time'] += 1
        
        # Calculate historical averages
        historical_data = []
        for date_str, stats in daily_stats.items():
            if stats['total'] > 0:
                historical_data.append({
                    'date': datetime.strptime(date_str, '%Y-%m-%d').date(),
                    'attendance_rate': (stats['present'] / stats['total']) * 100,
                    'punctuality_rate': (stats['on_time'] / stats['total']) * 100,
                })
        
        # Calculate moving averages
        if len(historical_data) < 7:
            return {'error': 'Insufficient data points for forecasting'}
        
        recent_data = historical_data[-14:]  # Last 2 weeks
        avg_attendance = statistics.mean([d['attendance_rate'] for d in recent_data])
        avg_punctuality = statistics.mean([d['punctuality_rate'] for d in recent_data])
        
        # Generate forecasts
        forecasts = []
        
        for i in range(1, days_ahead + 1):
            forecast_date = end_date + timedelta(days=i)
            
            # Apply weekday adjustments
            weekday = forecast_date.weekday()
            weekday_adjustment = AnalyticsService._get_weekday_adjustment(records, weekday)
            
            # Simple forecast with weekday adjustment
            forecast_attendance = min(100, max(0, avg_attendance + weekday_adjustment['attendance']))
            forecast_punctuality = min(100, max(0, avg_punctuality + weekday_adjustment['punctuality']))
            
            # Add some variation based on trends
            trend_adjustment = i * 0.1  # Small daily trend
            
            forecasts.append({
                'date': forecast_date,
                'predicted_attendance_rate': round(forecast_attendance + trend_adjustment, 2),
                'predicted_punctuality_rate': round(forecast_punctuality + trend_adjustment, 2),
                'confidence': 'medium',  # Simple confidence level
                'weekday': forecast_date.strftime('%A'),
            })
        
        return {
            'forecast_period': f"{days_ahead} days",
            'based_on_historical_days': historical_days,
            'forecasts': forecasts,
            'model_info': {
                'type': 'moving_average_with_weekday_adjustment',
                'confidence_level': 'medium',
                'last_updated': timezone.now(),
            }
        }

    @staticmethod
    def _get_weekday_adjustment(records: QuerySet, weekday: int) -> Dict[str, float]:
        """Get weekday-based adjustments for forecasting."""
        weekday_stats = defaultdict(lambda: {'total': 0, 'present': 0, 'on_time': 0})
        
        for record in records:
            day = record.date.weekday()
            weekday_stats[day]['total'] += 1
            
            if record.status != 'Absent':
                weekday_stats[day]['present'] += 1
                
            if record.status in ['On Time', 'Early']:
                weekday_stats[day]['on_time'] += 1
        
        # Calculate overall averages
        overall_attendance = 0
        overall_punctuality = 0
        total_days = len(weekday_stats)
        
        for day_stats in weekday_stats.values():
            if day_stats['total'] > 0:
                overall_attendance += (day_stats['present'] / day_stats['total']) * 100
                overall_punctuality += (day_stats['on_time'] / day_stats['total']) * 100
        
        overall_attendance /= total_days if total_days > 0 else 1
        overall_punctuality /= total_days if total_days > 0 else 1
        
        # Calculate adjustment for specific weekday
        day_stats = weekday_stats[weekday]
        if day_stats['total'] > 0:
            day_attendance = (day_stats['present'] / day_stats['total']) * 100
            day_punctuality = (day_stats['on_time'] / day_stats['total']) * 100
            
            return {
                'attendance': day_attendance - overall_attendance,
                'punctuality': day_punctuality - overall_punctuality,
            }
        
        return {'attendance': 0, 'punctuality': 0}  # No adjustment if no data