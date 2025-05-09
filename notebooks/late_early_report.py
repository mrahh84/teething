import marimo as mo
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go

__generated_with = "0.13.6"
app = mo.App(width="medium")


@app.cell
def imports():
    import marimo as mo
    import pandas as pd
    import datetime
    import plotly.express as px
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
def create_ui_elements(mo):
    mo.md("# Late Arrival and Early Departure Report")
    
    # Create date range picker
    today = datetime.date.today()
    date_range = mo.ui.date_range(
        start=today - datetime.timedelta(days=30),
        end=today,
        label="Select Date Range"
    )
    
    # Create sliders for threshold settings
    late_threshold = mo.ui.slider(
        min=1,
        max=60,
        value=15,
        label="Late Arrival Threshold (minutes)"
    )
    
    early_threshold = mo.ui.slider(
        min=1,
        max=60,
        value=15,
        label="Early Departure Threshold (minutes)"
    )
    
    # Create input for standard start and end time
    start_time = mo.ui.text(
        value="09:00",
        label="Standard Start Time (HH:MM)",
        placeholder="09:00"
    )
    
    end_time = mo.ui.text(
        value="17:00",
        label="Standard End Time (HH:MM)",
        placeholder="17:00"
    )
    
    # Display the UI elements in a nice layout
    mo.hstack([date_range])
    mo.hstack([start_time, end_time])
    mo.hstack([late_threshold, early_threshold])
    
    return date_range, late_threshold, early_threshold, start_time, end_time


@app.cell
def load_attendance_data(Employee, Event, date_range, pd, timezone):
    # Get the date range
    start_date = date_range.start
    end_date = date_range.end
    
    # Convert to datetime objects for filtering
    start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
    end_datetime = datetime.datetime.combine(end_date, datetime.time.max)
    
    # Make timezone-aware if your Django settings use timezone support
    start_datetime = timezone.make_aware(start_datetime) if timezone.is_naive(start_datetime) else start_datetime
    end_datetime = timezone.make_aware(end_datetime) if timezone.is_naive(end_datetime) else end_datetime
    
    # Get all employees
    all_employees = Employee.objects.all()
    
    # Get all clock events for the date range
    clock_events = Event.objects.filter(
        timestamp__gte=start_datetime,
        timestamp__lt=end_datetime,
        event_type__name__in=["Clock In", "Clock Out"]
    ).select_related('employee', 'event_type')
    
    # Convert events to DataFrame
    event_data = []
    for event in clock_events:
        event_data.append({
            'employee_id': event.employee.id,
            'employee_name': f"{event.employee.given_name} {event.employee.surname}",
            'timestamp': event.timestamp,
            'event_type': event.event_type.name,
            'date': event.timestamp.date()
        })
    
    if event_data:
        events_df = pd.DataFrame(event_data)
    else:
        events_df = pd.DataFrame(columns=['employee_id', 'employee_name', 'timestamp', 'event_type', 'date'])
    
    # Convert employees to DataFrame
    employee_data = []
    for emp in all_employees:
        employee_data.append({
            'employee_id': emp.id,
            'employee_name': f"{emp.given_name} {emp.surname}"
        })
    
    all_employees_df = pd.DataFrame(employee_data)
    
    return events_df, all_employees_df


