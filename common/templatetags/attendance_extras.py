from django import template
import re

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
    """
    Extract and normalize department from card designation.
    Returns the normalized department name or None if not found.
    """
    if not designation:
        return "No Department"
    
    # Extract department from designation (e.g., "Digitization Tech.1" -> "Digitization Tech")
    match = re.match(r'^([^.]+)', designation.strip())
    if match:
        raw_dept = match.group(1).strip()
        
        # Normalize department names to main departments
        dept = raw_dept.lower()
        
        # Map to main departments
        if ('digitization' in dept or 'digitzation' in dept) and 'tech' in dept:
            return 'Digitization Tech'
        elif 'digitization' in dept or 'digitzation' in dept:
            return 'Digitization Tech'
        elif 'tech' in dept and 'compute' in dept:
            return 'Tech Compute'
        elif 'tech' in dept or 'tch' in dept:
            return 'Tech Compute'
        elif 'con' in dept:
            return 'Con'
        elif 'custodian' in dept:
            return 'Custodian'
        elif 'material' in dept and 'retriever' in dept:
            return 'Material Retriever'
        elif 'material' in dept and 'retriver' in dept:
            return 'Material Retriever'
        elif 'admin' in dept:
            return 'Con'  # Map Admin to Con as specified
        else:
            # Return original if no match found
            return raw_dept
    return "No Department" 