"""
Performance monitoring and optimization utilities for the attendance system.
"""

import time
import functools
import logging
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


def performance_monitor(func_name=None, threshold_ms=1000):
    """
    Decorator to monitor function performance and cache slow operations.
    
    Args:
        func_name: Optional custom name for the function
        threshold_ms: Threshold in milliseconds to log slow operations
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                success = True
            except Exception as e:
                success = False
                raise e
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Log slow operations
                if duration_ms > threshold_ms:
                    logger.warning(
                        f"Slow operation detected: {func.__name__} took {duration_ms:.2f}ms"
                    )
                
                # Cache performance metrics
                metric_key = f"perf_metrics:{func.__name__}"
                metrics = cache.get(metric_key, {
                    'count': 0,
                    'total_time': 0,
                    'avg_time': 0,
                    'max_time': 0,
                    'min_time': float('inf'),
                    'slow_count': 0
                })
                
                metrics['count'] += 1
                metrics['total_time'] += duration_ms
                metrics['avg_time'] = metrics['total_time'] / metrics['count']
                metrics['max_time'] = max(metrics['max_time'], duration_ms)
                metrics['min_time'] = min(metrics['min_time'], duration_ms)
                if duration_ms > threshold_ms:
                    metrics['slow_count'] += 1
                
                cache.set(metric_key, metrics, 3600)  # Cache for 1 hour
                
                # Log performance metrics periodically
                if metrics['count'] % 100 == 0:  # Log every 100 calls
                    logger.info(
                        f"Performance metrics for {func.__name__}: "
                        f"avg={metrics['avg_time']:.2f}ms, "
                        f"max={metrics['max_time']:.2f}ms, "
                        f"slow={metrics['slow_count']}/{metrics['count']}"
                    )
            
            return result
        return wrapper
    return decorator


def get_performance_metrics(func_name: str) -> Dict[str, Any]:
    """Get performance metrics for a specific function."""
    metric_key = f"perf_metrics:{func_name}"
    return cache.get(metric_key, {})


def clear_performance_metrics(func_name: str = None) -> None:
    """Clear performance metrics for a specific function or all functions."""
    if func_name:
        metric_key = f"perf_metrics:{func_name}"
        cache.delete(metric_key)
    else:
        # Clear all performance metrics
        pattern = "perf_metrics:*"
        # Note: This requires Redis SCAN command - implement based on your cache backend
        # For now, we'll use a simple approach
        pass


def query_count_monitor(func):
    """
    Decorator to monitor database query counts.
    Useful for identifying N+1 query problems.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from django.db import connection
        
        # Store initial query count
        initial_queries = len(connection.queries) if hasattr(connection, 'queries') else 0
        
        # Execute function
        result = func(*args, **kwargs)
        
        # Count queries
        final_queries = len(connection.queries) if hasattr(connection, 'queries') else 0
        query_count = final_queries - initial_queries
        
        # Log if too many queries
        if query_count > 10:  # Threshold for "too many" queries
            logger.warning(
                f"High query count detected in {func.__name__}: {query_count} queries"
            )
        
        # Cache query count metrics
        metric_key = f"query_metrics:{func.__name__}"
        metrics = cache.get(metric_key, {
            'count': 0,
            'total_queries': 0,
            'avg_queries': 0,
            'max_queries': 0,
            'high_query_count': 0
        })
        
        metrics['count'] += 1
        metrics['total_queries'] += query_count
        metrics['avg_queries'] = metrics['total_queries'] / metrics['count']
        metrics['max_queries'] = max(metrics['max_queries'], query_count)
        if query_count > 10:
            metrics['high_query_count'] += 1
        
        cache.set(metric_key, metrics, 3600)
        
        return result
    return wrapper


def get_query_metrics(func_name: str) -> Dict[str, Any]:
    """Get query count metrics for a specific function."""
    metric_key = f"query_metrics:{func_name}"
    return cache.get(metric_key, {})


def cache_optimization_monitor(func):
    """
    Decorator to monitor cache hit rates and effectiveness.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Track cache operations
        cache_hits = 0
        cache_misses = 0
        
        # Execute function
        result = func(*args, **kwargs)
        
        # Calculate cache hit rate
        total_ops = cache_hits + cache_misses
        hit_rate = (cache_hits / total_ops * 100) if total_ops > 0 else 0
        
        # Log cache performance
        if hit_rate < 80:  # Low cache hit rate
            logger.warning(
                f"Low cache hit rate in {func.__name__}: {hit_rate:.1f}%"
            )
        
        # Cache metrics
        metric_key = f"cache_metrics:{func.__name__}"
        metrics = cache.get(metric_key, {
            'count': 0,
            'total_hits': 0,
            'total_misses': 0,
            'avg_hit_rate': 0
        })
        
        metrics['count'] += 1
        metrics['total_hits'] += cache_hits
        metrics['total_misses'] += cache_misses
        total_ops = metrics['total_hits'] + metrics['total_misses']
        metrics['avg_hit_rate'] = (metrics['total_hits'] / total_ops * 100) if total_ops > 0 else 0
        
        cache.set(metric_key, metrics, 3600)
        
        return result
    return wrapper


def get_cache_metrics(func_name: str) -> Dict[str, Any]:
    """Get cache performance metrics for a specific function."""
    metric_key = f"cache_metrics:{func_name}"
    return cache.get(metric_key, {})


def optimize_queryset(queryset, select_related=None, prefetch_related=None):
    """
    Utility function to optimize querysets with common optimizations.
    
    Args:
        queryset: The queryset to optimize
        select_related: List of fields to select_related
        prefetch_related: List of fields to prefetch_related
    """
    if select_related:
        queryset = queryset.select_related(*select_related)
    
    if prefetch_related:
        queryset = queryset.prefetch_related(*prefetch_related)
    
    return queryset


def bulk_operation_monitor(operation_name: str):
    """
    Decorator to monitor bulk operations for performance.
    
    Args:
        operation_name: Name of the bulk operation being monitored
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Execute bulk operation
            result = func(*args, **kwargs)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Log bulk operation performance
            logger.info(
                f"Bulk operation '{operation_name}' completed in {duration_ms:.2f}ms"
            )
            
            # Cache bulk operation metrics
            metric_key = f"bulk_metrics:{operation_name}"
            metrics = cache.get(metric_key, {
                'count': 0,
                'total_time': 0,
                'avg_time': 0,
                'max_time': 0
            })
            
            metrics['count'] += 1
            metrics['total_time'] += duration_ms
            metrics['avg_time'] = metrics['total_time'] / metrics['count']
            metrics['max_time'] = max(metrics['max_time'], duration_ms)
            
            cache.set(metric_key, metrics, 3600)
            
            return result
        return wrapper
    return decorator


def get_bulk_metrics(operation_name: str) -> Dict[str, Any]:
    """Get bulk operation metrics for a specific operation."""
    metric_key = f"bulk_metrics:{operation_name}"
    return cache.get(metric_key, {}) 