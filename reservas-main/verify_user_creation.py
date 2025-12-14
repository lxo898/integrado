import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drf.settings")
django.setup()

from api.forms import AdminUserForm
from api.models import Area, Carrera

def test_user_creation():
    print("--- TEST USER CREATION FROM FORM ---")
    
    # Ensure dependencies exist
    a, _ = Area.objects.get_or_create(name="Area Test User")
    c, _ = Carrera.objects.get_or_create(name="Carrera Test User", code="CTU")

    data = {
        "email": "test.user.form@inacap.cl",
        "first_name": "Test",
        "last_name": "User",
        "password": "password123",
        "rol": "Usuario",
        "is_active": True,
        "area": a.id,
        "carrera": c.id
    }
    
    print(f"Data to save: {data}")
    
    form = AdminUserForm(data)
    if not form.is_valid():
        print("FORM INVALID:")
        print(form.errors)
        return

    try:
        user = form.save()
        print(f"User created: {user} (ID: {user.id})")
        print(f"Profile area: {user.profile.area}")
        print(f"Profile carrera: {user.profile.carrera}")
        print("SUCCESS")
    except Exception as e:
        print(f"CRASH DURING SAVE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_user_creation()
