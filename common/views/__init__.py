"""Modular views package.

This package progressively replaces the monolithic views.py by grouping views
into focused modules. During migration, common.views still re-exports certain
callables to keep URL names and imports stable.
"""

