from django.core.management.base import BaseCommand
from django.core.cache import cache
from common.models import Employee, EventType, Location
from common.cache_utils import bulk_cache_employee_statuses, get_cached_event_types, get_cached_locations


class Command(BaseCommand):
    help = 'Warm up the cache with employee data for better performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            help='Force cache refresh even if data is already cached',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        if force:
            self.stdout.write(self.style.WARNING('Forcing cache refresh...'))
            cache.clear()
        
        self.stdout.write('Warming up cache...')
        
        # Cache event types and locations
        self.stdout.write('Caching event types and locations...')
        event_types = get_cached_event_types()
        locations = get_cached_locations()
        self.stdout.write(f'Cached {len(event_types)} event types and {len(locations)} locations')
        
        # Get all employee IDs
        employee_ids = list(Employee.objects.values_list('id', flat=True))
        self.stdout.write(f'Found {len(employee_ids)} employees')
        
        # Bulk cache employee statuses in batches
        batch_size = 50
        for i in range(0, len(employee_ids), batch_size):
            batch = employee_ids[i:i + batch_size]
            bulk_cache_employee_statuses(batch)
            self.stdout.write(f'Cached employee statuses for batch {i//batch_size + 1}/{(len(employee_ids) + batch_size - 1)//batch_size}')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully warmed cache for {len(employee_ids)} employees')) 