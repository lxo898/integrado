import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drf.settings")
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from api.models import Carrera, Area
from api.forms import CarreraForm, AreaForm

def run_diag():
    print("=== DIAGNOSTICO DE DUPLICADOS ===")
    
    # 1. Crear una carrera base
    c_name = "Informatica DUPLICATE TEST"
    Carrera.objects.filter(name=c_name).delete()
    Carrera.objects.create(name=c_name, code="TEST-1")
    print(f"Carrera creada: {c_name}")

    # 2. Intentar crear la MISMA carrera via Form
    print("Intentando crear duplicado...")
    data = {"name": c_name, "code": "TEST-2"}
    form = CarreraForm(data)
    
    if form.is_valid():
        print("ERROR: El formulario validó un duplicado! (Esto no debería pasar)")
    else:
        print("EXITO: El formulario detectó el error.")
        print(f"Errores encontrados: {form.errors}")

    # 3. Validar HTML de respuesta renderizando el form con errores
    # Esto simula lo que ve el usuario
    # No podemos renderizar la vista completa fácilmente sin request, pero sí el form.
    print("\nSimulando contexto visual:")
    for field, errors in form.errors.items():
        print(f"Campo '{field}': {errors}")

if __name__ == "__main__":
    run_diag()
