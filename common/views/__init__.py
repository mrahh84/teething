"""
Modular views package for the attendance system.

This package organizes views by functionality to improve maintainability
and reduce the size of the monolithic views.py file.

Phase 1: Package structure created, imports from legacy_views.py.
Phase 2: Functions will be migrated from legacy_views.py to these modules.
"""

# Import everything from legacy views for backward compatibility
from ..legacy_views import *

# Import from individual modules (these delegate to legacy_views for now)
from .security_views import *
from .attendance_views import *  
from .reporting_views import *
from .dashboard_views import *
from .location_views import *
from .api_views import *
from .system_views import *
from .utils import *