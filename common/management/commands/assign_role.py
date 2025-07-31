from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from common.models import UserRole


class Command(BaseCommand):
    help = 'Assign role to user'
    
    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('role', type=str, choices=['security', 'attendance', 'reporting', 'admin'])
    
    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options['username'])
            role, created = UserRole.objects.get_or_create(user=user)
            role.role = options['role']
            role.save()
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created role '{options['role']}' for user '{options['username']}'")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Updated role to '{options['role']}' for user '{options['username']}'")
                )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"User '{options['username']}' does not exist")
            ) 