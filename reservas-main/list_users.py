import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drf.settings")
django.setup()

from django.contrib.auth.models import User

def list_users():
    print(f"{'ID':<5} {'Username':<30} {'Email':<30} {'Superuser':<10} {'Staff':<10}")
    print("-" * 85)
    for u in User.objects.all():
        print(f"{u.id:<5} {u.username:<30} {u.email:<30} {str(u.is_superuser):<10} {str(u.is_staff):<10}")

if __name__ == "__main__":
    list_users()
