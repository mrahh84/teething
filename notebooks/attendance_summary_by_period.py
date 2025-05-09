import marimo as mo
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
from dateutil.relativedelta import relativedelta

__generated_with = "0.13.6"
app = mo.App(width="medium")


@app.cell
def imports():
    import marimo as mo
    import pandas as pd
    import datetime
    import plotly.express as px
    import plotly.graph_objects as go
    from dateutil.relativedelta import relativedelta
    import os
    import sys
    import django
    return django, datetime, go, mo, os, pd, px, relativedelta, sys


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
    mo.md("# Attendance Summary by Period")
    
    # Create a radio button group for period selection
    period_radio = mo.ui.radio(
        options=[
            {"label": "Daily", "value": "day"},
            {"label": "Weekly", "value": "week"},
            {"label": "Monthly", "value": "month"},
        ],
        value="day",
        label="Select Period"
    )
    
    # Create date picker for the start date
    today = datetime.date.today()
    date_picker = mo.ui.date(
        value=today - datetime.timedelta(days=30),
        label="Select Start Date",
        min=today - datetime.timedelta(days=365),
        max=today
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
    mo.hstack([period_radio, date_picker])
    mo.hstack([start_time, end_time])
    
    return period_radio, date_picker, start_time, end_time


@app.cell
def load_attendance_data(Employee, Event, date_picker, period_radio, pd, relativedelta, timezone):
    # Get the selected period and start date
    period = period_radio.value
    start_date = date_picker.value
    
    # Calculate the end date based on the period
    if period == "day":
        end_date = start_date + datetime.timedelta(days=1)
    elif period == "week":
        end_date = start_date + datetime.timedelta(weeks=1)
    elif period == "month":
        end_date = start_date + relativedelta(months=1)
    
    # Convert to datetime objects for filtering
    start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
    end_datetime = datetime.datetime.combine(end_date, datetime.time.min)
    
    # Make timezone-aware if your Django settings use timezone support
    start_datetime = timezone.make_aware(start_datetime) if timezone.is_naive(start_datetime) else start_datetime
    end_datetime = timezone.make_aware(end_datetime) if timezone.is_naive(end_datetime) else end_datetime
    
    # Get all employees
    all_employees = Employee.objects.all()
    
    # Get all clock events for the selected period
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
    
    return events_df, all_employees_df, start_date, end_date, period


@app.cell
def process_attendance_data(all_employees_df, events_df, pd, start_time, end_time, datetime):
    # If no events, return empty DataFrame
    if events_df.empty:
        summary_df = pd.DataFrame(columns=[
            'employee_id', 'employee_name', 'total_hours', 'late_arrivals', 
            'early_departures', 'missing_punches'
        ])
        return summary_df, 0, 0, 0, 0
    
    # Parse standard start and end times
    try:
        std_start_time = datetime.datetime.strptime(start_time.value, "%H:%M").time()
        std_end_time = datetime.datetime.strptime(end_time.value, "%H:%M").time()
    except ValueError:
        # Default times if parsing fails
        std_start_time = datetime.time(9, 0)
        std_end_time = datetime.time(17, 0)
    
    # Sort events by timestamp
    events_df = events_df.sort_values(['employee_id', 'date', 'timestamp'])
    
    # Initialize summary data
    summary_data = []
    
    # Track overall statistics
    total_late_arrivals = 0
    total_early_departures = 0
    total_missing_punches = 0
    company_total_hours = 0
    
    # Process each employee
    for employee_id, emp_name in zip(all_employees_df['employee_id'], all_employees_df['employee_name']):
        emp_events = events_df[events_df['employee_id'] == employee_id]
        
        if emp_events.empty:
            # Employee has no events in the period
            summary_data.append({
                'employee_id': employee_id,
                'employee_name': emp_name,
                'total_hours': 0,
                'late_arrivals': 0,
                'early_departures': 0,
                'missing_punches': 0
            })
            continue
        
        total_hours = 0
        late_arrivals = 0
        early_departures = 0
        missing_punches = 0
        
        # Group events by date
        for date, day_events in emp_events.groupby('date'):
            day_events_list = day_events.sort_values('timestamp').to_dict('records')
            
            # Check for clock in/out pairs and calculate hours
            has_clock_in = False
            has_clock_out = False
            clock_in_time = None
            
            for event in day_events_list:
                if event['event_type'] == 'Clock In':
                    has_clock_in = True
                    clock_in_time = event['timestamp']
                    
                    # Check if late arrival
                    event_time = clock_in_time.time()
                    if event_time > std_start_time:
                        late_arrivals += 1
                        
                elif event['event_type'] == 'Clock Out':
                    has_clock_out = True
                    
                    # Check if early departure
                    event_time = event['timestamp'].time()
                    if event_time < std_end_time:
                        early_departures += 1
                    
                    # Calculate hours if we have a matching clock in
                    if clock_in_time is not None:
                        duration = (event['timestamp'] - clock_in_time).total_seconds() / 3600  # hours
                        total_hours += duration
                        clock_in_time = None
            
            # Check for missing punches
            if has_clock_in != has_clock_out:
                missing_punches += 1
        
        # Add to summary data
        summary_data.append({
            'employee_id': employee_id,
            'employee_name': emp_name,
            'total_hours': total_hours,
            'late_arrivals': late_arrivals,
            'early_departures': early_departures,
            'missing_punches': missing_punches
        })
        
        # Update company totals
        total_late_arrivals += late_arrivals
        total_early_departures += early_departures
        total_missing_punches += missing_punches
        company_total_hours += total_hours
    
    # Create summary DataFrame
    summary_df = pd.DataFrame(summary_data)
    
    return summary_df, company_total_hours, total_late_arrivals, total_early_departures, total_missing_punches


@app.cell
def display_summary(mo, period, period_radio, start_date, end_date, summary_df, 
                 company_total_hours, total_late_arrivals, total_early_departures, 
                 total_missing_punches, all_employees_df):
    # Period formatting
    period_name = {
        "day": "Daily",
        "week": "Weekly",
        "month": "Monthly"
    }[period_radio.value]
    
    # Format dates for display
    period_display = period_name
    period_dates = f"{start_date.strftime('%Y-%m-%d')} to {(end_date - datetime.timedelta(days=1)).strftime('%Y-%m-%d')}"
    
    # Display summary header
    mo.md(f"# {period_name} Attendance Summary")
    mo.md(f"**Period:** {period_dates}")
    
    # Create company statistics
    avg_hours = company_total_hours / len(all_employees_df) if len(all_employees_df) > 0 else 0
    
    # Create a statistics layout
    mo.hstack([
        mo.vstack([
            mo.md("### Avg Hours/Employee"),
            mo.md(f"## {avg_hours:.2f}")
        ]),
        mo.vstack([
            mo.md("### Late Arrivals"),
            mo.md(f"## {total_late_arrivals}")
        ]),
        mo.vstack([
            mo.md("### Early Departures"),
            mo.md(f"## {total_early_departures}")
        ]),
        mo.vstack([
            mo.md("### Missing Punches"),
            mo.md(f"## {total_missing_punches}")
        ])
    ])
    
    return


@app.cell
def display_employee_summary_table(mo, summary_df):
    mo.md("## Employee Summary")
    
    if not summary_df.empty:
        # Format the DataFrame for display
        display_df = summary_df.copy()
        
        # Round hours to 2 decimal places
        display_df['total_hours'] = display_df['total_hours'].round(2)
        
        # Rename columns
        display_df = display_df.rename(columns={
            'employee_name': 'Employee Name',
            'total_hours': 'Total Hours',
            'late_arrivals': 'Late Arrivals',
            'early_departures': 'Early Departures',
            'missing_punches': 'Missing Punches'
        })
        
        # Remove employee_id column
        display_df = display_df.drop(columns=['employee_id'])
        
        # Display the table with sorting
        mo.ui.table(
            display_df,
            selection="single",
            pagination=True,
            width="100%"
        )
    else:
        mo.md("*No attendance data available for the selected period.*")
    
    return


@app.cell
def create_visualizations(mo, px, summary_df):
    if not summary_df.empty:
        mo.md("## Visualizations")
        
        # Top employees by hours worked
        top_hours_df = summary_df.sort_values('total_hours', ascending=False).head(10)
        
        fig_hours = px.bar(
            top_hours_df,
            x='employee_name',
            y='total_hours',
            labels={'employee_name': 'Employee', 'total_hours': 'Hours Worked'},
            title='Top 10 Employees by Hours Worked'
        )
        
        fig_hours.update_layout(xaxis_tickangle=-45)
        
        # Employees with most late arrivals
        top_late_df = summary_df.sort_values('late_arrivals', ascending=False).head(10)
        
        fig_late = px.bar(
            top_late_df,
            x='employee_name',
            y='late_arrivals',
            labels={'employee_name': 'Employee', 'late_arrivals': 'Late Arrivals'},
            title='Top 10 Employees by Late Arrivals'
        )
        
        fig_late.update_layout(xaxis_tickangle=-45)
        
        # Display charts in a layout
        mo.hstack([fig_hours, fig_late])
    
    return


if __name__ == "__main__":
    app.run() 