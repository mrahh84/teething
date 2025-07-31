from django import template
from django.contrib.auth.models import User

register = template.Library()


@register.filter
def has_role(user, role):
    """Check if user has specific role"""
    if not user.is_authenticated:
        return False
    return user.has_role(role)


@register.filter
def has_any_role(user, roles):
    """Check if user has any of the specified roles"""
    if not user.is_authenticated:
        return False
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split(',')]
    return user.has_any_role(roles)


@register.filter
def get_role_display(user):
    """Get user's role display name"""
    if not user.is_authenticated:
        return None
    try:
        return user.userrole.get_role_display()
    except:
        return None 