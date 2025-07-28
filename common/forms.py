from django import forms
from django.contrib.auth.models import User
from .models import AttendanceRecord, Employee
import datetime

class AttendanceRecordForm(forms.ModelForm):
    """Form for recording daily attendance"""
    LUNCH_TIME_CHOICES = [
        ('12:00', '12:00 PM'),
        ('12:30', '12:30 PM'),
        ('13:00', '1:00 PM'),
    ]
    lunch_time = forms.ChoiceField(
        required=False,
        choices=[('', '---------')] + LUNCH_TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Lunch Time"
    )
    class Meta:
        model = AttendanceRecord
        fields = [
            'employee', 'date', 'lunch_time', 'left_lunch_on_time',
            'returned_on_time_after_lunch', 'returned_after_lunch',
            'standup_attendance', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True)
        for field_name, field in self.fields.items():
            if field_name not in ['date', 'lunch_time', 'notes']:
                field.widget.attrs.update({'class': 'form-select'})
    def clean_lunch_time(self):
        value = self.cleaned_data.get('lunch_time')
        if not value:
            return None
        try:
            return datetime.datetime.strptime(value, "%H:%M").time()
        except Exception:
            return None


class BulkAttendanceForm(forms.Form):
    """Form for bulk attendance entry"""
    
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="Select the date for attendance records"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically add fields for each active employee
        employees = Employee.objects.filter(is_active=True).order_by('surname', 'given_name')
        
        for employee in employees:
            # Stand-up attendance
            self.fields[f'standup_{employee.id}'] = forms.ChoiceField(
                choices=[('', '---------')] + list(AttendanceRecord.ATTENDANCE_CHOICES),
                required=False,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label=f"{employee.surname}, {employee.given_name} - Stand-up"
            )
            
            # Lunch time
            self.fields[f'lunch_time_{employee.id}'] = forms.TimeField(
                required=False,
                widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
                label=f"{employee.surname}, {employee.given_name} - Lunch Time"
            )
            
            # Left lunch on time
            self.fields[f'left_lunch_{employee.id}'] = forms.ChoiceField(
                choices=[('', '---------')] + list(AttendanceRecord.ATTENDANCE_CHOICES),
                required=False,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label=f"{employee.surname}, {employee.given_name} - Left Lunch On Time"
            )
            
            # Returned on time after lunch
            self.fields[f'returned_on_time_{employee.id}'] = forms.ChoiceField(
                choices=[('', '---------')] + list(AttendanceRecord.ATTENDANCE_CHOICES),
                required=False,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label=f"{employee.surname}, {employee.given_name} - Returned On Time"
            )
            
            # Returned after lunch
            self.fields[f'returned_after_{employee.id}'] = forms.ChoiceField(
                choices=[('', '---------')] + list(AttendanceRecord.ATTENDANCE_CHOICES),
                required=False,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label=f"{employee.surname}, {employee.given_name} - Returned After Lunch"
            )
            
            # Note: Departure time is automatically pulled from clock-in system


class ProgressiveEntryForm(forms.Form):
    """Form for progressive attendance entry throughout the day"""
    
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Employee"
    )
    
    standup_attendance = forms.ChoiceField(
        choices=[('', '---------')] + list(AttendanceRecord.ATTENDANCE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Stand-up Meeting"
    )
    
    left_lunch_on_time = forms.ChoiceField(
        choices=[('', '---------')] + list(AttendanceRecord.ATTENDANCE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Left Lunch On Time"
    )
    
    returned_on_time_after_lunch = forms.ChoiceField(
        choices=[('', '---------')] + list(AttendanceRecord.ATTENDANCE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Returned On Time After Lunch"
    )
    
    returned_after_lunch = forms.ChoiceField(
        choices=[('', '---------')] + list(AttendanceRecord.ATTENDANCE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Returned After Lunch"
    )
    
    LUNCH_TIME_CHOICES = [
        ('12:00', '12:00 PM'),
        ('12:30', '12:30 PM'),
        ('13:00', '1:00 PM'),
    ]
    lunch_time = forms.ChoiceField(
        required=False,
        choices=[('', '---------')] + LUNCH_TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Lunch Time"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        label="Notes"
    )

    def clean_lunch_time(self):
        value = self.cleaned_data.get('lunch_time')
        if not value:
            return None
        try:
            return datetime.datetime.strptime(value, "%H:%M").time()
        except Exception:
            return None


class AttendanceFilterForm(forms.Form):
    """Form for filtering attendance records"""
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date"
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date"
    )
    
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True),
        required=False,
        empty_label="All Employees",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Employee"
    )
    
    has_issues = forms.ChoiceField(
        choices=[
            ('', 'All Records'),
            ('yes', 'Has Issues'),
            ('no', 'No Issues'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Issue Status"
    ) 


class HistoricalProgressiveEntryForm(forms.Form):
    """Form for historical progressive attendance entry - modifying previous days"""
    
    date_from = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date",
        help_text="Start date for the period you want to modify"
    )
    
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date",
        help_text="End date for the period you want to modify"
    )
    
    department = forms.ChoiceField(
        choices=[
            ('Digitization Tech', 'Digitization Tech'),
            ('Material Retriever', 'Material Retriever'),
            ('Custodian', 'Custodian'),
            ('Con', 'Con'),
            ('All Departments', 'All Departments'),
        ],
        initial='Digitization Tech',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Department",
        help_text="Select department to modify attendance records for employees in that department"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError("From date cannot be after To date")
        
        # Limit date range to prevent performance issues
        if date_from and date_to:
            date_diff = (date_to - date_from).days
            if date_diff > 31:  # Limit to 31 days
                raise forms.ValidationError("Date range cannot exceed 31 days")
        
        return cleaned_data


class BulkHistoricalUpdateForm(forms.Form):
    """Form for bulk updating historical attendance records"""
    
    field_to_update = forms.ChoiceField(
        choices=[
            ('standup_attendance', 'Stand-up Meeting Attendance'),
            ('left_lunch_on_time', 'Left Lunch On Time'),
            ('returned_on_time_after_lunch', 'Returned On Time After Lunch'),
            ('returned_after_lunch', 'Returned After Lunch'),
            ('lunch_time', 'Lunch Time'),
            ('notes', 'Notes'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Field to Update"
    )
    
    new_value = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="New Value",
        help_text="Leave blank to clear the field"
    )
    
    LUNCH_TIME_CHOICES = [
        ('12:00', '12:00 PM'),
        ('12:30', '12:30 PM'),
        ('13:00', '1:00 PM'),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make the form dynamic based on field selection
        self.fields['new_value'].widget.attrs['placeholder'] = 'Enter new value or leave blank to clear'
    
    def clean(self):
        cleaned_data = super().clean()
        field_to_update = cleaned_data.get('field_to_update')
        new_value = cleaned_data.get('new_value')
        
        # Validate lunch time format if updating lunch_time
        if field_to_update == 'lunch_time' and new_value:
            try:
                from datetime import datetime
                datetime.strptime(new_value, "%H:%M")
            except ValueError:
                raise forms.ValidationError("Lunch time must be in HH:MM format (e.g., 12:30)")
        
        return cleaned_data 