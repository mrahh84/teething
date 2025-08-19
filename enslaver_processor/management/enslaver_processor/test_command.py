from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'A simple test command'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Test command works!'))
