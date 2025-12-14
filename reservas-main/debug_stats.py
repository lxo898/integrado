import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'drf.settings')
django.setup()

from api.models import Reservation, User, Profile

print("--- Debugging Reservations ---")
count = Reservation.objects.count()
print(f"Total Reservations: {count}")

if count > 0:
    print("\nLast 5 Reservations:")
    for r in Reservation.objects.all().order_by('-id')[:5]:
        print(f"ID: {r.id}, User: {r.user.username}, Space: {r.space.name}, Start: {r.start}, Status: {r.status}")
        
    print("\n--- User Profiles ---")
    admin = User.objects.filter(is_superuser=True).first()
    if admin:
        print(f"Admin: {admin.username}, Profile exists: {hasattr(admin, 'profile')}")
        if hasattr(admin, 'profile'):
            print(f"Admin Area: {admin.profile.area}, Carrera: {admin.profile.carrera}")

    print("\n--- Stats Queries Preview ---")
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    from django.utils import timezone
    
    # Status
    print("Status Distribution:", list(Reservation.objects.values('status').annotate(count=Count('id'))))
    
    print("\n--- Approvals check ---")
    from api.models import Approval
    print(f"Total Approvals: {Approval.objects.count()}")
    for a in Approval.objects.all():
        print(f"Approval for Res {a.reservation.id}: {a.decision} at {a.decided_at}")
    
    # Career
    print("Career Distribution:", list(Reservation.objects.values('user__profile__carrera__name').annotate(count=Count('id'))))
else:
    print("No reservations found.")