@app.cell
def process_late_early_data(events_df, late_threshold, early_threshold, start_time, end_time, datetime, pd):
    # If no events, return empty DataFrame
    if events_df.empty:
        late_early_df = pd.DataFrame(columns=[
            'employee_id', 'employee_name', 'date', 'event_type', 
            'actual_time', 'threshold_time', 'deviation_minutes'
        ])
        return late_early_df, 0, 0
    
    # Parse standard start and end times
    try:
        std_start_time = datetime.datetime.strptime(start_time.value, "%H:%M").time()
        std_end_time = datetime.datetime.strptime(end_time.value, "%H:%M").time()
    except ValueError:
        # Default times if parsing fails
        std_start_time = datetime.time(9, 0)
        std_end_time = datetime.time(17, 0)
    
    # Get the threshold values in minutes
    late_mins = late_threshold.value
    early_mins = early_threshold.value
    
    # Initialize lists for late arrivals and early departures
    late_early_records = []
    
    # Process events by employee and date
    for (employee_id, employee_name, date), day_emp_events in events_df.groupby(['employee_id', 'employee_name', 'date']):
        # Sort events by timestamp for the employee on this day
        day_emp_events = day_emp_events.sort_values('timestamp')
        
        # Get first clock in and last clock out for the day
        clock_ins = day_emp_events[day_emp_events['event_type'] == 'Clock In']
        clock_outs = day_emp_events[day_emp_events['event_type'] == 'Clock Out']
        
        if not clock_ins.empty:
            first_clock_in = clock_ins.iloc[0]
            clock_in_time = first_clock_in['timestamp'].time()
            
            # Check if it's a late arrival
            if clock_in_time > std_start_time:
                # Calculate how many minutes late
                std_start_dt = datetime.datetime.combine(date, std_start_time)
                actual_dt = datetime.datetime.combine(date, clock_in_time)
                minutes_late = (actual_dt - std_start_dt).total_seconds() / 60
                
                # Only record if it exceeds the threshold
                if minutes_late >= late_mins:
                    late_early_records.append({
                        'employee_id': employee_id,
                        'employee_name': employee_name,
                        'date': date,
                        'event_type': 'Late Arrival',
                        'actual_time': clock_in_time.strftime('%H:%M'),
                        'threshold_time': std_start_time.strftime('%H:%M'),
                        'deviation_minutes': int(minutes_late)
                    })
        
        if not clock_outs.empty:
            last_clock_out = clock_outs.iloc[-1]
            clock_out_time = last_clock_out['timestamp'].time()
            
            # Check if it's an early departure
            if clock_out_time < std_end_time:
                # Calculate how many minutes early
                std_end_dt = datetime.datetime.combine(date, std_end_time)
                actual_dt = datetime.datetime.combine(date, clock_out_time)
                minutes_early = (std_end_dt - actual_dt).total_seconds() / 60
                
                # Only record if it exceeds the threshold
                if minutes_early >= early_mins:
                    late_early_records.append({
                        'employee_id': employee_id,
                        'employee_name': employee_name,
                        'date': date,
                        'event_type': 'Early Departure',
                        'actual_time': clock_out_time.strftime('%H:%M'),
                        'threshold_time': std_end_time.strftime('%H:%M'),
                        'deviation_minutes': int(minutes_early)
                    })
    
    # Create DataFrame
    if late_early_records:
        late_early_df = pd.DataFrame(late_early_records)
    else:
        late_early_df = pd.DataFrame(columns=[
            'employee_id', 'employee_name', 'date', 'event_type', 
            'actual_time', 'threshold_time', 'deviation_minutes'
        ])
    
    # Count late arrivals and early departures
    late_count = sum(1 for record in late_early_records if record['event_type'] == 'Late Arrival')
    early_count = sum(1 for record in late_early_records if record['event_type'] == 'Early Departure')
    
    return late_early_df, late_count, early_count


@app.cell
def display_summary(late_count, early_count, late_threshold, early_threshold, mo, start_time, end_time):
    # Display summary header
    mo.md(f"## Summary")
    
    # Display the configuration
    mo.md(f"**Standard Hours:** {start_time.value} to {end_time.value}")
    mo.md(f"**Late Threshold:** {late_threshold.value} minutes")
    mo.md(f"**Early Threshold:** {early_threshold.value} minutes")
    
    # Display counts in a layout
    mo.hstack([
        mo.vstack([
            mo.md("### Late Arrivals"),
            mo.md(f"## {late_count}")
        ]),
        mo.vstack([
            mo.md("### Early Departures"),
            mo.md(f"## {early_count}")
        ])
    ])
    
    return


@app.cell
def display_late_early_table(late_early_df, mo):
    mo.md("## Detailed Records")
    
    if not late_early_df.empty:
        # Format the DataFrame for display
        display_df = late_early_df.copy()
        
        # Convert date to string
        display_df['date'] = display_df['date'].astype(str)
        
        # Rename columns
        display_df = display_df.rename(columns={
            'employee_name': 'Employee Name',
            'date': 'Date',
            'event_type': 'Event Type',
            'actual_time': 'Actual Time',
            'threshold_time': 'Standard Time',
            'deviation_minutes': 'Minutes'
        })
        
        # Remove employee_id column
        display_df = display_df.drop(columns=['employee_id'])
        
        # Display the table with sorting and filtering
        mo.ui.table(
            display_df,
            selection="single",
            pagination=True,
            width="100%"
        )
    else:
        mo.md("*No late arrivals or early departures found matching the criteria.*")
    
    return


@app.cell
def create_visualizations(late_early_df, mo, px):
    if not late_early_df.empty:
        mo.md("## Visualizations")
        
        # Create a copy of the dataframe for analysis
        analysis_df = late_early_df.copy()
        
        # Convert date to datetime for proper sorting/grouping
        analysis_df['date'] = pd.to_datetime(analysis_df['date'])
        
        # Group by date and event type
        daily_counts = analysis_df.groupby(['date', 'event_type']).size().reset_index(name='count')
        
        # Create line chart of events over time
        fig = px.line(
            daily_counts,
            x='date',
            y='count',
            color='event_type',
            markers=True,
            labels={'date': 'Date', 'count': 'Count', 'event_type': 'Event Type'},
            title='Daily Late/Early Events'
        )
        
        # Employee analysis
        employee_counts = analysis_df.groupby(['employee_name', 'event_type']).size().reset_index(name='count')
        top_employees = employee_counts.sort_values('count', ascending=False).head(10)
        
        fig2 = px.bar(
            top_employees,
            x='employee_name',
            y='count',
            color='event_type',
            barmode='group',
            labels={'employee_name': 'Employee', 'count': 'Count', 'event_type': 'Event Type'},
            title='Top Employees with Late/Early Events'
        )
        
        fig2.update_layout(xaxis_tickangle=-45)
        
        # Display charts
        mo.vstack([fig, fig2])
    
    return


if __name__ == "__main__":
    app.run() 