"""
Management command to pre-compute reports for performance optimization.

Usage:
    python manage.py precompute_reports --daily
    python manage.py precompute_reports --weekly
    python manage.py precompute_reports --all
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import date, timedelta

from common.services.report_precomputation_service import report_precomputer
from common.services.caching_service import enhanced_cache


class Command(BaseCommand):
    help = 'Pre-compute reports to improve performance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--daily',
            action='store_true',
            help='Pre-compute daily reports',
        )
        parser.add_argument(
            '--weekly',
            action='store_true',
            help='Pre-compute weekly reports',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Pre-compute all reports',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Target date (YYYY-MM-DD format, defaults to today)',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up expired cache entries',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show pre-computation status',
        )
    
    def handle(self, *args, **options):
        if not any([options['daily'], options['weekly'], options['all'], options['cleanup'], options['status']]):
            raise CommandError('Please specify at least one action: --daily, --weekly, --all, --cleanup, or --status')
        
        # Parse target date
        target_date = None
        if options['date']:
            try:
                target_date = date.fromisoformat(options['date'])
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD')
        else:
            target_date = timezone.now().date()
        
        # Show status
        if options['status']:
            self.show_status()
        
        # Cleanup expired cache
        if options['cleanup']:
            self.cleanup_cache()
        
        # Pre-compute reports
        if options['daily'] or options['all']:
            self.precompute_daily_reports(target_date)
        
        if options['weekly'] or options['all']:
            self.precompute_weekly_reports(target_date)
        
        # Show final status
        if any([options['daily'], options['weekly'], options['all']]):
            self.show_status()
    
    def precompute_daily_reports(self, target_date: date):
        """Pre-compute daily reports."""
        self.stdout.write(
            self.style.SUCCESS(f'Starting daily report pre-computation for {target_date}')
        )
        
        try:
            results = report_precomputer.precompute_daily_reports(target_date)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Daily reports pre-computed successfully:\n'
                    f'  - Department summaries: {results["department_summaries"]}\n'
                    f'  - Employee statuses: {results["employee_statuses"]}\n'
                    f'  - Attendance records: {results["attendance_records"]}\n'
                    f'  - System metrics: {results["system_metrics"]}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to pre-compute daily reports: {e}')
            )
    
    def precompute_weekly_reports(self, target_date: date):
        """Pre-compute weekly reports."""
        self.stdout.write(
            self.style.SUCCESS(f'Starting weekly report pre-computation for week of {target_date}')
        )
        
        try:
            results = report_precomputer.precompute_weekly_reports(target_date)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Weekly reports pre-computed successfully:\n'
                    f'  - Weekly summaries: {results["weekly_summaries"]}\n'
                    f'  - Trend analysis: {results["trend_analysis"]}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to pre-compute weekly reports: {e}')
            )
    
    def cleanup_cache(self):
        """Clean up expired cache entries."""
        self.stdout.write('Cleaning up expired cache entries...')
        
        try:
            cleaned_count = enhanced_cache.cleanup_expired_cache()
            self.stdout.write(
                self.style.SUCCESS(f'Cleaned up {cleaned_count} expired cache entries')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to cleanup cache: {e}')
            )
    
    def show_status(self):
        """Show pre-computation and cache status."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('PRE-COMPUTATION STATUS')
        self.stdout.write('='*50)
        
        # Show pre-computation status
        try:
            status = report_precomputer.get_precomputation_status()
            
            self.stdout.write('\n📊 Pre-computed Reports:')
            self.stdout.write(f'  Daily reports (today): {"✅" if status["daily_reports"]["today"] else "❌"}')
            self.stdout.write(f'  Daily reports (yesterday): {"✅" if status["daily_reports"]["yesterday"] else "❌"}')
            self.stdout.write(f'  Weekly reports (current week): {"✅" if status["weekly_reports"]["current_week"] else "❌"}')
            self.stdout.write(f'  Last updated: {status["last_updated"]}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to get pre-computation status: {e}')
            )
        
        # Show cache status
        try:
            cache_stats = enhanced_cache.get_cache_stats()
            
            self.stdout.write('\n💾 Cache Status:')
            self.stdout.write(f'  Total entries: {cache_stats["total_entries"]}')
            self.stdout.write(f'  Valid entries: {cache_stats["valid_entries"]}')
            self.stdout.write(f'  Expired entries: {cache_stats["expired_entries"]}')
            self.stdout.write(f'  Cache hit rate: {cache_stats["cache_hit_rate"]}%')
            self.stdout.write(f'  Cache health: {cache_stats["cache_health"]}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to get cache stats: {e}')
            )
        
        self.stdout.write('\n' + '='*50)
