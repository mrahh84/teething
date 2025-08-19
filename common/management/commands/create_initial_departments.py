from django.core.management.base import BaseCommand
from common.models import Department


class Command(BaseCommand):
    help = 'Create initial departments for the system'

    def handle(self, *args, **options):
        departments_data = [
            {
                'name': 'Digitization Tech',
                'code': 'DIGITECH',
                'description': 'Digital technology and digitization department'
            },
            {
                'name': 'Repository and Conservation',
                'code': 'REPCONS',
                'description': 'Repository management and conservation services'
            },
            {
                'name': 'Main Security',
                'code': 'MAINSEC',
                'description': 'Main security and access control'
            },
            {
                'name': 'Administration',
                'code': 'ADMIN',
                'description': 'Administrative and management services'
            },
            {
                'name': 'IT Support',
                'code': 'ITSUPP',
                'description': 'Information technology support and maintenance'
            },
            {
                'name': 'Human Resources',
                'code': 'HR',
                'description': 'Human resources and personnel management'
            },
            {
                'name': 'Finance',
                'code': 'FINANCE',
                'description': 'Financial management and accounting'
            }
        ]

        created_count = 0
        for dept_data in departments_data:
            department, created = Department.objects.get_or_create(
                code=dept_data['code'],
                defaults={
                    'name': dept_data['name'],
                    'description': dept_data['description'],
                    'is_active': True
                }
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created department: {department.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Department already exists: {department.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} new departments')
        ) 