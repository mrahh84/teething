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
def create_ui_elements(Employee, mo):
    # Get all employees for the dropdown
    employees = Employee.objects.all().order_by('surname', 'given_name')
    
    # Create employee dropdown options
    employee_options = []
    for emp in employees:
        employee_options.append({
            'label': f"{emp.surname}, {emp.given_name}",
            'value': emp.id
        })
    
    # Create a dropdown for employee selection
    employee_dropdown = mo.ui.dropdown(
        options=employee_options,
        value=employee_options[0]['value'] if employee_options else None,
        label="Select Employee"
    )
    
    # Create a date range picker
    today = datetime.date.today()
    date_range = mo.ui.date_range(
        start=today - datetime.timedelta(days=30),
        end=today,
        label="Select Date Range"
    )
    
    # Display the UI elements
    mo.md("# Individual Employee Attendance History")
    mo.hstack([employee_dropdown, date_range])
    
    return employee_dropdown, date_range


@app.cell
def load_employee_data(Employee, employee_dropdown):
    # Get the selected employee
    selected_employee_id = employee_dropdown.value
    
    if selected_employee_id:
        employee = Employee.objects.get(id=selected_employee_id)
        employee_name = f"{employee.given_name} {employee.surname}"
    else:
        employee_name = "No employee selected"
        
    return employee_name


@app.cell
def load_attendance_data(Event, employee_dropdown, date_range, pd, timezone):
    # Get the selected employee ID and date range
    selected_employee_id = employee_dropdown.value
    start_date = date_range.start
    end_date = date_range.end
    
    # Convert to datetime objects for filtering
    start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
    end_datetime = datetime.datetime.combine(end_date, datetime.time.max)
    
    # Make timezone-aware if your Django settings use timezone support
    start_datetime = timezone.make_aware(start_datetime) if timezone.is_naive(start_datetime) else start_datetime
    end_datetime = timezone.make_aware(end_datetime) if timezone.is_naive(end_datetime) else end_datetime
    
    # Get attendance events for the selected employee and date range
    events = Event.objects.filter(
        employee_id=selected_employee_id,
        timestamp__range=(start_datetime, end_datetime)
    ).select_related('event_type', 'location').order_by('timestamp')
    
    # Convert to pandas DataFrame
    event_data = []
    for event in events:
        # Convert to local timezone for display
        local_timestamp = timezone.localtime(event.timestamp)
        event_data.append({
            'date': local_timestamp.date(),
            'timestamp': local_timestamp,
            'event_type': event.event_type.name,
            'location': event.location.name
        })
    
    if event_data:
        events_df = pd.DataFrame(event_data)
    else:
        events_df = pd.DataFrame(columns=['date', 'timestamp', 'event_type', 'location'])
    
    return events_df


@app.cell
def calculate_hours_worked(events_df, pd, datetime):
    # If the events DataFrame is empty, return empty DataFrames
    if events_df.empty:
        daily_hours_df = pd.DataFrame(columns=['date', 'hours_worked'])
        total_hours = 0
        return daily_hours_df, total_hours
    
    # Filter to only clock in/out events
    clock_events = events_df[events_df['event_type'].isin(['Clock In', 'Clock Out'])].copy()
    
    if clock_events.empty:
        daily_hours_df = pd.DataFrame(columns=['date', 'hours_worked'])
        total_hours = 0
        return daily_hours_df, total_hours
    
    # Sort events by timestamp
    clock_events = clock_events.sort_values('timestamp')
    
    # Group by date
    clock_events['date'] = clock_events['timestamp'].dt.date
    
    # Initialize variables for calculating hours
    daily_hours = {}
    total_hours = 0
    current_clock_in = None
    
    # Loop through events by date
    for date, day_events in clock_events.groupby('date'):
        day_hours = 0
        day_records = day_events.to_dict('records')
        
        # Process each event for the day
        for i, event in enumerate(day_records):
            if event['event_type'] == 'Clock In':
                current_clock_in = event['timestamp']
            elif event['event_type'] == 'Clock Out' and current_clock_in is not None:
                # Calculate duration between clock in and clock out
                duration = (event['timestamp'] - current_clock_in).total_seconds() / 3600  # hours
                day_hours += duration
                current_clock_in = None
        
        # Store hours for the day
        daily_hours[date] = day_hours
        total_hours += day_hours
    
    # Convert to DataFrame
    daily_hours_df = pd.DataFrame(
        [{'date': date, 'hours_worked': hours} for date, hours in daily_hours.items()]
    )
    
    # Sort by date
    daily_hours_df = daily_hours_df.sort_values('date')
    
    return daily_hours_df, total_hours


@app.cell
def display_employee_info(mo, employee_name, date_range, total_hours):
    # Display employee name and date range
    mo.md(f"## {employee_name}")
    mo.md(f"**Period:** {date_range.start.strftime('%Y-%m-%d')} to {date_range.end.strftime('%Y-%m-%d')}")
    
    # Display total hours worked
    mo.md(f"**Total Hours Worked:** {total_hours:.2f} hours")
    
    return


@app.cell
def display_raw_events(events_df, mo):
    mo.md("## Raw Attendance Records")
    
    if not events_df.empty:
        # Format the DataFrame for display
        display_df = events_df.copy()
        
        # Format timestamp
        display_df['Time'] = display_df['timestamp'].dt.strftime('%I:%M %p')
        display_df['Date'] = display_df['timestamp'].dt.strftime('%Y-%m-%d')
        
        # Select and rename columns for display
        table_data = display_df[['Date', 'Time', 'event_type', 'location']].rename(
            columns={'event_type': 'Event Type', 'location': 'Location'}
        )
        
        # Display the table
        mo.ui.table(table_data)
    else:
        mo.md("*No attendance records found for the selected period.*")
    
    return


@app.cell
def create_daily_hours_chart(daily_hours_df, mo, px):
    mo.md("## Daily Hours Worked")
    
    if not daily_hours_df.empty:
        # Create a bar chart of daily hours
        fig = px.bar(
            daily_hours_df,
            x='date',
            y='hours_worked',
            labels={'date': 'Date', 'hours_worked': 'Hours Worked'},
            title='Daily Hours Worked'
        )
        
        # Customize the layout
        fig.update_layout(
            xaxis_title='Date',
            yaxis_title='Hours',
            height=400
        )
        
        return fig
    else:
        mo.md("*No hours data available for the selected period.*")
        return None


if __name__ == "__main__":
    app.run() 