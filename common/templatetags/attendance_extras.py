from django import template
import re
from ..services.attendance_service import normalize_department_from_designation

register = template.Library()

@register.filter
def absent_count(records):
    return sum(1 for r in records if getattr(r, 'absent', False))

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key."""
    return dictionary.get(key)

@register.filter
def get_department_from_designation(designation):
    """Template filter delegating to service function."""
    return normalize_department_from_designation(designation) or "No Department"