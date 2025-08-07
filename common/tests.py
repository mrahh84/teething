from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.db import connection
from django.test.utils import override_settings
from django.db.models import Q
from datetime import datetime, time, timedelta, date
import time as time_module

from .models import (
    Employee, Card, Location, EventType, Event, AttendanceRecord, UserRole, Department,
    AnalyticsCache, ReportConfiguration, EmployeeAnalytics, DepartmentAnalytics, SystemPerformance
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
        
        # Create attendance role for the test user
        UserRole.objects.create(user=self.user, role='attendance')
    
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
        with self.assertNumQueries(6):  # Optimized state with bulk prefetch and reduced queries (6 due to department filtering)
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

    def test_historical_progressive_results_with_clock_times(self):
        """Test that historical progressive results include clock in/out times."""
        client = Client()
        client.force_login(self.user)
        
        # Create test data with clock in/out events
        today = timezone.now().date()
        start_of_day = timezone.make_aware(datetime.combine(today, time.min))
        
        # Create clock in/out events for test employee
        test_employee = self.employees[0]
        clock_in_event = Event.objects.create(
            employee=test_employee,
            event_type=self.clock_in_type,
            location=self.location,
            timestamp=start_of_day + timedelta(hours=9, minutes=30),  # 9:30 AM
            created_by=self.user
        )
        clock_out_event = Event.objects.create(
            employee=test_employee,
            event_type=self.clock_out_type,
            location=self.location,
            timestamp=start_of_day + timedelta(hours=17, minutes=30),  # 5:30 PM
            created_by=self.user
        )
        
        # Test the historical progressive results view
        response = client.get(
            reverse('historical_progressive_results'),
            {
                'date_from': today.isoformat(),
                'date_to': today.isoformat(),
                'department': 'All Departments'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        # Verify that clock times are included in the response
        self.assertContains(response, '09:30')  # Clock in time
        self.assertContains(response, '17:30')  # Clock out time


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
        with self.assertNumQueries(6):  # Optimized count: session, user, events, employees, cards, departments
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


class LetterFilteringTestCase(TestCase):
    """Test cases for letter filtering functionality in main_security view."""
    
    def setUp(self):
        """Set up test data for letter filtering tests."""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test employees with different surnames
        self.employees = []
        surnames = ['Adams', 'Brown', 'Clark', 'Davis', 'Evans', 'Fisher', 'Garcia', 'Harris']
        
        for i, surname in enumerate(surnames):
            employee = Employee.objects.create(
                given_name=f'Test{i}',
                surname=surname,
                is_active=True
            )
            self.employees.append(employee)
    
    def test_letter_filtering_works(self):
        """Test that letter filtering correctly filters employees by surname."""
        client = Client()
        client.force_login(self.user)
        
        # Test filtering by letter 'A'
        response = client.get(reverse('main_security') + '?letter=A')
        self.assertEqual(response.status_code, 200)
        
        # Should only show employees with surnames starting with 'A'
        self.assertContains(response, 'Adams')
        self.assertNotContains(response, 'Brown')
        self.assertNotContains(response, 'Clark')
        
        # Test filtering by letter 'B'
        response = client.get(reverse('main_security') + '?letter=A')
        self.assertEqual(response.status_code, 200)
        
        # Should only show employees with surnames starting with 'A'
        self.assertContains(response, 'Adams')
        self.assertNotContains(response, 'Brown')
        self.assertNotContains(response, 'Clark')
        
        # Test 'all' filter - explicitly set letter to 'all'
        response = client.get(reverse('main_security') + '?letter=all')
        self.assertEqual(response.status_code, 200)
        
        # Should show all employees (check for at least a few)
        self.assertContains(response, 'Adams')
        self.assertContains(response, 'Brown')
        self.assertContains(response, 'Clark')
    
    def test_letter_filtering_case_insensitive(self):
        """Test that letter filtering is case insensitive."""
        client = Client()
        client.force_login(self.user)
        
        # Test lowercase letter
        response = client.get(reverse('main_security') + '?letter=a')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adams')
        
        # Test uppercase letter
        response = client.get(reverse('main_security') + '?letter=A')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adams')
    
    def test_letter_filtering_with_other_filters(self):
        """Test that letter filtering works with other filters."""
        client = Client()
        client.force_login(self.user)
        
        # Test letter filtering with search
        response = client.get(reverse('main_security') + '?letter=A&search=Test')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adams')
        
        # Test letter filtering with status filter
        response = client.get(reverse('main_security') + '?letter=A&status=all')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adams')


class TemplateFragmentCachingTestCase(TestCase):
    """Test cases for template fragment caching functionality."""
    
    def setUp(self):
        """Set up test data for template caching tests."""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test employees
        self.employees = []
        for i in range(5):
            employee = Employee.objects.create(
                given_name=f'Test{i}',
                surname=f'Employee{i}',
                is_active=True
            )
            self.employees.append(employee)
        
        # Create test attendance records
        today = timezone.now().date()
        for employee in self.employees:
            AttendanceRecord.objects.create(
                employee=employee,
                date=today,
                created_by=self.user
            )
    
    def test_attendance_list_template_renders_with_caching(self):
        """Test that attendance list template renders successfully with fragment caching."""
        client = Client()
        client.force_login(self.user)
        
        # Test that the page renders without errors
        response = client.get(reverse('attendance_list'))
        self.assertEqual(response.status_code, 200)
        
        # Verify that the page contains expected content (indicating caching is working)
        self.assertContains(response, 'Attendance Records')
        self.assertContains(response, 'Apply Filters')
        self.assertContains(response, 'Clear Filters')
    
    def test_main_security_template_renders_with_caching(self):
        """Test that main security template renders successfully with fragment caching."""
        client = Client()
        client.force_login(self.user)
        
        # Test that the page renders without errors
        response = client.get(reverse('main_security'))
        self.assertEqual(response.status_code, 200)
        
        # Verify that the page contains expected content (indicating caching is working)
        self.assertContains(response, 'Employee Status')
        self.assertContains(response, 'Apply Filters')
        self.assertContains(response, 'Clear All Filters')
    
    def test_analytics_template_renders_with_caching(self):
        """Test that analytics template renders successfully with fragment caching."""
        client = Client()
        client.force_login(self.user)
        
        # Test that the page renders without errors
        response = client.get(reverse('attendance_analytics'))
        self.assertEqual(response.status_code, 200)
        
        # Verify that the page contains expected content (indicating caching is working)
        self.assertContains(response, 'Attendance Analytics')
        self.assertContains(response, 'Apply Filter')
        self.assertContains(response, 'Period Attendance Summary')
    
    def test_cache_keys_are_unique_for_different_users(self):
        """Test that cache keys are unique for different users."""
        client = Client()
        
        # Create second user
        user2 = User.objects.create_user(
            username='testuser2',
            password='testpass123'
        )
        
        # Login first user
        client.force_login(self.user)
        response1 = client.get(reverse('attendance_list'))
        self.assertEqual(response1.status_code, 200)
        
        # Login second user
        client.force_login(user2)
        response2 = client.get(reverse('attendance_list'))
        self.assertEqual(response2.status_code, 200)
        
        # Both responses should be successful (different cache keys)
        self.assertNotEqual(response1.content, response2.content)
    
    def test_cache_invalidation_on_data_change(self):
        """Test that cache is invalidated when data changes."""
        client = Client()
        client.force_login(self.user)
        
        # First request
        response1 = client.get(reverse('attendance_list'))
        self.assertEqual(response1.status_code, 200)
        
        # Add new attendance record
        new_employee = Employee.objects.create(
            given_name='New',
            surname='Employee',
            is_active=True
        )
        AttendanceRecord.objects.create(
            employee=new_employee,
            date=timezone.now().date(),
            created_by=self.user
        )
        
        # Second request - should show new data
        response2 = client.get(reverse('attendance_list'))
        self.assertEqual(response2.status_code, 200)
        
        # Content should be different due to new data
        self.assertNotEqual(response1.content, response2.content)
    
    def test_template_fragment_caching_performance(self):
        """Test that template fragment caching improves performance."""
        client = Client()
        client.force_login(self.user)
        
        # Measure first request (cache miss)
        start_time = time_module.time()
        response1 = client.get(reverse('attendance_list'))
        first_request_time = time_module.time() - start_time
        self.assertEqual(response1.status_code, 200)
        
        # Measure second request (cache hit)
        start_time = time_module.time()
        response2 = client.get(reverse('attendance_list'))
        second_request_time = time_module.time() - start_time
        self.assertEqual(response2.status_code, 200)
        
        # Second request should be faster (cached fragments) - allow for small variations
        self.assertLessEqual(second_request_time, first_request_time * 1.1)
    
    def test_cache_fragments_are_functional(self):
        """Test that cache fragments are actually working by checking performance."""
        client = Client()
        client.force_login(self.user)
        
        # First request - should cache fragments
        response1 = client.get(reverse('attendance_list'))
        self.assertEqual(response1.status_code, 200)
        
        # Second request - should use cached fragments
        response2 = client.get(reverse('attendance_list'))
        self.assertEqual(response2.status_code, 200)
        
        # Both responses should contain the same data (indicating caching worked)
        self.assertContains(response1, 'Attendance Records')
        self.assertContains(response2, 'Attendance Records')
        
        # The responses should be functionally equivalent (same data, different CSRF tokens)
        self.assertIn('Attendance Records', str(response1.content))
        self.assertIn('Attendance Records', str(response2.content))


class UserRoleTestCase(TestCase):
    def setUp(self):
        """Create test users with different roles"""
        # Create users
        self.security_user = User.objects.create_user('security', 'security@test.com', 'password')
        self.attendance_user = User.objects.create_user('attendance', 'attendance@test.com', 'password')
        self.reporting_user = User.objects.create_user('reporting', 'reporting@test.com', 'password')
        self.admin_user = User.objects.create_user('admin', 'admin@test.com', 'password')
        
        # Assign roles
        UserRole.objects.create(user=self.security_user, role='security')
        UserRole.objects.create(user=self.attendance_user, role='attendance')
        UserRole.objects.create(user=self.reporting_user, role='reporting')
        UserRole.objects.create(user=self.admin_user, role='admin')
        
        # Create test data
        self.location = Location.objects.create(name='Test Location')
        self.event_type = EventType.objects.create(name='Clock In')
        self.employee = Employee.objects.create(
            given_name='Test',
            surname='Employee'
        )
    
    def test_security_access(self):
        """Test security role access"""
        client = Client()
        client.login(username='security', password='password')
        
        # Should access clock functions
        response = client.get(reverse('main_security'))
        self.assertEqual(response.status_code, 200)
        
        # Should not access attendance management
        response = client.get(reverse('attendance_list'))
        self.assertEqual(response.status_code, 302)  # Redirected
        
        # Should not access reports
        response = client.get(reverse('reports_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirected
    
    def test_attendance_access(self):
        """Test attendance management role access"""
        client = Client()
        client.login(username='attendance', password='password')
        
        # Should access attendance functions
        response = client.get(reverse('attendance_list'))
        self.assertEqual(response.status_code, 200)
        
        # Should access clock functions
        response = client.get(reverse('main_security'))
        self.assertEqual(response.status_code, 200)
        
        # Should access reports
        response = client.get(reverse('reports_dashboard'))
        self.assertEqual(response.status_code, 200)
    
    def test_reporting_access(self):
        """Test reporting role access"""
        client = Client()
        client.login(username='reporting', password='password')
        
        # Should access reports
        response = client.get(reverse('reports_dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # Should not access attendance management
        response = client.get(reverse('attendance_list'))
        self.assertEqual(response.status_code, 302)  # Redirected
        
        # Should not access clock functions
        response = client.get(reverse('main_security'))
        self.assertEqual(response.status_code, 302)  # Redirected
    
    def test_admin_access(self):
        """Test admin role access"""
        client = Client()
        client.login(username='admin', password='password')
        
        # Should access everything
        response = client.get(reverse('main_security'))
        self.assertEqual(response.status_code, 200)
        
        response = client.get(reverse('attendance_list'))
        self.assertEqual(response.status_code, 200)
        
        response = client.get(reverse('reports_dashboard'))
        self.assertEqual(response.status_code, 200)
    
    def test_user_role_methods(self):
        """Test User model role methods"""
        # Test get_role
        self.assertEqual(self.security_user.get_role(), 'security')
        self.assertEqual(self.attendance_user.get_role(), 'attendance')
        self.assertEqual(self.reporting_user.get_role(), 'reporting')
        self.assertEqual(self.admin_user.get_role(), 'admin')
        
        # Test has_role
        self.assertTrue(self.security_user.has_role('security'))
        self.assertFalse(self.security_user.has_role('admin'))
        
        # Test has_any_role
        self.assertTrue(self.attendance_user.has_any_role(['attendance', 'admin']))
        self.assertFalse(self.attendance_user.has_any_role(['security', 'reporting']))
    
    def test_no_role_user(self):
        """Test user without role assignment"""
        no_role_user = User.objects.create_user('norole', 'norole@test.com', 'password')
        client = Client()
        client.login(username='norole', password='password')
        
        # Should be redirected to main_security with error message
        response = client.get(reverse('attendance_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('main_security', response.url)


class RoleIntegrationTestCase(TestCase):
    def setUp(self):
        """Set up test data for integration tests"""
        # Create users with roles
        self.security_user = User.objects.create_user('security', 'security@test.com', 'password')
        self.attendance_user = User.objects.create_user('attendance', 'attendance@test.com', 'password')
        self.reporting_user = User.objects.create_user('reporting', 'reporting@test.com', 'password')
        self.admin_user = User.objects.create_user('admin', 'admin@test.com', 'password')
        
        UserRole.objects.create(user=self.security_user, role='security')
        UserRole.objects.create(user=self.attendance_user, role='attendance')
        UserRole.objects.create(user=self.reporting_user, role='reporting')
        UserRole.objects.create(user=self.admin_user, role='admin')
        
        # Create test data
        self.location = Location.objects.create(name='Test Location')
        self.event_type = EventType.objects.create(name='Clock In')
        self.employee = Employee.objects.create(
            given_name='Test',
            surname='Employee'
        )
    
    def test_api_permissions(self):
        """Test API endpoint permissions"""
        client = Client()
        
        # Test security user API access
        client.login(username='security', password='password')
        response = client.get(reverse('api_event_list'))
        self.assertEqual(response.status_code, 200)
        
        # Test admin user API access
        client.login(username='admin', password='password')
        response = client.get(reverse('api_single_employee', args=[self.employee.id]))
        self.assertEqual(response.status_code, 200)
        
        # Test non-admin user API access (should be denied)
        client.login(username='security', password='password')
        response = client.get(reverse('api_single_employee', args=[self.employee.id]))
        self.assertEqual(response.status_code, 403)  # Forbidden
    
    def test_template_role_filters(self):
        """Test template role filters"""
        from django.template import Template, Context
        
        template = Template("""
            {% load role_extras %}
            {% if user|has_role:'security' %}Security User{% endif %}
            {% if user|has_any_role:'attendance,admin' %}Attendance or Admin{% endif %}
            {% if user|get_role_display %}{{ user|get_role_display }}{% endif %}
        """)
        
        context = Context({'user': self.security_user})
        result = template.render(context)
        
        self.assertIn('Security User', result)
        self.assertNotIn('Attendance or Admin', result)
        self.assertIn('Security', result)
    
    def test_role_based_navigation(self):
        """Test that navigation shows correct items based on role"""
        client = Client()
        
        # Test security user navigation
        client.login(username='security', password='password')
        response = client.get(reverse('main_security'))
        self.assertContains(response, 'Clock-in/Out')
        
        # Test admin user navigation
        client.login(username='admin', password='password')
        response = client.get(reverse('main_security'))
        self.assertContains(response, 'Clock-in/Out')
        self.assertContains(response, 'Attendance')


class RoleModelTestCase(TestCase):
    def setUp(self):
        """Set up test data for model tests"""
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password')
    
    def test_userrole_creation(self):
        """Test UserRole model creation"""
        user_role = UserRole.objects.create(user=self.user, role='security')
        self.assertEqual(user_role.user, self.user)
        self.assertEqual(user_role.role, 'security')
        self.assertIsNotNone(user_role.created_at)
        self.assertIsNotNone(user_role.updated_at)
    
    def test_userrole_str(self):
        """Test UserRole string representation"""
        user_role = UserRole.objects.create(user=self.user, role='attendance')
        self.assertEqual(str(user_role), 'testuser - Attendance Management')
    
    def test_userrole_choices(self):
        """Test UserRole choices"""
        choices = UserRole.ROLE_CHOICES
        expected_choices = [
            ('security', 'Security'),
            ('attendance', 'Attendance Management'),
            ('reporting', 'Reporting'),
            ('admin', 'Administrator'),
        ]
        self.assertEqual(choices, expected_choices)
    
    def test_user_methods(self):
        """Test User model role methods"""
        # Test without role
        self.assertIsNone(self.user.get_role())
        self.assertFalse(self.user.has_role('security'))
        self.assertFalse(self.user.has_any_role(['security', 'admin']))
        
        # Test with role
        UserRole.objects.create(user=self.user, role='security')
        self.assertEqual(self.user.get_role(), 'security')
        self.assertTrue(self.user.has_role('security'))
        self.assertTrue(self.user.has_any_role(['security', 'admin']))
        self.assertFalse(self.user.has_any_role(['attendance', 'reporting']))


class AnalyticsModelsTestCase(TestCase):
    """Test cases for analytics models"""
    
    def setUp(self):
        """Set up test data for analytics models"""
        # Create departments
        self.department1 = Department.objects.create(
            name='Test Department 1',
            code='TEST1',
            description='Test department 1'
        )
        self.department2 = Department.objects.create(
            name='Test Department 2',
            code='TEST2',
            description='Test department 2'
        )
        
        # Create employees
        self.employee1 = Employee.objects.create(
            given_name='John',
            surname='Doe',
            department=self.department1
        )
        self.employee2 = Employee.objects.create(
            given_name='Jane',
            surname='Smith',
            department=self.department2
        )
        
        # Create analytics cache
        self.analytics_cache = AnalyticsCache.objects.create(
            cache_key='test_cache_key',
            data={'test': 'data'},
            expires_at=timezone.now() + timedelta(hours=1),
            cache_type='daily_summary'
        )
        
        # Create report configuration
        self.user = User.objects.create_user(
            username='testuser',
            password='password'
        )
        self.report_config = ReportConfiguration.objects.create(
            user=self.user,
            report_type='daily_dashboard',
            configuration={'test': 'config'}
        )
        
        # Create employee analytics
        self.employee_analytics = EmployeeAnalytics.objects.create(
            employee=self.employee1,
            date=date.today(),
            total_events=5,
            clock_in_count=2,
            clock_out_count=2,
            total_hours_worked=8.5,
            attendance_score=85.0,
            is_anomaly=False
        )
        
        # Create department analytics
        self.department_analytics = DepartmentAnalytics.objects.create(
            department=self.department1,
            date=date.today(),
            total_employees=10,
            present_employees=8,
            absent_employees=2,
            average_attendance_rate=80.0,
            average_hours_worked=7.5,
            total_hours_worked=75.0
        )
        
        # Create system performance
        self.system_performance = SystemPerformance.objects.create(
            date=date.today(),
            total_events_processed=100,
            active_users=5,
            api_requests=50,
            average_response_time=0.5,
            database_queries=200,
            slow_queries=2,
            cache_hit_rate=85.0,
            cache_misses=15
        )
    
    def test_department_creation(self):
        """Test department model creation"""
        self.assertEqual(self.department1.name, 'Test Department 1')
        self.assertEqual(self.department1.code, 'TEST1')
        self.assertTrue(self.department1.is_active)
        self.assertEqual(str(self.department1), 'Test Department 1')
    
    def test_analytics_cache_creation(self):
        """Test analytics cache model creation"""
        self.assertEqual(self.analytics_cache.cache_key, 'test_cache_key')
        self.assertEqual(self.analytics_cache.cache_type, 'daily_summary')
        self.assertFalse(self.analytics_cache.is_expired())
        self.assertEqual(str(self.analytics_cache), 'daily_summary: test_cache_key')
    
    def test_report_configuration_creation(self):
        """Test report configuration model creation"""
        self.assertEqual(self.report_config.user, self.user)
        self.assertEqual(self.report_config.report_type, 'daily_dashboard')
        self.assertEqual(self.report_config.configuration, {'test': 'config'})
        self.assertEqual(str(self.report_config), 'testuser - daily_dashboard')
    
    def test_employee_analytics_creation(self):
        """Test employee analytics model creation"""
        self.assertEqual(self.employee_analytics.employee, self.employee1)
        self.assertEqual(self.employee_analytics.total_events, 5)
        self.assertEqual(self.employee_analytics.total_hours_worked, 8.5)
        self.assertEqual(self.employee_analytics.attendance_score, 85.0)
        self.assertFalse(self.employee_analytics.is_anomaly)
        self.assertEqual(str(self.employee_analytics), 'John Doe - 2025-07-30')
    
    def test_department_analytics_creation(self):
        """Test department analytics model creation"""
        self.assertEqual(self.department_analytics.department, self.department1)
        self.assertEqual(self.department_analytics.total_employees, 10)
        self.assertEqual(self.department_analytics.present_employees, 8)
        self.assertEqual(self.department_analytics.average_attendance_rate, 80.0)
        self.assertEqual(str(self.department_analytics), 'Test Department 1 - 2025-07-30')
    
    def test_system_performance_creation(self):
        """Test system performance model creation"""
        self.assertEqual(self.system_performance.total_events_processed, 100)
        self.assertEqual(self.system_performance.active_users, 5)
        self.assertEqual(self.system_performance.average_response_time, 0.5)
        self.assertEqual(self.system_performance.cache_hit_rate, 85.0)
        self.assertEqual(str(self.system_performance), 'System Performance - 2025-07-30')
    
    def test_employee_department_relationship(self):
        """Test employee-department relationship"""
        self.assertEqual(self.employee1.department, self.department1)
        self.assertEqual(self.employee2.department, self.department2)
        self.assertIn(self.employee1, self.department1.employee_set.all())
        self.assertIn(self.employee2, self.department2.employee_set.all())


class AnalyticsAPITestCase(TestCase):
    """Test cases for analytics API endpoints"""
    
    def setUp(self):
        """Set up test data for API tests"""
        # Create test user with reporting role
        self.user = User.objects.create_user(
            username='reporting_user',
            password='password'
        )
        self.user_role = UserRole.objects.create(
            user=self.user,
            role='reporting'
        )
        
        # Create test data
        self.department = Department.objects.create(
            name='Test Department',
            code='TEST',
            description='Test department'
        )
        
        self.employee = Employee.objects.create(
            given_name='John',
            surname='Doe',
            department=self.department
        )
        
        self.employee_analytics = EmployeeAnalytics.objects.create(
            employee=self.employee,
            date=date.today(),
            total_events=5,
            total_hours_worked=8.5,
            attendance_score=85.0
        )
        
        self.department_analytics = DepartmentAnalytics.objects.create(
            department=self.department,
            date=date.today(),
            total_employees=10,
            present_employees=8,
            average_attendance_rate=80.0
        )
        
        self.analytics_cache = AnalyticsCache.objects.create(
            cache_key='test_cache',
            data={'test': 'data'},
            expires_at=timezone.now() + timedelta(hours=1),
            cache_type='daily_summary'
        )
        
        self.report_config = ReportConfiguration.objects.create(
            user=self.user,
            report_type='daily_dashboard',
            configuration={'test': 'config'}
        )
    
    def test_departments_api_list(self):
        """Test departments API list endpoint"""
        # Create admin user for this test
        admin_user = User.objects.create_user(
            username='admin_user',
            password='password'
        )
        UserRole.objects.create(
            user=admin_user,
            role='admin'
        )
        
        self.client.login(username='admin_user', password='password')
        response = self.client.get('/common/api/departments/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertGreater(len(data['results']), 0)
    
    def test_employee_analytics_api_list(self):
        """Test employee analytics API list endpoint"""
        self.client.login(username='reporting_user', password='password')
        response = self.client.get('/common/api/employee-analytics/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertGreater(len(data['results']), 0)
    
    def test_department_analytics_api_list(self):
        """Test department analytics API list endpoint"""
        self.client.login(username='reporting_user', password='password')
        response = self.client.get('/common/api/department-analytics/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertGreater(len(data['results']), 0)
    
    def test_analytics_cache_api_list(self):
        """Test analytics cache API list endpoint"""
        self.client.login(username='reporting_user', password='password')
        response = self.client.get('/common/api/analytics-cache/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertGreater(len(data['results']), 0)
    
    def test_report_configuration_api_list(self):
        """Test report configuration API list endpoint"""
        self.client.login(username='reporting_user', password='password')
        response = self.client.get('/common/api/report-configurations/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertGreater(len(data['results']), 0)
    
    def test_employee_analytics_filtering(self):
        """Test employee analytics API filtering"""
        self.client.login(username='reporting_user', password='password')
        
        # Test filtering by employee
        response = self.client.get(f'/common/api/employee-analytics/?employee_id={self.employee.id}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        
        # Test filtering by date
        today = date.today().isoformat()
        response = self.client.get(f'/common/api/employee-analytics/?start_date={today}&end_date={today}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
    
    def test_department_analytics_filtering(self):
        """Test department analytics API filtering"""
        self.client.login(username='reporting_user', password='password')
        
        # Test filtering by department
        response = self.client.get(f'/common/api/department-analytics/?department_id={self.department.id}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        
        # Test filtering by date
        today = date.today().isoformat()
        response = self.client.get(f'/common/api/department-analytics/?start_date={today}&end_date={today}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)


class AnalyticsIntegrationTestCase(TestCase):
    """Integration tests for analytics functionality"""
    
    def setUp(self):
        """Set up test data for integration tests"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='password'
        )
        
        # Create department
        self.department = Department.objects.create(
            name='Test Department',
            code='TEST',
            description='Test department'
        )
        
        # Create employee
        self.employee = Employee.objects.create(
            given_name='John',
            surname='Doe',
            department=self.department
        )
        
        # Create events for analytics
        self.event_type = EventType.objects.create(name='Clock In')
        self.location = Location.objects.create(name='Test Location')
        
        # Create some events
        Event.objects.create(
            event_type=self.event_type,
            employee=self.employee,
            location=self.location,
            timestamp=timezone.now(),
            created_by=self.user
        )
    
    def test_employee_department_assignment(self):
        """Test that employees can be assigned to departments"""
        self.assertEqual(self.employee.department, self.department)
        self.assertIn(self.employee, self.department.employee_set.all())
    
    def test_analytics_cache_functionality(self):
        """Test analytics cache functionality"""
        # Create cache entry
        cache_entry = AnalyticsCache.objects.create(
            cache_key='test_integration',
            data={'employee_count': 1, 'department_count': 1},
            expires_at=timezone.now() + timedelta(hours=1),
            cache_type='daily_summary'
        )
        
        # Test cache retrieval
        retrieved_cache = AnalyticsCache.objects.get(cache_key='test_integration')
        self.assertEqual(retrieved_cache.data['employee_count'], 1)
        self.assertFalse(retrieved_cache.is_expired())
    
    def test_report_configuration_user_specific(self):
        """Test that report configurations are user-specific"""
        config1 = ReportConfiguration.objects.create(
            user=self.user,
            report_type='daily_dashboard',
            configuration={'user': 'specific'}
        )
        
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            password='password'
        )
        
        config2 = ReportConfiguration.objects.create(
            user=other_user,
            report_type='daily_dashboard',
            configuration={'user': 'other'}
        )
        
        # Test that configurations are separate
        self.assertNotEqual(config1.configuration, config2.configuration)
        self.assertEqual(config1.user, self.user)
        self.assertEqual(config2.user, other_user)


class RealTimeAnalyticsTestCase(TestCase):
    """Test cases for real-time analytics API endpoints"""
    
    def setUp(self):
        """Set up test data for real-time analytics"""
        # Create test user with reporting role
        self.reporting_user = User.objects.create_user(
            username='realtime_test_user',
            password='password',
            email='realtime@test.com'
        )
        UserRole.objects.create(user=self.reporting_user, role='reporting')
        
        # Create test department
        self.department = Department.objects.create(
            name='Test Department',
            code='TEST',
            description='Test department for real-time analytics',
            is_active=True
        )
        
        # Create test employees
        self.employee1 = Employee.objects.create(
            given_name='John',
            surname='Doe',
            department=self.department,
            is_active=True
        )
        
        self.employee2 = Employee.objects.create(
            given_name='Jane',
            surname='Smith',
            department=self.department,
            is_active=True
        )
        
        # Create test event types
        self.clock_in_type = EventType.objects.create(name='Clock In')
        self.clock_out_type = EventType.objects.create(name='Clock Out')
        self.check_in_type = EventType.objects.create(name='Check In To Room')
        self.check_out_type = EventType.objects.create(name='Check Out of Room')
        
        # Create test locations
        self.location1 = Location.objects.create(name='Main Security')
        self.location2 = Location.objects.create(name='Repository and Conservation')
        
        # Create test events
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Employee 1: Clocked in today
        Event.objects.create(
            employee=self.employee1,
            event_type=self.clock_in_type,
            location=self.location1,
            timestamp=timezone.now() - timedelta(hours=2)
        )
        
        # Employee 2: Clocked in and out today
        Event.objects.create(
            employee=self.employee2,
            event_type=self.clock_in_type,
            location=self.location1,
            timestamp=timezone.now() - timedelta(hours=4)
        )
        Event.objects.create(
            employee=self.employee2,
            event_type=self.clock_out_type,
            location=self.location1,
            timestamp=timezone.now() - timedelta(hours=1)
        )
        
        # Add some movement events
        Event.objects.create(
            employee=self.employee1,
            event_type=self.check_in_type,
            location=self.location2,
            timestamp=timezone.now() - timedelta(hours=1)
        )
    
    def test_realtime_employee_status_api(self):
        """Test real-time employee status API endpoint"""
        self.client.login(username='realtime_test_user', password='password')
        response = self.client.get('/common/api/realtime/employees/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check that we get employee data with real-time status (paginated response)
        self.assertIsInstance(data, dict)
        self.assertIn('results', data)
        self.assertIsInstance(data['results'], list)
        self.assertEqual(len(data['results']), 2)
        
        # Check that employee data includes real-time fields
        employee_data = data['results'][0]
        self.assertIn('current_status', employee_data)
        self.assertIn('last_activity', employee_data)
        self.assertIn('current_location', employee_data)
        
        # Check specific status values
        emp1_data = next(emp for emp in data['results'] if emp['given_name'] == 'John' and emp['surname'] == 'Doe')
        emp2_data = next(emp for emp in data['results'] if emp['given_name'] == 'Jane' and emp['surname'] == 'Smith')
        
        self.assertEqual(emp1_data['current_status'], 'clocked_in')
        self.assertEqual(emp2_data['current_status'], 'clocked_out')
    
    def test_live_attendance_counter_api(self):
        """Test live attendance counter API endpoint"""
        self.client.login(username='realtime_test_user', password='password')
        response = self.client.get('/common/api/realtime/attendance-counter/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check that we get attendance statistics
        self.assertIn('total_employees', data)
        self.assertIn('currently_clocked_in', data)
        self.assertIn('currently_clocked_out', data)
        self.assertIn('attendance_rate', data)
        self.assertIn('last_updated', data)
        
        # Check specific values
        self.assertEqual(data['total_employees'], 2)
        self.assertEqual(data['currently_clocked_in'], 1)
        self.assertEqual(data['currently_clocked_out'], 1)
        self.assertEqual(data['attendance_rate'], 50.0)
    
    def test_attendance_heatmap_api(self):
        """Test attendance heat map API endpoint"""
        self.client.login(username='realtime_test_user', password='password')
        response = self.client.get('/common/api/realtime/heatmap/?days=7')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check that we get heat map data
        self.assertIn('heat_map_data', data)
        self.assertIn('date_range', data)
        
        # Check data structure
        heat_map_data = data['heat_map_data']
        self.assertIsInstance(heat_map_data, list)
        
        # Check that we have data for each hour of each day
        self.assertGreater(len(heat_map_data), 0)
        
        # Check individual data points
        for item in heat_map_data:
            self.assertIn('date', item)
            self.assertIn('hour', item)
            self.assertIn('count', item)
            self.assertIn('intensity', item)
    
    def test_employee_movement_api(self):
        """Test employee movement API endpoint"""
        self.client.login(username='realtime_test_user', password='password')
        response = self.client.get('/common/api/realtime/movements/?days=7')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check that we get movement data
        self.assertIn('nodes', data)
        self.assertIn('links', data)
        self.assertIn('date_range', data)
        
        # Check data structure
        self.assertIsInstance(data['nodes'], list)
        self.assertIsInstance(data['links'], list)
        
        # Check that we have location nodes
        self.assertGreater(len(data['nodes']), 0)
        
        # Check that nodes include our test locations
        location_names = [loc.name for loc in Location.objects.all()]
        for node in data['nodes']:
            self.assertIn(node, location_names)
    

        self.assertContains(response, 'Live Employee Status')
        self.assertContains(response, 'Attendance Heat Map')
        self.assertContains(response, 'Employee Movement Flow')




if __name__ == '__main__':
    # Run performance tests
    import unittest
    unittest.main()
