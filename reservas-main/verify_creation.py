import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drf.settings")
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth.models import User
from api.models import Carrera, Area
from api.views import CarreraCreateView, AreaCreateView

def test_creation():
    print("--- INICIANDO DIAGNÓSTICO ---")
    
    # 1. Crear un usuario admin temporal para la prueba
    username = "test_admin_debug"
    password = "password123"
    email = "test_admin@inacap.cl"
    
    user, created = User.objects.get_or_create(username=email, email=email)
    if created:
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        print(f"Usuario de prueba creado: {email}")
    else:
        print(f"Usuario de prueba existe: {email}")

    # 2. Probar creación de Carrera via Vista (simulando POST)
    print("\n[PRUEBA 1] Creando Carrera 'Ingeniería Test'...")
    factory = RequestFactory()
    data = {"name": "Ingeniería Test", "code": "ING-TEST"}
    request = factory.post("/carreras/nueva/", data)
    request.user = user
    request._messages = [] # Mock messages

    # Necesitamos añadir el soporte de mensajes al request factory
    from django.contrib.messages.storage.fallback import FallbackStorage
    setattr(request, 'session', 'session')
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    try:
        view = CarreraCreateView.as_view()
        response = view(request)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 302:
            print("EXITO: La vista redirigió (302), lo cual indica éxito.")
            if Carrera.objects.filter(name="Ingeniería Test").exists():
                print("VERIFICADO: La carrera existe en la base de datos.")
            else:
                print("FALLO: Redirigió pero NO se guardó en BD.")
        else:
            print("FALLO: La vista no redirigió.")
            if hasattr(response, 'context_data'):
                form = response.context_data.get('form')
                if form and form.errors:
                    print("ERRORES DEL FORMULARIO:", form.errors)
    except Exception as e:
        print(f"EXCEPCIÓN AL EJECUTAR VISTA: {e}")

    # 3. Probar creación de Area
    print("\n[PRUEBA 2] Creando Area 'Area Test'...")
    data_area = {"name": "Area Test", "description": "Test Desc"}
    request_area = factory.post("/areas/nueva/", data_area)
    request_area.user = user
    setattr(request_area, 'session', 'session')
    messages_area = FallbackStorage(request_area)
    setattr(request_area, '_messages', messages_area)

    try:
        view = AreaCreateView.as_view()
        response = view(request_area)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 302:
            print("EXITO: La vista redirigió (302).")
            if Area.objects.filter(name="Area Test").exists():
                print("VERIFICADO: El área existe en la base de datos.")
        else:
            print("FALLO: Status code inesperado.")
            if hasattr(response, 'context_data'):
                form = response.context_data.get('form')
                if form and form.errors:
                    print("ERRORES DEL FORMULARIO:", form.errors)

    except Exception as e:
        print(f"EXCEPCIÓN AREA: {e}")

    print("\n--- DIAGNÓSTICO FINALIZADO ---")

if __name__ == "__main__":
    test_creation()
