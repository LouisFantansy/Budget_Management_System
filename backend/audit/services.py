from typing import Optional

from .models import AuditLog


def create_audit_log(
    *,
    actor=None,
    category: str,
    action: str,
    target_type: str,
    target_id=None,
    target_label: str = '',
    department=None,
    book=None,
    version=None,
    details: Optional[dict] = None,
):
    return AuditLog.objects.create(
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        category=category,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        department=department,
        book=book,
        version=version,
        details=details or {},
    )
