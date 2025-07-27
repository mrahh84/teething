import marimo as mo
import pandas as pd
import datetime
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go

__generated_with = "0.13.6"
app = mo.App(width="medium")


@app.cell
def imports():
    import marimo as mo
    import pandas as pd
    import datetime
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go
    import os
    import sys
    import django
    return django, datetime, go, mo, os, pd, px, sys


@app.cell
def setup_django_environment():
    # Add the project root directory to Python path
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Set up Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
    import django
    django.setup()
    
    # Now you can import Django models
    from common.models import Employee, Event, EventType, Location
    from django.utils import timezone
    return Employee, Event, EventType, Location, timezone


@app.cell
def date_selector(mo):
    today = datetime.date.today()
    
    date_input = mo.ui.date(
        value=today,
        label="Select Date",
        min=today - datetime.timedelta(days=365),
        max=today
    )
    
    return date_input


@app.cell
def load_attendance_data(Employee, Event, date_input, pd, timezone):
    # Get the selected date from the date picker
    selected_date = date_input.value
    
    # Convert to datetime objects for filtering
    start_of_day = datetime.datetime.combine(selected_date, datetime.time.min)
    end_of_day = datetime.datetime.combine(selected_date, datetime.time.max)
    
    # Make timezone-aware if your Django settings use timezone support
    start_of_day = timezone.make_aware(start_of_day) if timezone.is_naive(start_of_day) else start_of_day
    end_of_day = timezone.make_aware(end_of_day) if timezone.is_naive(end_of_day) else end_of_day
    
    # Get all employees
    all_employees = Employee.objects.all()
    
    # Get all clock events for the selected date
    clock_events = Event.objects.filter(
        timestamp__range=(start_of_day, end_of_day),
        event_type__name__in=["Clock In", "Clock Out"]
    ).select_related('employee', 'event_type')
    
    # Convert to pandas DataFrame
    event_data = []
    for event in clock_events:
        # Convert to local timezone for display
        local_timestamp = timezone.localtime(event.timestamp)
        event_data.append({
            'employee_id': event.employee.id,
            'employee_name': f"{event.employee.given_name} {event.employee.surname}",
            'timestamp': local_timestamp,
            'event_type': event.event_type.name
        })
    
    # Create DataFrame
    if event_data:
        events_df = pd.DataFrame(event_data)
    else:
        events_df = pd.DataFrame(columns=['employee_id', 'employee_name', 'timestamp', 'event_type'])
    
    # Convert all employees to DataFrame for reference
    employee_data = []
    for emp in all_employees:
        employee_data.append({
            'employee_id': emp.id,
            'employee_name': f"{emp.given_name} {emp.surname}"
        })
    
    all_employees_df = pd.DataFrame(employee_data)
    
    return all_employees_df, events_df


@app.cell
def process_attendance_data(events_df, all_employees_df, pd):
    # Get the latest event for each employee
    if not events_df.empty:
        # Sort by timestamp to ensure the latest event is selected
        events_df = events_df.sort_values('timestamp')
        
        # Get the latest event for each employee
        latest_events = events_df.groupby('employee_id').last().reset_index()
        
        # Identify employees who are clocked in
        clocked_in_df = latest_events[latest_events['event_type'] == 'Clock In']
        
        # Get the IDs of clocked in employees
        clocked_in_ids = set(clocked_in_df['employee_id'])
        
        # Identify employees who are not clocked in
        not_clocked_in_df = all_employees_df[~all_employees_df['employee_id'].isin(clocked_in_ids)]
    else:
        # If no events, all employees are not clocked in
        clocked_in_df = pd.DataFrame(columns=['employee_id', 'employee_name', 'timestamp', 'event_type'])
        not_clocked_in_df = all_employees_df
    
    # Count employees in each category
    total_employees = len(all_employees_df)
    clocked_in_count = len(clocked_in_df)
    not_clocked_in_count = total_employees - clocked_in_count
    
    return clocked_in_df, not_clocked_in_df, total_employees, clocked_in_count, not_clocked_in_count


@app.cell
def display_summary(mo, clocked_in_count, not_clocked_in_count, total_employees, date_input):
    # Create a summary with the counts
    mo.md(f"# Daily Attendance Dashboard for {date_input.value.strftime('%A, %B %d, %Y')}")
    
    # Create a layout with three columns for the counts
    mo.hstack([
        mo.vstack([
            mo.md("### Total Employees"),
            mo.md(f"## {total_employees}")
        ]),
        mo.vstack([
            mo.md("### Currently Clocked In"),
            mo.md(f"## {clocked_in_count}")
        ]),
        mo.vstack([
            mo.md("### Not Clocked In"),
            mo.md(f"## {not_clocked_in_count}")
        ])
    ])
    
    # Create a donut chart visualization
    fig = go.Figure(data=[
        go.Pie(
            values=[clocked_in_count, not_clocked_in_count],
            labels=['Clocked In', 'Not Clocked In'],
            hole=.5,
            marker_colors=['#2ECC71', '#E74C3C']
        )
    ])
    
    fig.update_layout(
        title_text='Attendance Status',
        showlegend=True
    )
    
    return fig


@app.cell
def display_clocked_in_employees(mo, clocked_in_df):
    mo.md("## Employees Currently Clocked In")
    
    if not clocked_in_df.empty:
        # Format timestamp for display
        clocked_in_df['clock_in_time'] = clocked_in_df['timestamp'].dt.strftime('%I:%M %p')
        
        # Create a table with the clocked in employees
        table_data = clocked_in_df[['employee_name', 'clock_in_time']].rename(
            columns={'employee_name': 'Employee Name', 'clock_in_time': 'Clock In Time'}
        )
        
        # Sort by clock in time
        table_data = table_data.sort_values('Clock In Time')
        
        # Display the table
        mo.ui.table(table_data)
    else:
        mo.md("*No employees clocked in for the selected date.*")
    return


@app.cell
def display_not_clocked_in_employees(mo, not_clocked_in_df):
    mo.md("## Employees Not Clocked In")
    
    if not not_clocked_in_df.empty:
        # Create a table with the employees who are not clocked in
        table_data = not_clocked_in_df[['employee_name']].rename(
            columns={'employee_name': 'Employee Name'}
        )
        
        # Sort alphabetically
        table_data = table_data.sort_values('Employee Name')
        
        # Display the table
        mo.ui.table(table_data)
    else:
        mo.md("*All employees are clocked in for the selected date.*")
    return


if __name__ == "__main__":
    app.run() 