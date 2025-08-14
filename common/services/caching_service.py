"""
Enhanced Caching Service for Phase 2 Performance Optimization

Implements multi-level caching strategy with intelligent cache invalidation
and report pre-computation capabilities.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q

from ..models import AnalyticsCache, User

logger = logging.getLogger(__name__)


class EnhancedCachingService:
    """Enhanced caching service with multi-level caching strategy."""
    
    def __init__(self):
        self.cache_timeouts = {
            'daily_summary': 3600,      # 1 hour
            'employee_status': 300,      # 5 minutes
            'department_stats': 1800,    # 30 minutes
            'comprehensive_report': 7200, # 2 hours
            'attendance_heatmap': 1800,  # 30 minutes
            'employee_analytics': 3600,  # 1 hour
            'location_analytics': 1800,  # 30 minutes
            'system_performance': 300,   # 5 minutes
        }
    
    def get_cached_report(self, report_key: str, user_id: int = None) -> Optional[Dict[str, Any]]:
        """
        Get cached report data with multi-level fallback.
        
        Args:
            report_key: The report identifier
            user_id: Optional user ID for user-specific caching
            
        Returns:
            Cached data or None if not found
        """
        # Level 1: Try user-specific cache first
        if user_id:
            user_key = f"{report_key}:user:{user_id}"
            cached = cache.get(user_key)
            if cached:
                logger.debug(f"User-specific cache hit for {user_key}")
                return cached
        
        # Level 2: Try general cache
        general_key = f"report:{report_key}"
        cached = cache.get(general_key)
        if cached:
            logger.debug(f"General cache hit for {general_key}")
            return cached
        
        # Level 3: Try database cache
        try:
            cache_obj = AnalyticsCache.objects.get(
                cache_key=report_key,
                expires_at__gt=timezone.now()
            )
            logger.debug(f"Database cache hit for {report_key}")
            
            # Also update the Django cache for faster future access
            cache.set(general_key, cache_obj.data, self.cache_timeouts.get(report_key, 3600))
            
            return cache_obj.data
        except AnalyticsCache.DoesNotExist:
            logger.debug(f"Cache miss for {report_key}")
            return None
    
    def cache_report(self, report_key: str, data: Dict[str, Any], 
                    user_id: int = None, cache_type: str = 'general') -> bool:
        """
        Cache report data at multiple levels.
        
        Args:
            report_key: The report identifier
            data: The data to cache
            user_id: Optional user ID for user-specific caching
            cache_type: Type of cache for database storage
            
        Returns:
            True if caching was successful
        """
        try:
            timeout = self.cache_timeouts.get(cache_type, 3600)
            
            # Level 1: Cache general version
            general_key = f"report:{report_key}"
            cache.set(general_key, data, timeout)
            
            # Level 2: Cache user-specific version if needed
            if user_id:
                user_key = f"{report_key}:user:{user_id}"
                cache.set(user_key, data, timeout)
            
            # Level 3: Store in database for persistence
            AnalyticsCache.objects.update_or_create(
                cache_key=report_key,
                defaults={
                    'data': data,
                    'expires_at': timezone.now() + timedelta(seconds=timeout),
                    'cache_type': cache_type,
                    'user_specific': user_id is not None,
                    'user_id': user_id
                }
            )
            
            logger.info(f"Successfully cached {report_key} with timeout {timeout}s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache report {report_key}: {e}")
            return False
    
    def invalidate_cache(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Cache key pattern to match
            
        Returns:
            Number of cache entries invalidated
        """
        try:
            # Invalidate Django cache
            invalidated_count = 0
            
            # Get all keys matching the pattern
            if hasattr(cache, 'keys'):
                matching_keys = cache.keys(f"*{pattern}*")
                for key in matching_keys:
                    cache.delete(key)
                    invalidated_count += 1
            
            # Invalidate database cache
            db_invalidated = AnalyticsCache.objects.filter(
                cache_key__icontains=pattern
            ).delete()[0]
            
            invalidated_count += db_invalidated
            
            logger.info(f"Invalidated {invalidated_count} cache entries for pattern '{pattern}'")
            return invalidated_count
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache pattern '{pattern}': {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and health metrics."""
        try:
            total_cache_entries = AnalyticsCache.objects.count()
            expired_entries = AnalyticsCache.objects.filter(
                expires_at__lte=timezone.now()
            ).count()
            
            # Calculate cache hit rate (approximate)
            cache_hit_rate = 0
            if total_cache_entries > 0:
                valid_entries = total_cache_entries - expired_entries
                cache_hit_rate = (valid_entries / total_cache_entries) * 100
            
            return {
                'total_entries': total_cache_entries,
                'expired_entries': expired_entries,
                'valid_entries': total_cache_entries - expired_entries,
                'cache_hit_rate': round(cache_hit_rate, 2),
                'cache_health': 'GOOD' if cache_hit_rate > 80 else 'NEEDS_ATTENTION'
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries from database."""
        try:
            expired_count = AnalyticsCache.objects.filter(
                expires_at__lte=timezone.now()
            ).delete()[0]
            
            logger.info(f"Cleaned up {expired_count} expired cache entries")
            return expired_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return 0


class CacheInvalidationService:
    """Service for intelligent cache invalidation."""
    
    @staticmethod
    def invalidate_employee_cache(employee_id: int) -> int:
        """Invalidate all caches related to an employee."""
        patterns = [
            f"employee_status:{employee_id}",
            f"employee_analytics:{employee_id}",
            f"attendance_record:{employee_id}",
            f"employee_events:{employee_id}"
        ]
        
        total_invalidated = 0
        for pattern in patterns:
            total_invalidated += EnhancedCachingService().invalidate_cache(pattern)
        
        return total_invalidated
    
    @staticmethod
    def invalidate_department_cache(department_id: int) -> int:
        """Invalidate department-related caches."""
        patterns = [
            f"dept_summary:{department_id}",
            f"dept_employees:{department_id}",
            f"department_analytics:{department_id}",
            "department_stats"
        ]
        
        total_invalidated = 0
        for pattern in patterns:
            total_invalidated += EnhancedCachingService().invalidate_cache(pattern)
        
        return total_invalidated
    
    @staticmethod
    def invalidate_date_cache(date_str: str) -> int:
        """Invalidate caches for a specific date."""
        patterns = [
            f"daily_summary:{date_str}",
            f"attendance_record:{date_str}",
            f"daily_dashboard:{date_str}"
        ]
        
        total_invalidated = 0
        for pattern in patterns:
            total_invalidated += EnhancedCachingService().invalidate_cache(pattern)
        
        return total_invalidated
    
    @staticmethod
    def invalidate_all_reports() -> int:
        """Invalidate all report caches."""
        return EnhancedCachingService().invalidate_cache("report:")


# Global instances
enhanced_cache = EnhancedCachingService()
cache_invalidator = CacheInvalidationService()
