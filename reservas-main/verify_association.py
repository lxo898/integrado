
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'drf.settings')
django.setup()

from django.contrib.auth.models import User, Group
from api.models import Area, Carrera, Profile
from api.forms import AdminUserForm

def verify_association():
    print("Verifying Area/Carrera Association...")

    # Clean up previous test data
    User.objects.filter(username="test_user_assoc").delete()
    Area.objects.filter(name="Test Area").delete()
    Carrera.objects.filter(name="Test Carrera").delete()

    # Create dummy Area and Carrera
    area = Area.objects.create(name="Test Area")
    carrera = Carrera.objects.create(name="Test Carrera")
    print(f"Created Area: {area}")
    print(f"Created Carrera: {carrera}")

    # Test AdminUserForm
    form_data = {
        "email": "test_user_assoc@inacap.cl",
        "first_name": "Test",
        "last_name": "User",
        "password": "password123",
        "rol": "Usuario",
        "is_active": True,
        "area": area.id,
        # "carrera": carrera.id # Test only associating Area first
        # Form validation requires simple values for ModelChoiceField in tests usually, 
        # but ModelChoiceField expects the ID in cleaned_data usually coming from POST. 
        # However, passing the ID in data dictionary works for form validation.
    }
    
    # We need to simulate the POST data for the form.
    # ModelChoiceField expects the PK.
    
    form = AdminUserForm(data=form_data)
    if form.is_valid():
        user = form.save()
        print(f"User created: {user.username}")
        
        # Verify Profile association
        profile = user.profile
        print(f"Profile Area: {profile.area}")
        print(f"Profile Carrera: {profile.carrera}")
        
        if profile.area == area and profile.carrera is None:
            print("SUCCESS: User associated with Area correctly.")
        else:
            print("FAILURE: User association incorrect.")
            
    else:
        print("Form errors:", form.errors)

    # Cleanup
    User.objects.filter(username="test_user_assoc").delete()
    Area.objects.filter(name="Test Area").delete()
    Carrera.objects.filter(name="Test Carrera").delete()

if __name__ == "__main__":
    verify_association()
