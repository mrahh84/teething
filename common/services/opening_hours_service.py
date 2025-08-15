"""
Opening Hours Service

This service manages opening hours, bank holidays, and department-specific schedules.
Handles Barbados bank holidays and various department operating hours.
"""

from django.utils import timezone
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Any, Optional, Tuple
import json
import logging

logger = logging.getLogger(__name__)


class OpeningHoursService:
    """Service for managing opening hours and holiday schedules"""
    
    def __init__(self):
        # Barbados Bank Holidays 2025-2026
        self.barbados_holidays = {
            # 2025
            '2025-01-01': 'New Year\'s Day',
            '2025-01-21': 'Errol Barrow Day',
            '2025-04-18': 'Good Friday',
            '2025-04-21': 'Easter Monday',
            '2025-05-01': 'Labour Day',
            '2025-05-26': 'Whit Monday',
            '2025-08-04': 'Kadooment Day',
            '2025-11-30': 'Independence Day',
            '2025-12-25': 'Christmas Day',
            '2025-12-26': 'Boxing Day',
            
            # 2026
            '2026-01-01': 'New Year\'s Day',
            '2026-01-21': 'Errol Barrow Day',
            '2026-04-03': 'Good Friday',
            '2026-04-06': 'Easter Monday',
            '2026-05-01': 'Labour Day',
            '2026-05-18': 'Whit Monday',
            '2026-08-03': 'Kadooment Day',
            '2026-11-30': 'Independence Day',
            '2026-12-25': 'Christmas Day',
            '2026-12-26': 'Boxing Day',
        }
        
        # Department-specific schedules (can be customized per department)
        self.department_schedules = {
            'default': {
                'monday': {'start': time(9, 0), 'end': time(17, 0), 'open': True},
                'tuesday': {'start': time(9, 0), 'end': time(17, 0), 'open': True},
                'wednesday': {'start': time(9, 0), 'end': time(17, 0), 'open': True},
                'thursday': {'start': time(9, 0), 'end': time(17, 0), 'open': True},
                'friday': {'start': time(9, 0), 'end': time(17, 0), 'open': True},
                'saturday': {'start': time(9, 0), 'end': time(13, 0), 'open': False},  # Half day
                'sunday': {'start': time(9, 0), 'end': time(17, 0), 'open': False},
            },
            'security': {
                'monday': {'start': time(0, 0), 'end': time(23, 59), 'open': True},  # 24/7
                'tuesday': {'start': time(0, 0), 'end': time(23, 59), 'open': True},
                'wednesday': {'start': time(0, 0), 'end': time(23, 59), 'open': True},
                'thursday': {'start': time(0, 0), 'end': time(23, 59), 'open': True},
                'friday': {'start': time(0, 0), 'end': time(23, 59), 'open': True},
                'saturday': {'start': time(0, 0), 'end': time(23, 59), 'open': True},
                'sunday': {'start': time(0, 0), 'end': time(23, 59), 'open': True},
            },
            'maintenance': {
                'monday': {'start': time(7, 0), 'end': time(18, 0), 'open': True},  # Extended hours
                'tuesday': {'start': time(7, 0), 'end': time(18, 0), 'open': True},
                'wednesday': {'start': time(7, 0), 'end': time(18, 0), 'open': True},
                'thursday': {'start': time(7, 0), 'end': time(18, 0), 'open': True},
                'friday': {'start': time(7, 0), 'end': time(18, 0), 'open': True},
                'saturday': {'start': time(8, 0), 'end': time(16, 0), 'open': True},  # Weekend work
                'sunday': {'start': time(8, 0), 'end': time(16, 0), 'open': True},
            },
            'administration': {
                'monday': {'start': time(8, 30), 'end': time(17, 30), 'open': True},  # Standard office
                'tuesday': {'start': time(8, 30), 'end': time(17, 30), 'open': True},
                'wednesday': {'start': time(8, 30), 'end': time(17, 30), 'open': True},
                'thursday': {'start': time(8, 30), 'end': time(17, 30), 'open': True},
                'friday': {'start': time(8, 30), 'end': time(17, 30), 'open': True},
                'saturday': {'start': time(9, 0), 'end': time(17, 0), 'open': False},
                'sunday': {'start': time(9, 0), 'end': time(17, 0), 'open': False},
            }
        }
        
        # Special periods (can be extended for seasonal variations)
        self.special_periods = {
            'christmas_break': {
                'start': '2025-12-24',
                'end': '2025-12-26',
                'description': 'Christmas Break',
                'all_departments_closed': True
            },
            'new_year_break': {
                'start': '2025-12-31',
                'end': '2026-01-02',
                'description': 'New Year Break',
                'all_departments_closed': True
            },
            'summer_hours': {
                'start': '2025-07-01',
                'end': '2025-08-31',
                'description': 'Summer Hours (Early Close)',
                'early_close_hours': {'monday': time(16, 0), 'tuesday': time(16, 0), 'wednesday': time(16, 0), 'thursday': time(16, 0), 'friday': time(16, 0)}
            }
        }
    
    def is_bank_holiday(self, check_date: date) -> Tuple[bool, Optional[str]]:
        """
        Check if a date is a Barbados bank holiday.
        
        Args:
            check_date: Date to check
            
        Returns:
            Tuple of (is_holiday, holiday_name)
        """
        date_str = check_date.strftime('%Y-%m-%d')
        holiday_name = self.barbados_holidays.get(date_str)
        return bool(holiday_name), holiday_name
    
    def is_special_period(self, check_date: date) -> Tuple[bool, Optional[Dict]]:
        """
        Check if a date falls within a special period.
        
        Args:
            check_date: Date to check
            
        Returns:
            Tuple of (is_special, special_period_info)
        """
        for period_name, period_info in self.special_periods.items():
            start_date = datetime.strptime(period_info['start'], '%Y-%m-%d').date()
            end_date = datetime.strptime(period_info['end'], '%Y-%m-%d').date()
            
            if start_date <= check_date <= end_date:
                return True, period_info
        
        return False, None
    
    def get_department_schedule(self, department_name: str = None) -> Dict:
        """
        Get the schedule for a specific department.
        
        Args:
            department_name: Name of the department (defaults to 'default')
            
        Returns:
            Dictionary containing the department's schedule
        """
        if not department_name:
            department_name = 'default'
        
        # Normalize department name for matching
        department_key = department_name.lower().replace(' ', '_')
        
        # Try to find exact match first
        if department_key in self.department_schedules:
            return self.department_schedules[department_key]
        
        # Try partial matches
        for key, schedule in self.department_schedules.items():
            if key in department_key or department_key in key:
                return schedule
        
        # Fall back to default schedule
        return self.department_schedules['default']
    
    def is_working_day(self, check_date: date, department_name: str = None) -> Tuple[bool, str]:
        """
        Check if a date is a working day for a department.
        
        Args:
            check_date: Date to check
            department_name: Name of the department
            
        Returns:
            Tuple of (is_working_day, reason)
        """
        # Check if it's a bank holiday
        is_holiday, holiday_name = self.is_bank_holiday(check_date)
        if is_holiday:
            return False, f"Bank Holiday: {holiday_name}"
        
        # Check if it's a special period
        is_special, special_info = self.is_special_period(check_date)
        if is_special and special_info.get('all_departments_closed', False):
            return False, f"Special Period: {special_info['description']}"
        
        # Get department schedule
        schedule = self.get_department_schedule(department_name)
        
        # Check if the day of week is open for this department
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_name = day_names[check_date.weekday()]
        
        if day_name in schedule and schedule[day_name]['open']:
            return True, f"Regular working day ({day_name.title()})"
        else:
            return False, f"Department closed on {day_name.title()}"
    
    def is_working_hours(self, check_datetime: datetime, department_name: str = None) -> Tuple[bool, str]:
        """
        Check if a datetime is within working hours for a department.
        
        Args:
            check_datetime: Datetime to check
            department_name: Name of the department
            
        Returns:
            Tuple of (is_working_hours, reason)
        """
        check_date = check_datetime.date()
        check_time = check_datetime.time()
        
        # First check if it's a working day
        is_working_day, day_reason = self.is_working_day(check_date, department_name)
        if not is_working_day:
            return False, day_reason
        
        # Get department schedule
        schedule = self.get_department_schedule(department_name)
        
        # Check if current time is within working hours
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_name = day_names[check_date.weekday()]
        
        if day_name not in schedule:
            return False, f"No schedule defined for {day_name.title()}"
        
        day_schedule = schedule[day_name]
        
        # Check for special period early close
        is_special, special_info = self.is_special_period(check_date)
        if is_special and 'early_close_hours' in special_info:
            early_close_time = special_info['early_close_hours'].get(day_name)
            if early_close_time:
                if day_schedule['start'] <= check_time <= early_close_time:
                    return True, f"Special period hours ({day_schedule['start'].strftime('%H:%M')} - {early_close_time.strftime('%H:%M')})"
                else:
                    return False, f"Outside special period hours ({day_schedule['start'].strftime('%H:%M')} - {early_close_time.strftime('%H:%M')})"
        
        # Regular working hours check
        if day_schedule['start'] <= check_time <= day_schedule['end']:
            return True, f"Regular working hours ({day_schedule['start'].strftime('%H:%M')} - {day_schedule['end'].strftime('%H:%M')})"
        else:
            return False, f"Outside working hours ({day_schedule['start'].strftime('%H:%M')} - {day_schedule['end'].strftime('%H:%M')})"
    
    def get_working_hours_info(self, check_datetime: datetime, department_name: str = None) -> Dict[str, Any]:
        """
        Get comprehensive working hours information for a datetime and department.
        
        Args:
            check_datetime: Datetime to check
            department_name: Name of the department
            
        Returns:
            Dictionary containing working hours information
        """
        check_date = check_datetime.date()
        check_time = check_datetime.time()
        
        # Get all the status information
        is_working_day, day_reason = self.is_working_day(check_date, department_name)
        is_working_hours, hours_reason = self.is_working_hours(check_datetime, department_name)
        is_holiday, holiday_name = self.is_bank_holiday(check_date)
        is_special, special_info = self.is_special_period(check_date)
        
        # Get department schedule
        schedule = self.get_department_schedule(department_name)
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_name = day_names[check_date.weekday()]
        day_schedule = schedule.get(day_name, {})
        
        # Determine status and message
        if is_holiday:
            status = 'bank_holiday'
            message = f"Bank Holiday: {holiday_name}"
        elif is_special and special_info.get('all_departments_closed', False):
            status = 'special_period_closed'
            message = f"Special Period: {special_info['description']}"
        elif not is_working_day:
            status = 'closed'
            message = day_reason
        elif not is_working_hours:
            status = 'outside_hours'
            message = hours_reason
        else:
            status = 'open'
            message = hours_reason
        
        return {
            'datetime': check_datetime,
            'date': check_date.strftime('%Y-%m-%d'),
            'time': check_time.strftime('%H:%M:%S'),
            'day_of_week': day_name.title(),
            'department': department_name,
            'status': status,
            'message': message,
            'is_working_day': is_working_day,
            'is_working_hours': is_working_hours,
            'is_bank_holiday': is_holiday,
            'is_special_period': is_special,
            'holiday_name': holiday_name,
            'special_period_info': special_info,
            'day_schedule': day_schedule,
            'next_working_day': self._get_next_working_day(check_date, department_name),
            'next_working_hours': self._get_next_working_hours(check_datetime, department_name)
        }
    
    def _get_next_working_day(self, from_date: date, department_name: str = None) -> Optional[Dict]:
        """Get information about the next working day"""
        current_date = from_date + timedelta(days=1)
        
        # Look ahead up to 30 days
        for _ in range(30):
            is_working, reason = self.is_working_day(current_date, department_name)
            if is_working:
                schedule = self.get_department_schedule(department_name)
                day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                day_name = day_names[current_date.weekday()]
                day_schedule = schedule.get(day_name, {})
                
                return {
                    'date': current_date.strftime('%Y-%m-%d'),
                    'day': day_name.title(),
                    'start_time': day_schedule.get('start', time(9, 0)).strftime('%H:%M'),
                    'end_time': day_schedule.get('end', time(17, 0)).strftime('%H:%M'),
                    'days_until': (current_date - from_date).days
                }
            
            current_date += timedelta(days=1)
        
        return None
    
    def _get_next_working_hours(self, from_datetime: datetime, department_name: str = None) -> Optional[Dict]:
        """Get information about the next working hours period"""
        current_datetime = from_datetime
        
        # If we're in working hours, find the next period
        if self.is_working_hours(from_datetime, department_name):
            # Look for next working day
            return self._get_next_working_day(from_datetime.date(), department_name)
        
        # If we're outside working hours, look for next working hours today
        current_date = from_datetime.date()
        is_working_day, _ = self.is_working_day(current_date, department_name)
        
        if is_working_day:
            schedule = self.get_department_schedule(department_name)
            day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            day_name = day_names[current_date.weekday()]
            day_schedule = schedule.get(day_name, {})
            
            if day_schedule.get('open', False):
                start_time = day_schedule.get('start', time(9, 0))
                
                # Check if there are working hours later today
                if from_datetime.time() < start_time:
                    return {
                        'date': current_date.strftime('%Y-%m-%d'),
                        'day': day_name.title(),
                        'start_time': start_time.strftime('%H:%M'),
                        'end_time': day_schedule.get('end', time(17, 0)).strftime('%H:%M'),
                        'days_until': 0,
                        'hours_until': (datetime.combine(current_date, start_time) - from_datetime).total_seconds() / 3600
                    }
        
        # Look for next working day
        return self._get_next_working_day(current_date, department_name)
    
    def get_upcoming_holidays(self, days_ahead: int = 30) -> List[Dict]:
        """
        Get list of upcoming bank holidays.
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of upcoming holiday information
        """
        today = timezone.now().date()
        upcoming_holidays = []
        
        for date_str, holiday_name in self.barbados_holidays.items():
            holiday_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if today <= holiday_date <= today + timedelta(days=days_ahead):
                days_until = (holiday_date - today).days
                upcoming_holidays.append({
                    'date': date_str,
                    'name': holiday_name,
                    'days_until': days_until,
                    'is_today': holiday_date == today
                })
        
        # Sort by date
        upcoming_holidays.sort(key=lambda x: x['days_until'])
        return upcoming_holidays
    
    def get_working_hours_summary(self, department_name: str = None) -> Dict[str, Any]:
        """
        Get a summary of working hours for a department.
        
        Args:
            department_name: Name of the department
            
        Returns:
            Dictionary containing working hours summary
        """
        schedule = self.get_department_schedule(department_name)
        
        summary = {
            'department': department_name or 'default',
            'schedule': {},
            'total_working_hours_per_week': 0,
            'working_days_per_week': 0
        }
        
        for day_name, day_info in schedule.items():
            if day_info['open']:
                start_time = day_info['start']
                end_time = day_info['end']
                
                # Calculate hours for this day
                start_dt = datetime.combine(date.today(), start_time)
                end_dt = datetime.combine(date.today(), end_time)
                hours = (end_dt - start_dt).total_seconds() / 3600
                
                summary['schedule'][day_name.title()] = {
                    'open': True,
                    'start': start_time.strftime('%H:%M'),
                    'end': end_time.strftime('%H:%M'),
                    'hours': round(hours, 1)
                }
                
                summary['total_working_hours_per_week'] += hours
                summary['working_days_per_week'] += 1
            else:
                summary['schedule'][day_name.title()] = {
                    'open': False,
                    'start': None,
                    'end': None,
                    'hours': 0
                }
        
        summary['total_working_hours_per_week'] = round(summary['total_working_hours_per_week'], 1)
        
        return summary
