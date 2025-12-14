import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drf.settings")
django.setup()

from django.contrib.auth.models import User

def clean_users():
    print("Iniciando limpieza de usuarios...")
    # Mantener al Superusuario (ID 1) o cualquiera con is_superuser=True
    # El usuario pidió "menos el del administrador", asumimos el superuser principal.
    
    deleted_count = 0
    for u in User.objects.all():
        if u.is_superuser:
            print(f"Conservando administrador: {u.username} (ID: {u.id})")
        else:
            print(f"Eliminando usuario: {u.username} (ID: {u.id})")
            u.delete()
            deleted_count += 1
            
    print(f"Limpieza completada. Eliminados: {deleted_count}")

if __name__ == "__main__":
    clean_users()
