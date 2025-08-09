"""Attendance-related views module (Phase 1 modularization).

For now, we import from the legacy common.views to avoid duplicating logic.
In Phase 2, we'll move implementations here.
"""
from .. import views as legacy_views

# Re-export legacy views under the new module to prepare URLs to import here
attendance_list = legacy_views.attendance_list
progressive_entry = legacy_views.progressive_entry
historical_progressive_entry = legacy_views.historical_progressive_entry
bulk_historical_update = legacy_views.bulk_historical_update

