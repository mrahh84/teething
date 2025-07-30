from rest_framework import permissions


class SecurityPermission(permissions.BasePermission):
    """Allow access to security role and above"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.has_any_role(['security', 'attendance', 'admin'])


class AttendancePermission(permissions.BasePermission):
    """Allow access to attendance role and above"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.has_any_role(['attendance', 'admin'])


class ReportingPermission(permissions.BasePermission):
    """Allow access to reporting role and above"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.has_any_role(['reporting', 'attendance', 'admin'])


class AdminPermission(permissions.BasePermission):
    """Allow access to admin role only"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.has_role('admin') 