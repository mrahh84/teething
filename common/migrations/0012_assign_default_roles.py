from django.db import migrations


def assign_default_roles(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserRole = apps.get_model('common', 'UserRole')
    
    # Assign admin role to superusers
    for user in User.objects.filter(is_superuser=True):
        UserRole.objects.get_or_create(user=user, defaults={'role': 'admin'})
    
    # Assign security role to regular users (default)
    for user in User.objects.filter(is_superuser=False):
        UserRole.objects.get_or_create(user=user, defaults={'role': 'security'})


def reverse_assign_default_roles(apps, schema_editor):
    UserRole = apps.get_model('common', 'UserRole')
    UserRole.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('common', '0011_userrole_and_more'),
    ]
    
    operations = [
        migrations.RunPython(assign_default_roles, reverse_assign_default_roles),
    ] 