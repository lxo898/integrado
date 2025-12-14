# api/utils.py
from typing import Iterable
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.mail import send_mail
from .models import Notification

def users_in_group(group_name: str) -> Iterable[User]:
    try:
        g = Group.objects.get(name=group_name)
        return g.user_set.all()
    except Group.DoesNotExist:
        return []

def notify_users(users: Iterable[User], message: str, email_subject: str | None = None, email_body: str | None = None):
    # Notificación interna
    for u in users:
        Notification.objects.create(user=u, message=message)

    # Correo (opcional)
    if email_subject and email_body and getattr(settings, "SEND_EMAIL_TO_CLEANING", False):
        recipient_list = [u.email for u in users if u.email]
        if recipient_list:
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                fail_silently=True,  # evita romper el flujo si el SMTP falla
            )

def is_coordinator(user):
    """Pertenece al grupo 'Coordinador'."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name="Coordinador").exists()

def check_resource_availability(resource, start_dt, end_dt, exclude_reservation_id=None) -> int:
    """
    Calcula cuántos ítems de 'resource' quedan disponibles en el lapso [start_dt, end_dt).
    Total - (Suma de quantity usadas en reservas superpuestas APPR/PEND).
    """
    from .models import Reservation, ReservationResource
    
    # 1. Total base
    total = resource.quantity
    
    # 2. Reservas que solapan (misma lógica que reservation.overlaps)
    #    Status: PENDING o APPROVED
    overlaps = Reservation.objects.filter(
        status__in=[Reservation.PENDING, Reservation.APPROVED],
        start__lt=end_dt, end__gt=start_dt
    )
    
    if exclude_reservation_id:
        overlaps = overlaps.exclude(id=exclude_reservation_id)
        
    # 3. Sumar uso
    used_count = 0
    # Optimización: filtrar ReservationResource que apunten a este resource
    # y cuyas reservas estén en 'overlaps'
    usage_qs = ReservationResource.objects.filter(
        resource=resource,
        reservation__in=overlaps
    )
    
    for usage in usage_qs:
        used_count += usage.quantity
        
    return max(0, total - used_count)
