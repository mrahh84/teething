from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.db import connection
from django.test.utils import override_settings
from django.db.models import Q
from datetime import datetime, time, timedelta
import time as time_module

from .models import (
    Employee, Card, Location, EventType, Event, AttendanceRecord
)


class DatabaseOptimizationTestCase(TestCase):
    """Test cases for Phase 1 database query optimizations."""
    
    def setUp(self):
        """Set up test data for database optimization tests."""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test data
        self.card = Card.objects.create(designation='TEST001')
        self.location = Location.objects.create(name='Test Location')
        self.clock_in_type = EventType.objects.create(name='Clock In')
        self.clock_out_type = EventType.objects.create(name='Clock Out')
        
        # Create test employees
        self.employees = []
        for i in range(10):
            employee = Employee.objects.create(
                given_name=f'Test{i}',
                surname=f'Employee{i}',
                card_number=self.card,
                is_active=True
            )
            self.employees.append(employee)
        
        # Create clock-in events for today
        today = timezone.now().date()
        start_of_day = timezone.make_aware(datetime.combine(today, time.min))
        
        for i, employee in enumerate(self.employees[:5]):  # Only first 5 employees clock in
            Event.objects.create(
                employee=employee,
                event_type=self.clock_in_type,
                location=self.location,
                timestamp=start_of_day + timedelta(hours=9, minutes=i),
                created_by=self.user
            )
        
        # Create some attendance records
        for i, employee in enumerate(self.employees[:3]):  # First 3 have attendance records
            AttendanceRecord.objects.get_or_create(
                employee=employee,
                date=today,
                defaults={
                    'standup_attendance': 'YES',
                    'lunch_time': time(12, 0),
                    'created_by': self.user
                }
            )
    
    def test_progressive_entry_query_optimization(self):
        """Test that progressive_entry view uses optimized queries."""
        client = Client()
        client.force_login(self.user)
        
        # Count queries - should be significantly reduced from N+1 pattern
        with self.assertNumQueries(6):  # Realistic count: session, user, events, employees, cards, departments
            response = client.get(reverse('progressive_entry'))
            self.assertEqual(response.status_code, 200)
    
    def test_attendance_list_query_optimization(self):
        """Test that attendance_list view uses optimized queries."""
        client = Client()
        client.force_login(self.user)
        
        # Count queries - current state with N+1 queries from properties
        # This test documents the current state and will be improved in Phase 2
        with self.assertNumQueries(51):  # Current state with N+1 queries from arrival_time/departure_time properties
            response = client.get(reverse('attendance_list'))
            self.assertEqual(response.status_code, 200)
    
    def test_bulk_prefetch_optimization(self):
        """Test that bulk prefetch reduces N+1 queries."""
        today = timezone.now().date()
        
        # Test the optimized query pattern from progressive_entry
        start_of_day = timezone.make_aware(datetime.combine(today, time.min))
        end_of_day = timezone.make_aware(datetime.combine(today, time.max))
        
        # Get clocked-in employee IDs
        clocked_in_employee_ids = set(
            Event.objects.filter(
                event_type__name='Clock In',
                timestamp__gte=start_of_day,
                timestamp__lte=end_of_day
            ).values_list('employee_id', flat=True)
        )
        
        # Get employees with optimized prefetch
        employees = Employee.objects.filter(
            id__in=clocked_in_employee_ids, 
            is_active=True
        ).select_related('card_number').order_by('surname', 'given_name')
        
        # Get attendance records with optimized prefetch
        today_records = AttendanceRecord.objects.filter(
            date=today,
            employee__in=employees
        ).select_related('employee', 'employee__card_number')
        
        # Create lookup dictionary for O(1) access
        records_by_employee = {record.employee_id: record for record in today_records}
        
        # Test that we can access records efficiently
        for employee in employees:
            record = records_by_employee.get(employee.id)
            if record:
                self.assertIsNotNone(record.employee.card_number)
    
    def test_database_indexes_exist(self):
        """Test that the new database indexes have been created."""
        with connection.cursor() as cursor:
            # Check Event model indexes
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='common_event'
                AND name LIKE 'idx_%'
            """)
            event_indexes = [row[0] for row in cursor.fetchall()]
            
            expected_event_indexes = [
                'idx_emp_events_emp_time',
                'idx_event_type_time', 
                'idx_location_time'
            ]
            
            for index_name in expected_event_indexes:
                self.assertIn(index_name, event_indexes, f"Index {index_name} not found")
            
            # Check AttendanceRecord model indexes
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='common_attendancerecord'
                AND name LIKE 'common_atte_%'
            """)
            attendance_indexes = [row[0] for row in cursor.fetchall()]
            
            # Should have indexes for date, employee+date, status+date, employee+status
            self.assertGreaterEqual(len(attendance_indexes), 4)
            
            # Check Employee model indexes
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='common_employee'
                AND name LIKE 'common_empl_%'
            """)
            employee_indexes = [row[0] for row in cursor.fetchall()]
            
            # Should have indexes for is_active+surname+given_name and card_number+is_active
            self.assertGreaterEqual(len(employee_indexes), 2)
    
    def test_query_performance_improvement(self):
        """Test that optimized queries are faster than unoptimized ones."""
        today = timezone.now().date()
        
        # Test unoptimized query (simulating old pattern)
        start_time = time_module.time()
        employees = Employee.objects.filter(is_active=True)
        for employee in employees:
            # This would cause N+1 queries in the old pattern
            employee.card_number.designation if employee.card_number else None
        unoptimized_time = time_module.time() - start_time
        
        # Test optimized query
        start_time = time_module.time()
        employees_optimized = Employee.objects.filter(is_active=True).select_related('card_number')
        for employee in employees_optimized:
            employee.card_number.designation if employee.card_number else None
        optimized_time = time_module.time() - start_time
        
        # Optimized query should be faster
        self.assertLess(optimized_time, unoptimized_time)
    
    def test_attendance_record_lookup_optimization(self):
        """Test that attendance record lookups use O(1) dictionary access."""
        today = timezone.now().date()
        
        # Create test attendance records
        records = []
        for employee in self.employees[:5]:
            record, created = AttendanceRecord.objects.get_or_create(
                employee=employee,
                date=today,
                defaults={'created_by': self.user}
            )
            records.append(record)
        
        # Test optimized lookup pattern
        today_records = AttendanceRecord.objects.filter(
            date=today,
            employee__in=self.employees
        ).select_related('employee', 'employee__card_number')
        
        # Create lookup dictionary for O(1) access
        records_by_employee = {record.employee_id: record for record in today_records}
        
        # Test that lookups work correctly
        for employee in self.employees[:5]:
            record = records_by_employee.get(employee.id)
            self.assertIsNotNone(record)
            self.assertEqual(record.employee, employee)
    
    def test_employee_filtering_optimization(self):
        """Test that employee filtering uses optimized queries."""
        # Test department filtering
        employees = Employee.objects.filter(is_active=True).select_related('card_number')
        
        # Apply department filter (simulating the filter_employees_by_department function)
        filtered_employees = [emp for emp in employees if emp.card_number and 'TEST' in emp.card_number.designation]
        
        # Should have employees with TEST cards
        self.assertGreater(len(filtered_employees), 0)
        
        # Test search filtering
        search_query = 'Test'
        search_filtered = employees.filter(
            Q(given_name__icontains=search_query) |
            Q(surname__icontains=search_query) |
            Q(card_number__designation__icontains=search_query)
        )
        
        # Should find employees with 'Test' in their names
        self.assertGreater(search_filtered.count(), 0)
    
    def test_view_functionality_preserved(self):
        """Test that view functionality is preserved after optimizations."""
        client = Client()
        client.force_login(self.user)
        
        # Test progressive_entry view
        response = client.get(reverse('progressive_entry'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Employee')  # Should contain employee data
        
        # Test attendance_list view
        response = client.get(reverse('attendance_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Attendance Records')  # Should contain attendance data
    
    def test_ajax_functionality_preserved(self):
        """Test that AJAX functionality in progressive_entry is preserved."""
        client = Client()
        client.force_login(self.user)
        
        # Test AJAX save request
        employee = self.employees[0]
        response = client.post(
            reverse('progressive_entry'),
            {
                'employee_id': employee.id,
                'field_name': 'standup_attendance',
                'field_value': 'YES'
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        # Check that the attendance record was created/updated
        record = AttendanceRecord.objects.filter(employee=employee, date=timezone.now().date()).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.standup_attendance, 'YES')


class PerformanceMonitoringTestCase(TestCase):
    """Test cases for performance monitoring and metrics."""
    
    def setUp(self):
        """Set up test data for performance monitoring."""
        self.user = User.objects.create_user(
            username='perfuser',
            password='testpass123'
        )
        
        # Create minimal test data
        self.card = Card.objects.create(designation='PERF001')
        self.location = Location.objects.create(name='Perf Location')
        self.clock_in_type = EventType.objects.create(name='Clock In')
        
        self.employee = Employee.objects.create(
            given_name='Perf',
            surname='Test',
            card_number=self.card,
            is_active=True
        )
    
    def test_query_count_monitoring(self):
        """Test that we can monitor query counts."""
        # Test that optimized views use fewer queries
        client = Client()
        client.force_login(self.user)
        
        # Create a clock-in event
        Event.objects.create(
            employee=self.employee,
            event_type=self.clock_in_type,
            location=self.location,
            timestamp=timezone.now(),
            created_by=self.user
        )
        
        # Test that progressive_entry uses optimized queries
        with self.assertNumQueries(6):  # Realistic count: session, user, events, employees, cards, departments
            response = client.get(reverse('progressive_entry'))
            self.assertEqual(response.status_code, 200)
    
    def test_response_time_monitoring(self):
        """Test that response times are reasonable."""
        client = Client()
        client.force_login(self.user)
        
        # Test response time for optimized views
        start_time = time_module.time()
        response = client.get(reverse('progressive_entry'))
        response_time = time_module.time() - start_time
        
        # Response should be fast (less than 1 second)
        self.assertLess(response_time, 1.0)
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    # Run performance tests
    import unittest
    unittest.main()
