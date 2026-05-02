from typing import Optional

from .models import Notification


def create_notification(
    *,
    recipient,
    category: str,
    title: str,
    message: str = '',
    target_type: str = '',
    target_id=None,
    department=None,
    extra: Optional[dict] = None,
):
    if not recipient or not getattr(recipient, 'is_authenticated', True):
        return None
    return Notification.objects.create(
        recipient=recipient,
        category=category,
        title=title,
        message=message,
        target_type=target_type,
        target_id=target_id,
        department=department,
        extra=extra or {},
    )


def create_notifications(recipients, **kwargs):
    created = []
    seen_user_ids = set()
    for recipient in recipients:
        if not recipient or recipient.id in seen_user_ids:
            continue
        seen_user_ids.add(recipient.id)
        notification = create_notification(recipient=recipient, **kwargs)
        if notification:
            created.append(notification)
    return created
