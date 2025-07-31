"""
Check the clock-in status of all employees in the system.
Run this script with: python manage.py shell < scripts/check_employee_status.py
"""

from common.models import Employee

print("\nEmployee Clock-In Status Report")
print("=" * 70)
print(f"{'Name':<30} {'Card':<15} {'Status':<15} {'Last Event Time'}")
print("-" * 70)

clocked_in_count = 0
for employee in Employee.objects.all().order_by('surname', 'given_name'):
    name = f"{employee.given_name} {employee.surname}"
    card = employee.card_number.designation if employee.card_number else "No Card"
    
    is_clocked_in = employee.is_clocked_in()
    status = "Clocked In" if is_clocked_in else "Clocked Out"
    
    if is_clocked_in:
        clocked_in_count += 1
        
    if employee.last_clockinout_time:
        from django.utils import timezone
        local_time = timezone.localtime(employee.last_clockinout_time)
        last_time = local_time.strftime("%Y-%m-%d %H:%M")
    else:
        last_time = "Never"
    
    print(f"{name:<30} {card:<15} {status:<15} {last_time}")

print("=" * 70)
print(f"Total employees: {Employee.objects.count()}")
print(f"Currently clocked in: {clocked_in_count}") 