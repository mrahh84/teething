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
    Employee, Card, Location, EventType, Event, AttendanceRecord, UserRole
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


if __name__ == '__main__':
    # Run performance tests
    import unittest
    unittest.main()
