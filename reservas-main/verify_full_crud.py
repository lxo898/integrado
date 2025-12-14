import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drf.settings")
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from api.models import Carrera, Area
from api.views import (
    CarreraCreateView, CarreraUpdateView, CarreraDeleteView,
    AreaCreateView, AreaUpdateView, AreaDeleteView
)

def setup_admin():
    email = "debug_admin@inacap.cl"
    u, _ = User.objects.get_or_create(username=email, email=email)
    u.set_password("pass")
    u.is_staff = True
    u.save()
    return u

def mock_request(user, path, data=None):
    factory = RequestFactory()
    if data is not None:
        req = factory.post(path, data)
    else:
        req = factory.get(path)
    req.user = user
    setattr(req, 'session', 'session')
    messages = FallbackStorage(req)
    setattr(req, '_messages', messages)
    return req

def run_test():
    print("=== INICIANDO DIAGNÓSTICO PROFUNDO ===")
    user = setup_admin()
    
    # --- CARRERA ---
    print("\n[CARRERA] Testing Flow...")
    
    # 1. CREATE
    c_name = "Carrera Debug"
    # Limpiar si existe
    Carrera.objects.filter(name=c_name).delete()
    
    req = mock_request(user, "/carreras/nueva/", {"name": c_name, "code": "DBG-1"})
    try:
        resp = CarreraCreateView.as_view()(req)
        if resp.status_code == 302:
            print(f" -> CREATE: OK (302 Redirect).")
        else:
            print(f" -> CREATE: FALLO. Status: {resp.status_code}")
            if hasattr(resp, 'render'): 
                print(resp.render().content.decode()[:500]) # Primeros 500 chars del error
    except Exception as e:
        print(f" -> CREATE: CRASH. {e}")

    # Recuperar objeto
    obj = Carrera.objects.filter(name=c_name).first()
    if not obj:
        print(" -> ERROR FATAL: No se guardó en BD.")
        return

    # 2. UPDATE
    print(f" -> Objeto creado ID: {obj.id}")
    req = mock_request(user, f"/carreras/{obj.id}/editar/", {"name": c_name + " Edit", "code": "DBG-2"})
    try:
        resp = CarreraUpdateView.as_view()(req, pk=obj.id)
        if resp.status_code == 302:
            print(f" -> UPDATE: OK (302 Redirect).")
            opts = Carrera.objects.get(pk=obj.id)
            if opts.name == c_name + " Edit":
                print(" -> UPDATE: BD actualizada correctamente.")
            else:
                print(" -> UPDATE: BD NO se actualizó.")
        else:
             print(f" -> UPDATE: FALLO. Status: {resp.status_code}")
    except Exception as e:
        print(f" -> UPDATE: CRASH. {e}")

    # 3. DELETE
    req = mock_request(user, f"/carreras/{obj.id}/eliminar/", {}) # POST vacío confirma delete
    try:
        resp = CarreraDeleteView.as_view()(req, pk=obj.id)
        if resp.status_code == 302:
            if not Carrera.objects.filter(pk=obj.id).exists():
                print(f" -> DELETE: OK (Eliminado).")
            else:
                print(f" -> DELETE: Fallo (Objeto sigue en BD).")
        else:
            print(f" -> DELETE: FALLO. Status: {resp.status_code}")
    except Exception as e:
        print(f" -> DELETE: CRASH. {e}")


    # --- AREA ---
    print("\n[AREA] Testing Flow...")
    a_name = "Area Debug"
    Area.objects.filter(name=a_name).delete()

    # 1. CREATE
    req = mock_request(user, "/areas/nueva/", {"name": a_name, "description": "Desc"})
    try:
        resp = AreaCreateView.as_view()(req)
        if resp.status_code == 302:
            print(f" -> CREATE: OK.")
        else:
            print(f" -> CREATE: FALLO. Status: {resp.status_code}")
    except Exception as e:
        print(f" -> CREATE: CRASH. {e}")

    obj = Area.objects.filter(name=a_name).first()
    if obj:
        # 2. UPDATE
        req = mock_request(user, f"/areas/{obj.id}/editar/", {"name": a_name + " Edit", "description": "New Desc"})
        try:
             resp = AreaUpdateView.as_view()(req, pk=obj.id)
             if resp.status_code == 302:
                 print(" -> UPDATE: OK.")
             else:
                 print(f" -> UPDATE: FALLO {resp.status_code}")
        except Exception as e:
            print(f" -> UPDATE: CRASH {e}")
            
        # 3. DELETE
        req = mock_request(user, f"/areas/{obj.id}/eliminar/", {})
        try:
            resp = AreaDeleteView.as_view()(req, pk=obj.id)
            if resp.status_code == 302:
                print(" -> DELETE: OK.")
        except Exception as e:
            print(f" -> DELETE: CRASH {e}")

    print("\n=== FIN DIAGNÓSTICO ===")

if __name__ == "__main__":
    run_test()
