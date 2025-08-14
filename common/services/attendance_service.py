"""Attendance domain services.

Centralizes business logic used by views and other layers.
"""
from __future__ import annotations

import re
from typing import Iterable, List

from django.db.models import QuerySet

from ..models import Card, Employee


def normalize_department_from_designation(designation: str | None) -> str | None:
    if not designation:
        return None
    match = re.match(r"^([^.]+)", designation.strip())
    if not match:
        return None
    raw_dept = match.group(1).strip()
    dept = raw_dept.lower()

    if ("digitization" in dept or "digitzation" in dept) and "tech" in dept:
        return "Digitization Tech"
    if "digitization" in dept or "digitzation" in dept:
        return "Digitization Tech"
    if "tech" in dept and "compute" in dept:
        return "Tech Compute"
    if "tech" in dept or "tch" in dept:
        return "Tech Compute"
    if "con" in dept:
        return "Con"
    if "custodian" in dept:
        return "Custodian"
    if "material" in dept and "retriever" in dept:
        return "Material Retriever"
    if "material" in dept and "retriver" in dept:
        return "Material Retriever"
    if "admin" in dept:
        return "Con"
    return raw_dept


def list_available_departments() -> List[str]:
    departments = set()
    for card in Card.objects.all():
        dept = normalize_department_from_designation(card.designation)
        if dept:
            departments.add(dept)
    return sorted(list(departments))


def filter_employees_by_department(
    employees: QuerySet[Employee], department: str | None
) -> List[Employee] | QuerySet[Employee]:
    if not department:
        return employees
    filtered = []
    for employee in employees:
        if employee.card_number:
            emp_dept = normalize_department_from_designation(employee.card_number.designation)
            if emp_dept == department:
                filtered.append(employee)
    return filtered

