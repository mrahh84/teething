from django import template
register = template.Library()

@register.filter
def absent_count(records):
    return sum(1 for r in records if getattr(r, 'absent', False)) 