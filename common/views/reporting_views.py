"""
Reporting and analytics views.

This module contains all reporting functionality including
dashboards, exports, and analytical reports.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest, StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as django_timezone
from drf_spectacular.utils import extend_schema
from django.db.models import Q, Count, Prefetch, Avg
from datetime import datetime, timedelta, date, timezone, time
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
import json
import traceback
import csv
import re
import logging
from typing import Optional
from django.core.cache import cache

from ..models import (
    Employee, Event, EventType, Location, AttendanceRecord, Card, Department,
    AnalyticsCache, ReportConfiguration, EmployeeAnalytics, DepartmentAnalytics, SystemPerformance,
    TaskAssignment, LocationMovement, LocationAnalytics
)
from ..forms import (
    AttendanceRecordForm, BulkHistoricalUpdateForm, ProgressiveEntryForm, 
    HistoricalProgressiveEntryForm, AttendanceFilterForm,
    TaskAssignmentForm, BulkTaskAssignmentForm, LocationAssignmentFilterForm
)
from ..utils import performance_monitor, query_count_monitor
from ..services.attendance_service import (
    normalize_department_from_designation as svc_normalize_department_from_designation,
    list_available_departments as svc_list_available_departments,
    filter_employees_by_department as svc_filter_employees_by_department,
)
from ..decorators import security_required, attendance_required, reporting_required, admin_required


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def reports_dashboard(request):
    """Main reports dashboard."""
    context = {
        'page_title': 'Reports Dashboard',
        'active_tab': 'reports_dashboard',
    }
    return render(request, 'reports/dashboard.html', context)


@admin_required  # Admin role only
@extend_schema(exclude=True)
def performance_dashboard(request):
    """Performance monitoring dashboard."""
    from django.db.models import Count, Avg, Q
    from datetime import timedelta
    
    today = django_timezone.localtime(django_timezone.now()).date()
    last_30_days = today - timedelta(days=30)
    
    # Get system performance metrics
    system_metrics = SystemPerformance.objects.filter(
        measurement_date__gte=last_30_days
    ).order_by('-measurement_date')
    
    # Get employee performance metrics
    employees = Employee.objects.filter(is_active=True).select_related('department')
    
    # Calculate attendance rates
    attendance_rates = []
    for employee in employees:
        events = employee.employee_events.filter(
            timestamp__date__gte=last_30_days,
            timestamp__date__lte=today
        )
        
        if events.exists():
            clock_in_count = events.filter(event_type__name='Clock In').count()
            attendance_rate = (clock_in_count / 30) * 100 if 30 > 0 else 0
            
            attendance_rates.append({
                'employee_name': f"{employee.given_name} {employee.surname}",
                'department': employee.department.name if employee.department else 'N/A',
                'attendance_rate': round(attendance_rate, 1),
                'total_events': events.count()
            })
    
    # Sort by attendance rate
    attendance_rates.sort(key=lambda x: x['attendance_rate'], reverse=True)
    
    context = {
        'page_title': 'Performance Dashboard',
        'active_tab': 'performance_dashboard',
        'system_metrics': system_metrics,
        'attendance_rates': attendance_rates,
        'total_employees': employees.count(),
        'avg_attendance_rate': round(
            sum(r['attendance_rate'] for r in attendance_rates) / len(attendance_rates), 1
        ) if attendance_rates else 0
    }
    return render(request, 'reports/performance_dashboard.html', context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def daily_dashboard_report(request):
    """Daily dashboard report."""
    from django.db.models import Count, Q
    from datetime import timedelta
    
    today = django_timezone.localtime(django_timezone.now()).date()
    yesterday = today - timedelta(days=1)
    
    # Get daily statistics
    total_employees = Employee.objects.filter(is_active=True).count()
    present_today = Event.objects.filter(
        event_type__name='Clock In',
        timestamp__date=today
    ).values('employee').distinct().count()
    
    present_yesterday = Event.objects.filter(
        event_type__name='Clock In',
        timestamp__date=yesterday
    ).values('employee').distinct().count()
    
    # Calculate change
    change = present_today - present_yesterday
    change_percentage = (change / present_yesterday * 100) if present_yesterday > 0 else 0
    
    context = {
        'page_title': 'Daily Dashboard Report',
        'active_tab': 'daily_dashboard',
        'today': today,
        'yesterday': yesterday,
        'total_employees': total_employees,
        'present_today': present_today,
        'present_yesterday': present_yesterday,
        'change': change,
        'change_percentage': round(change_percentage, 1),
        'change_abs': abs(change),
        'change_percentage_abs': abs(round(change_percentage, 1))
    }
    return render(request, 'reports/daily_dashboard_report.html', context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def employee_history_report(request):
    """Employee history report."""
    from django.db.models import Count, Q
    from datetime import timedelta
    
    # Get filter parameters
    employee_id = request.GET.get('employee_id')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    if not all([employee_id, start_date_str, end_date_str]):
        # Show form for selecting parameters
        employees = Employee.objects.filter(is_active=True).order_by('given_name', 'surname')
        context = {
            'page_title': 'Employee History Report',
            'active_tab': 'employee_history',
            'employees': employees
        }
        return render(request, 'reports/employee_history_report.html', context)
    
    try:
        employee = get_object_or_404(Employee, id=employee_id)
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get employee events
        events = employee.employee_events.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).order_by('timestamp')
        
        # Calculate statistics
        total_events = events.count()
        clock_in_events = events.filter(event_type__name='Clock In')
        clock_out_events = events.filter(event_type__name='Clock Out')
        
        # Calculate total hours
        total_hours = 0
        for clock_in in clock_in_events:
            # Find corresponding clock out
            clock_out = clock_out_events.filter(
                timestamp__gt=clock_in.timestamp
            ).first()
            
            if clock_out:
                duration = clock_out.timestamp - clock_in.timestamp
                total_hours += duration.total_seconds() / 3600
        
        context = {
            'page_title': 'Employee History Report',
            'active_tab': 'employee_history',
            'employee': employee,
            'start_date': start_date,
            'end_date': end_date,
            'events': events,
            'total_events': total_events,
            'total_hours': round(total_hours, 2),
            'clock_in_count': clock_in_events.count(),
            'clock_out_count': clock_out_events.count()
        }
        return render(request, 'reports/employee_history_report.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating report: {str(e)}')
        return redirect('employee_history_report')


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def period_summary_report(request):
    """Period summary report."""
    from django.db.models import Count, Q
    from datetime import timedelta
    
    # Get filter parameters
    period_type = request.GET.get('period_type', 'month')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    if not all([start_date_str, end_date_str]):
        # Show form for selecting parameters
        context = {
            'page_title': 'Period Summary Report',
            'active_tab': 'period_summary',
            'period_type': period_type
        }
        return render(request, 'reports/period_summary_report.html', context)
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get events in period
        events = Event.objects.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).select_related('employee', 'employee__department', 'event_type')
        
        # Calculate statistics by department
        department_stats = {}
        for event in events:
            dept_name = event.employee.department.name if event.employee.department else 'Unknown'
            if dept_name not in department_stats:
                department_stats[dept_name] = {
                    'total_events': 0,
                    'clock_ins': 0,
                    'clock_outs': 0,
                    'employees': set()
                }
            
            department_stats[dept_name]['total_events'] += 1
            department_stats[dept_name]['employees'].add(event.employee.id)
            
            if event.event_type.name == 'Clock In':
                department_stats[dept_name]['clock_ins'] += 1
            elif event.event_type.name == 'Clock Out':
                department_stats[dept_name]['clock_outs'] += 1
        
        # Convert sets to counts
        for dept in department_stats.values():
            dept['unique_employees'] = len(dept['employees'])
            del dept['employees']
        
        context = {
            'page_title': 'Period Summary Report',
            'active_tab': 'period_summary',
            'start_date': start_date,
            'end_date': end_date,
            'period_type': period_type,
            'department_stats': department_stats,
            'total_events': events.count(),
            'total_employees': Employee.objects.filter(is_active=True).count()
        }
        return render(request, 'reports/period_summary_report.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generating report: {str(e)}')
        return redirect('period_summary_report')


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
@xframe_options_sameorigin
def generate_marimo_report(request, report_type):
    """Generate Marimo report."""
    from django.db.models import Count, Q
    from datetime import timedelta
    
    today = django_timezone.localtime(django_timezone.now()).date()
    
    if report_type == 'daily':
        # Daily report
        start_date = today
        end_date = today
        title = f"Daily Report - {today.strftime('%B %d, %Y')}"
    elif report_type == 'weekly':
        # Weekly report
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        title = f"Weekly Report - {start_date.strftime('%B %d')} to {end_date.strftime('%B %d, %Y')}"
    elif report_type == 'monthly':
        # Monthly report
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        title = f"Monthly Report - {start_date.strftime('%B %Y')}"
    else:
        return HttpResponse("Invalid report type", status=400)
    
    # Get events in period
    events = Event.objects.filter(
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date
    ).select_related('employee', 'employee__department', 'event_type')
    
    # Calculate statistics
    total_events = events.count()
    total_employees = Employee.objects.filter(is_active=True).count()
    present_employees = events.filter(event_type__name='Clock In').values('employee').distinct().count()
    
    # Department breakdown
    department_stats = {}
    for event in events:
        dept_name = event.employee.department.name if event.employee.department else 'Unknown'
        if dept_name not in department_stats:
            department_stats[dept_name] = {
                'events': 0,
                'employees': set(),
                'clock_ins': 0,
                'clock_outs': 0
            }
        
        department_stats[dept_name]['events'] += 1
        department_stats[dept_name]['employees'].add(event.employee.id)
        
        if event.event_type.name == 'Clock In':
            department_stats[dept_name]['clock_ins'] += 1
        elif event.event_type.name == 'Clock Out':
            department_stats[dept_name]['clock_outs'] += 1
    
    # Convert sets to counts
    for dept in department_stats.values():
        dept['unique_employees'] = len(dept['employees'])
        del dept['employees']
    
    # Generate HTML report
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .summary {{ display: flex; margin-bottom: 30px; }}
            .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; margin-right: 20px; text-align: center; flex: 1; }}
            .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
            .stat-label {{ font-size: 14px; color: #666; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            h1, h2 {{ color: #333; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{title}</h1>
            <p>Generated on {today.strftime('%B %d, %Y at %I:%M %p')}</p>
        </div>

        <div class="summary">
            <div class="stat-box">
                <div class="stat-label">Total Events</div>
                <div class="stat-value">{total_events}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Total Employees</div>
                <div class="stat-value">{total_employees}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Present Today</div>
                <div class="stat-value">{present_employees}</div>
            </div>
        </div>

        <h2>Department Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Department</th>
                    <th>Events</th>
                    <th>Employees</th>
                    <th>Clock Ins</th>
                    <th>Clock Outs</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for dept_name, stats in department_stats.items():
        html += f"""
                <tr>
                    <td>{dept_name}</td>
                    <td>{stats['events']}</td>
                    <td>{stats['unique_employees']}</td>
                    <td>{stats['clock_ins']}</td>
                    <td>{stats['clock_outs']}</td>
                </tr>
        """
    
    html += """
            </tbody>
        </table>
    </body>
    </html>
    """
    
    return HttpResponse(html, content_type="text/html")


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def generate_daily_dashboard_html(request, selected_date):
    """Generate daily dashboard HTML report."""
    from django.db.models import Count, Q
    from datetime import timedelta
    
    try:
        if isinstance(selected_date, str):
            selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        
        # Get daily statistics
        total_employees = Employee.objects.filter(is_active=True).count()
        present_today = Event.objects.filter(
            event_type__name='Clock In',
            timestamp__date=selected_date
        ).values('employee').distinct().count()
        
        absent_today = total_employees - present_today
        attendance_rate = (present_today / total_employees * 100) if total_employees > 0 else 0
        
        # Get events by hour
        hourly_events = {}
        for hour in range(24):
            hourly_events[hour] = {
                'clock_ins': 0,
                'clock_outs': 0
            }
        
        events = Event.objects.filter(
            timestamp__date=selected_date
        ).select_related('employee', 'employee__department', 'event_type')
        
        for event in events:
            hour = event.timestamp.hour
            if event.event_type.name == 'Clock In':
                hourly_events[hour]['clock_ins'] += 1
            elif event.event_type.name == 'Clock Out':
                hourly_events[hour]['clock_outs'] += 1
        
        # Department breakdown
        department_stats = {}
        for event in events:
            dept_name = event.employee.department.name if event.employee.department else 'Unknown'
            if dept_name not in department_stats:
                department_stats[dept_name] = {
                    'present': 0,
                    'total': 0
                }
            
            if event.event_type.name == 'Clock In':
                department_stats[dept_name]['present'] += 1
        
        # Get total employees per department
        for dept_name in department_stats:
            dept_employees = Employee.objects.filter(
                department__name=dept_name,
                is_active=True
            ).count()
            department_stats[dept_name]['total'] = dept_employees
            department_stats[dept_name]['absent'] = dept_employees - department_stats[dept_name]['present']
        
        # Generate HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Daily Dashboard - {selected_date.strftime('%B %d, %Y')}</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .summary {{ display: flex; margin-bottom: 30px; }}
                .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; margin-right: 20px; text-align: center; flex: 1; }}
                .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .stat-label {{ font-size: 14px; color: #666; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
                .chart {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Daily Dashboard Report</h1>
                <h2>{selected_date.strftime('%B %d, %Y')}</h2>
            </div>

            <div class="summary">
                <div class="stat-box">
                    <div class="stat-label">Total Employees</div>
                    <div class="stat-value">{total_employees}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Present Today</div>
                    <div class="stat-value">{present_today}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Absent Today</div>
                    <div class="stat-value">{absent_today}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Attendance Rate</div>
                    <div class="stat-value">{round(attendance_rate, 1)}%</div>
                </div>
            </div>

            <h2>Department Breakdown</h2>
            <table>
                <thead>
                    <tr>
                        <th>Department</th>
                        <th>Present</th>
                        <th>Absent</th>
                        <th>Total</th>
                        <th>Rate</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for dept_name, stats in department_stats.items():
            rate = (stats['present'] / stats['total'] * 100) if stats['total'] > 0 else 0
            html += f"""
                    <tr>
                        <td>{dept_name}</td>
                        <td>{stats['present']}</td>
                        <td>{stats['absent']}</td>
                        <td>{stats['total']}</td>
                        <td>{round(rate, 1)}%</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>

            <h2>Hourly Activity</h2>
            <table>
                <thead>
                    <tr>
                        <th>Hour</th>
                        <th>Clock Ins</th>
                        <th>Clock Outs</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for hour in range(24):
            html += f"""
                    <tr>
                        <td>{hour:02d}:00</td>
                        <td>{hourly_events[hour]['clock_ins']}</td>
                        <td>{hourly_events[hour]['clock_outs']}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </body>
        </html>
        """
        
        return HttpResponse(html, content_type="text/html")
        
    except Exception as e:
        return HttpResponse(
            f"Error generating daily dashboard: {str(e)}", status=500
        )


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def generate_employee_history_html(request, employee_id, start_date, end_date):
    """Generate employee history HTML report."""
    try:
        employee = get_object_or_404(Employee, id=employee_id)
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get employee events
        events = employee.employee_events.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).order_by('timestamp')
        
        # Calculate statistics
        total_events = events.count()
        clock_in_events = events.filter(event_type__name='Clock In')
        clock_out_events = events.filter(event_type__name='Clock Out')
        
        # Calculate total hours and daily breakdown
        total_hours = 0
        daily_hours = {}
        event_days = set()
        
        for clock_in in clock_in_events:
            # Find corresponding clock out
            clock_out = clock_out_events.filter(
                timestamp__gt=clock_in.timestamp
            ).first()
            
            if clock_out:
                duration = clock_out.timestamp - clock_in.timestamp
                hours = duration.total_seconds() / 3600
                total_hours += hours
                
                day = clock_in.timestamp.date()
                event_days.add(day)
                if day not in daily_hours:
                    daily_hours[day] = 0
                daily_hours[day] += hours
        
        # Prepare data for charts
        dates = sorted(daily_hours.keys())
        hours_data = [daily_hours[date] for date in dates]
        
        # Create bar chart data
        bar_chart_data = {
            "x": [date.strftime('%Y-%m-%d') for date in dates],
            "y": hours_data,
            "type": "bar",
            "name": "Hours Worked",
            "marker": {"color": "rgb(55, 83, 109)"}
        }
        
        bar_chart_layout = {
            "title": "Daily Hours Worked",
            "xaxis": {"title": "Date"},
            "yaxis": {"title": "Hours"},
            "margin": {"l": 50, "r": 50, "b": 50, "t": 50, "pad": 4}
        }
        
        bar_chart_json = json.dumps({"data": [bar_chart_data], "layout": bar_chart_layout})
        
        # Create calendar heatmap data
        calendar_data = []
        for date in dates:
            hours = daily_hours[date]
            calendar_data.append([date.strftime('%Y-%m-%d'), hours])
        
        calendar_plot = {
            "type": "heatmap",
            "x": [d.strftime('%Y-%m-%d') for d in dates],
            "y": [0],  # Single row for heatmap
            "z": [hours_data],
            "colorscale": [
                [0, "rgb(255,255,255)"],  # No hours = white
                [0.1, "rgb(220,237,252)"],
                [0.5, "rgb(66,146,198)"],
                [1, "rgb(8,48,107)"],  # Max hours = dark blue
            ],
            "showscale": True,
        }

        calendar_layout = {
            "title": "Attendance Calendar",
            "margin": {"l": 50, "r": 50, "b": 50, "t": 50, "pad": 4},
        }

        calendar_json = json.dumps({"data": [calendar_plot], "layout": calendar_layout})

        # Create HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Employee Attendance History</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .employee-info {{ margin-bottom: 30px; }}
                .summary {{ display: flex; margin-bottom: 30px; }}
                .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; margin-right: 20px; text-align: center; }}
                .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .stat-label {{ font-size: 14px; color: #666; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>Employee Attendance History</h1>

            <div class="employee-info">
                <h2>{employee.given_name} {employee.surname}</h2>
                <p>Report period: {start_date.strftime("%Y-%m-%d")} to {(end_date - timedelta(days=1)).strftime("%Y-%m-%d")}</p>
            </div>

            <div class="summary">
                <div class="stat-box">
                    <div class="stat-label">Total Days</div>
                    <div class="stat-value">{len(event_days)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Hours</div>
                    <div class="stat-value">{round(total_hours, 2)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Average Hours/Day</div>
                    <div class="stat-value">{round(total_hours / len(event_days), 2) if event_days else 0}</div>
                </div>
            </div>

            <h2>Hours Overview</h2>
            <div id="barChart" style="height: 300px;"></div>

            <h2>Attendance Calendar</h2>
            <div id="calendarHeatmap" style="height: 400px;"></div>

            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script>
                var barChartData = {bar_chart_json};
                Plotly.newPlot('barChart', barChartData.data, barChartData.layout);

                var calendarData = {calendar_json};
                Plotly.newPlot('calendarHeatmap', calendarData.data, calendarData.layout);
            </script>
        </body>
        </html>
        """

        return HttpResponse(html, content_type="text/html")

    except Exception as e:
        return HttpResponse(
            f"Error generating employee history report: {str(e)}", status=500
        )


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def comprehensive_reports(request):
    """Comprehensive reports dashboard."""
    from django.db.models import Count, Q
    from datetime import timedelta
    
    today = django_timezone.localtime(django_timezone.now()).date()
    last_30_days = today - timedelta(days=30)
    
    # Get overall statistics
    total_employees = Employee.objects.filter(is_active=True).count()
    total_events = Event.objects.filter(
        timestamp__date__gte=last_30_days
    ).count()
    
    # Get department statistics - OPTIMIZED with single query aggregation
    department_stats = Employee.objects.filter(
        is_active=True
    ).values('department__name').annotate(
        employee_count=Count('id'),
        event_count=Count(
            'employee_events',
            filter=Q(employee_events__timestamp__date__gte=last_30_days)
        ),
        clock_in_count=Count(
            'employee_events',
            filter=Q(
                employee_events__event_type__name='Clock In',
                employee_events__timestamp__date__gte=last_30_days
            )
        )
    ).filter(
        department__isnull=False
    ).order_by('-clock_in_count')
    
    # Calculate attendance rates and format data
    department_stats = [
        {
            'name': stat['department__name'],
            'employees': stat['employee_count'],
            'events': stat['event_count'],
            'clock_ins': stat['clock_in_count'],
            'attendance_rate': round(
                (stat['clock_in_count'] / stat['employee_count'] * 100) 
                if stat['employee_count'] > 0 else 0, 1
            )
        }
        for stat in department_stats
    ]
    
    # Sort by attendance rate
    department_stats.sort(key=lambda x: x['attendance_rate'], reverse=True)
    
    # Get recent activity
    recent_events = Event.objects.filter(
        timestamp__date__gte=today
    ).select_related('employee', 'employee__department', 'event_type').order_by('-timestamp')[:10]
    
    context = {
        'page_title': 'Comprehensive Reports',
        'active_tab': 'comprehensive_reports',
        'total_employees': total_employees,
        'total_events': total_events,
        'department_stats': department_stats,
        'recent_events': recent_events,
        'period': {
            'start_date': last_30_days,
            'end_date': today
        }
    }
    return render(request, 'reports/comprehensive_reports.html', context)


def generate_period_summary_html(request, start_date, end_date, department_filter=None):
    """Generate period summary HTML report."""
    from django.db.models import Count, Q
    from datetime import timedelta
    
    try:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get events in period
        events = Event.objects.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).select_related('employee', 'employee__department', 'event_type')
        
        # Apply department filter if specified
        if department_filter:
            events = events.filter(employee__department__name__icontains=department_filter)
        
        # Calculate statistics by department - OPTIMIZED with aggregation
        from django.db.models import Count, Q
        
        # Get department statistics in a single query
        dept_stats = events.values('employee__department__name').annotate(
            total_events=Count('id'),
            clock_ins=Count('id', filter=Q(event_type__name='Clock In')),
            clock_outs=Count('id', filter=Q(event_type__name='Clock Out')),
            unique_employees=Count('employee', distinct=True)
        ).filter(
            employee__department__isnull=False
        ).order_by('-total_events')
        
        # Convert to the expected format
        department_stats = {}
        total_events = 0
        total_employees = set()
        
        for stat in dept_stats:
            dept_name = stat['employee__department__name']
            department_stats[dept_name] = {
                'total_events': stat['total_events'],
                'clock_ins': stat['clock_ins'],
                'clock_outs': stat['clock_outs'],
                'unique_employees': stat['unique_employees'],
                'total_hours': 0  # Will be calculated below
            }
            total_events += stat['total_events']
        
        # Calculate hours worked for each department (this part is more complex and kept as is)
        for dept_name, stats in department_stats.items():
            dept_events = events.filter(employee__department__name=dept_name)
            clock_ins = dept_events.filter(event_type__name='Clock In')
            clock_outs = dept_events.filter(event_type__name='Clock Out')
            
            total_hours = 0
            for clock_in in clock_ins:
                # Find corresponding clock out
                clock_out = clock_outs.filter(
                    timestamp__gt=clock_in.timestamp
                ).first()
                
                if clock_out:
                    duration = clock_out.timestamp - clock_in.timestamp
                    total_hours += duration.total_seconds() / 3600
            
            stats['total_hours'] = round(total_hours, 2)
        
        # Generate HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Period Summary Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .summary {{ display: flex; margin-bottom: 30px; }}
                .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; margin-right: 20px; text-align: center; flex: 1; }}
                .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .stat-label {{ font-size: 14px; color: #666; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
                .filter-info {{ background-color: #e8f4fd; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Period Summary Report</h1>
                <p>Period: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}</p>
            </div>

            <div class="filter-info">
                <strong>Report Period:</strong> {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}<br>
                <strong>Department Filter:</strong> {department_filter if department_filter else 'All Departments'}<br>
                <strong>Generated:</strong> {django_timezone.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>

            <div class="summary">
                <div class="stat-box">
                    <div class="stat-label">Total Events</div>
                    <div class="stat-value">{total_events}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Employees</div>
                    <div class="stat-value">{len(total_employees)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Departments</div>
                    <div class="stat-value">{len(department_stats)}</div>
                </div>
            </div>

            <h2>Department Breakdown</h2>
            <table>
                <thead>
                    <tr>
                        <th>Department</th>
                        <th>Events</th>
                        <th>Employees</th>
                        <th>Clock Ins</th>
                        <th>Clock Outs</th>
                        <th>Total Hours</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for dept_name, stats in department_stats.items():
            html += f"""
                    <tr>
                        <td>{dept_name}</td>
                        <td>{stats['total_events']}</td>
                        <td>{stats['unique_employees']}</td>
                        <td>{stats['clock_ins']}</td>
                        <td>{stats['clock_outs']}</td>
                        <td>{stats['total_hours']}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>

            <h2>Summary Statistics</h2>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Total Events</td>
                        <td>{total_events}</td>
                    </tr>
                    <tr>
                        <td>Total Employees</td>
                        <td>{len(total_employees)}</td>
                    </tr>
                    <tr>
                        <td>Total Departments</td>
                        <td>{len(department_stats)}</td>
                    </tr>
                    <tr>
                        <td>Total Clock Ins</td>
                        <td>{sum(stats['clock_ins'] for stats in department_stats.values())}</td>
                    </tr>
                    <tr>
                        <td>Total Clock Outs</td>
                        <td>{sum(stats['clock_outs'] for stats in department_stats.values())}</td>
                    </tr>
                    <tr>
                        <td>Total Hours Worked</td>
                        <td>{sum(stats['total_hours'] for stats in department_stats.values())}</td>
                    </tr>
                </tbody>
            </table>
        </body>
        </html>
        """
        
        return HttpResponse(html, content_type="text/html")
        
    except Exception as e:
        return HttpResponse(
            f"Error generating period summary report: {str(e)}", status=500
        )


def employee_history_report_csv(request):
    """Export employee history as CSV."""
    from django.http import StreamingHttpResponse
    import csv
    
    try:
        # Get parameters
        employee_id = request.GET.get('employee_id')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        if not all([employee_id, start_date_str, end_date_str]):
            return HttpResponse("Missing required parameters", status=400)
        
        employee = get_object_or_404(Employee, id=employee_id)
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get employee events
        events = employee.employee_events.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).order_by('timestamp')
        
        # Create CSV response
        response = StreamingHttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="employee_history_{employee.id}_{start_date}_{end_date}.csv"'}
        )
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Date', 'Time', 'Event Type', 'Location', 'Notes', 'Employee ID', 'Employee Name'
        ])
        
        # Write data rows
        for event in events:
            # Convert to local timezone for display
            local_timestamp = timezone.localtime(event.timestamp)
            writer.writerow([
                local_timestamp.date(),
                local_timestamp.time(),
                event.event_type.name,
                event.location.name if event.location else 'N/A',
                event.notes or '',
                employee.id,
                f"{employee.given_name} {employee.surname}"
            ])
        
        return response
        
    except Exception as e:
        return HttpResponse(
            f"Error generating CSV report: {str(e)}", status=500
        )


def period_summary_report_csv(request):
    """Export period summary as CSV."""
    from django.http import StreamingHttpResponse
    import csv
    
    try:
        # Get parameters
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        department_filter = request.GET.get('department')
        
        if not all([start_date_str, end_date_str]):
            return HttpResponse("Missing required parameters", status=400)
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get events in period
        events = Event.objects.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).select_related('employee', 'employee__department', 'event_type')
        
        # Apply department filter if specified
        if department_filter:
            events = events.filter(employee__department__name__icontains=department_filter)
        
        # Calculate statistics by department
        department_stats = {}
        total_events = 0
        total_employees = set()
        
        for event in events:
            total_events += 1
            total_employees.add(event.employee.id)
            
            dept_name = event.employee.department.name if event.employee.department else 'Unknown'
            if dept_name not in department_stats:
                department_stats[dept_name] = {
                    'total_events': 0,
                    'clock_ins': 0,
                    'clock_outs': 0,
                    'employees': set(),
                    'total_hours': 0
                }
            
            department_stats[dept_name]['total_events'] += 1
            department_stats[dept_name]['employees'].add(event.employee.id)
            
            if event.event_type.name == 'Clock In':
                department_stats[dept_name]['clock_ins'] += 1
            elif event.event_type.name == 'Clock Out':
                department_stats[dept_name]['clock_outs'] += 1
        
        # Calculate hours worked for each department
        for dept_name, stats in department_stats.items():
            dept_events = events.filter(employee__department__name=dept_name)
            clock_ins = dept_events.filter(event_type__name='Clock In')
            clock_outs = dept_events.filter(event_type__name='Clock Out')
            
            total_hours = 0
            for clock_in in clock_ins:
                # Find corresponding clock out
                clock_out = clock_outs.filter(
                    timestamp__gt=clock_in.timestamp
                ).first()
                
                if clock_out:
                    duration = clock_out.timestamp - clock_in.timestamp
                    total_hours += duration.total_seconds() / 3600
            
            stats['total_hours'] = round(total_hours, 2)
            stats['unique_employees'] = len(stats['employees'])
            del stats['employees']
        
        # Create CSV response
        response = StreamingHttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="period_summary_{start_date}_{end_date}.csv"'}
        )
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Department', 'Total Events', 'Employees', 'Clock Ins', 'Clock Outs', 'Total Hours'
        ])
        
        # Write department data
        for dept_name, stats in department_stats.items():
            writer.writerow([
                dept_name,
                stats['total_events'],
                stats['unique_employees'],
                stats['clock_ins'],
                stats['clock_outs'],
                stats['total_hours']
            ])
        
        # Write summary row
        writer.writerow([])
        writer.writerow(['SUMMARY', '', '', '', '', ''])
        writer.writerow([
            'TOTAL',
            total_events,
            len(total_employees),
            sum(stats['clock_ins'] for stats in department_stats.values()),
            sum(stats['clock_outs'] for stats in department_stats.values()),
            sum(stats['total_hours'] for stats in department_stats.values())
        ])
        
        return response
        
    except Exception as e:
        return HttpResponse(
            f"Error generating CSV report: {str(e)}", status=500
        )


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def async_report_generation(request):
    """Async report generation dashboard."""
    
    if request.method == 'POST':
        from ..services.async_report_service import AsyncReportService
        
        async_service = AsyncReportService()
        
        # Get report parameters
        report_type = request.POST.get('report_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        department = request.POST.get('department')
        
        # Validate parameters
        if not all([report_type, start_date, end_date]):
            messages.error(request, 'Missing required parameters')
            return redirect('async_report_generation')
        
        try:
            # Convert dates
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date format')
            return redirect('async_report_generation')
        
        # Prepare parameters
        report_params = {
            'start_date': start_date,
            'end_date': end_date,
            'department': department
        }
        
        # Queue report generation
        report_id = async_service.queue_report_generation(
            request.user.id, report_type, report_params
        )
        
        messages.success(
            request, 
            f'Report queued successfully. Report ID: {report_id}'
        )
        
        return redirect('async_report_status', report_id=report_id)
    
    # Get available report types
    report_types = [
        {'value': 'attendance_summary', 'label': 'Attendance Summary'},
        {'value': 'department_performance', 'label': 'Department Performance'},
        {'value': 'comprehensive_report', 'label': 'Comprehensive Report'},
    ]
    
    # Get user's queued reports
    from ..services.async_report_service import AsyncReportService
    async_service = AsyncReportService()
    
    user_reports = []
    for report_type in ['attendance_summary', 'department_performance', 'comprehensive_report']:
        # Check for cached reports
        cache_key = f"async_report:{request.user.id}:{report_type}"
        cached_report = cache.get(cache_key)
        if cached_report:
            user_reports.append({
                'type': report_type,
                'status': 'ready',
                'generated_at': cached_report.get('generated_at'),
                'data': cached_report
            })
    
    context = {
        'page_title': 'Async Report Generation',
        'active_tab': 'async_reports',
        'report_types': report_types,
        'user_reports': user_reports,
    }
    
    return render(request, 'reports/async_report_generation.html', context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def async_report_status(request, report_id):
    """Check status of async report generation."""
    
    from ..services.async_report_service import AsyncReportService
    
    async_service = AsyncReportService()
    status = async_service.get_report_status(report_id)
    
    context = {
        'page_title': 'Report Status',
        'active_tab': 'async_reports',
        'report_id': report_id,
        'status': status,
    }
    
    return render(request, 'reports/async_report_status.html', context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def async_report_download(request, report_id):
    """Download completed async report."""
    
    from ..services.async_report_service import AsyncReportService
    
    async_service = AsyncReportService()
    status = async_service.get_report_status(report_id)
    
    if status['status'] != 'ready':
        messages.error(request, 'Report not ready for download')
        return redirect('async_report_status', report_id=report_id)
    
    # Generate download response based on report type
    report_data = status['data']
    report_type = report_data['report_type']
    
    if request.GET.get('format') == 'csv':
        return _generate_csv_response(report_data, report_type)
    elif request.GET.get('format') == 'json':
        return _generate_json_response(report_data, report_type)
    else:
        # Default to HTML view
        context = {
            'page_title': f'{report_type.replace("_", " ").title()} Report',
            'active_tab': 'async_reports',
            'report_data': report_data,
            'report_id': report_id,
        }
        return render(request, 'reports/async_report_view.html', context)


def _generate_csv_response(report_data, report_type):
    """Generate CSV response for report data."""
    
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    if report_type == 'attendance_summary':
        # Write header
        writer.writerow(['Employee ID', 'Given Name', 'Surname', 'Department', 'Total Days', 'On Time Days', 'Late Days', 'Absent Days'])
        
        # Write data
        for row in report_data['data']:
            writer.writerow([
                row['employee_id'],
                row['given_name'],
                row['surname'],
                row['department_name'],
                row['total_days'],
                row['on_time_days'],
                row['late_days'],
                row['absent_days']
            ])
    
    elif report_type == 'department_performance':
        # Write header
        writer.writerow(['Department ID', 'Department Name', 'Total Employees', 'Total Records', 'On Time Count', 'Late Count', 'Absent Count', 'Attendance Rate'])
        
        # Write data
        for row in report_data['data']:
            writer.writerow([
                row['department_id'],
                row['department_name'],
                row['total_employees'],
                row['total_attendance_records'],
                row['on_time_count'],
                row['late_count'],
                row['absent_count'],
                f"{row['attendance_rate']:.1f}%"
            ])
    
    elif report_type == 'comprehensive_report':
        # Write summary
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Employees', report_data['summary']['total_employees']])
        writer.writerow(['Total Events', report_data['summary']['total_events']])
        writer.writerow(['Total Departments', report_data['summary']['total_departments']])
        writer.writerow(['Report Period', report_data['summary']['report_period']])
        writer.writerow([])
        
        # Write attendance summary
        writer.writerow(['Attendance Summary'])
        writer.writerow(['Employee ID', 'Given Name', 'Surname', 'Department', 'Total Days', 'On Time Days', 'Late Days', 'Absent Days'])
        
        for row in report_data['data']['attendance_summary']:
            writer.writerow([
                row['employee_id'],
                row['given_name'],
                row['surname'],
                row['department_name'],
                row['total_days'],
                row['on_time_days'],
                row['late_days'],
                row['absent_days']
            ])
    
    return response


def _generate_json_response(report_data, report_type):
    """Generate JSON response for report data."""
    
    from django.http import JsonResponse
    
    return JsonResponse(report_data, json_dumps_params={'indent': 2})


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def optimized_attendance_summary(request):
    """Optimized attendance summary using Phase 3 optimizations."""
    
    from ..services.optimized_reporting_service import OptimizedReportingService
    
    # Get parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    department_id = request.GET.get('department_id')
    
    # Default to last 30 days
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
    
    # Convert department_id to int if provided
    if department_id:
        try:
            department_id = int(department_id)
        except ValueError:
            department_id = None
    
    # Get optimized data
    service = OptimizedReportingService()
    attendance_data = service.get_attendance_summary_sql(
        start_date, end_date, department_id
    )
    
    # Get departments for filter
    departments = Department.objects.filter(is_active=True).order_by('name')
    
    context = {
        'page_title': 'Optimized Attendance Summary',
        'active_tab': 'optimized_reports',
        'attendance_data': attendance_data,
        'start_date': start_date,
        'end_date': end_date,
        'department_id': department_id,
        'departments': departments,
        'total_employees': len(attendance_data),
        'total_days': sum(d['total_days'] for d in attendance_data) if attendance_data else 0,
    }
    
    return render(request, 'reports/optimized_attendance_summary.html', context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def paginated_attendance_list(request):
    """Paginated attendance list using Phase 3 optimizations."""
    
    from ..services.optimized_reporting_service import PaginatedReportService
    
    # Get parameters
    date_filter = request.GET.get('date')
    department_filter = request.GET.get('department')
    page = request.GET.get('page', 1)
    
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    # Default to today if no date specified
    if not date_filter:
        date_filter = timezone.now().date().isoformat()
    
    try:
        target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
    except ValueError:
        target_date = timezone.now().date()
    
    # Get paginated data
    service = PaginatedReportService(page_size=25)
    result = service.get_paginated_attendance_data(
        target_date, department_filter, page
    )
    
    # Get departments for filter
    departments = Department.objects.filter(is_active=True).order_by('name')
    
    context = {
        'page_title': 'Paginated Attendance List',
        'active_tab': 'optimized_reports',
        'records': result['records'],
        'pagination': result['pagination'],
        'date_filter': target_date.isoformat(),
        'department_filter': department_filter,
        'departments': departments,
    }
    
    return render(request, 'reports/paginated_attendance_list.html', context)