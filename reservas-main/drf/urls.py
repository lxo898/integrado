# drf/urls.py
from django.contrib import admin
from django.urls import path, include
from api.views import admin_user_new

urlpatterns = [
    # Ruta personalizada para crear usuarios con rol (solo Administrador)
    path("admin/usuarios/nuevo/", admin_user_new, name="admin_user_new"),
    path("admin/", admin.site.urls),
    # Rutas de la app principal
    path("", include("api.urls")),
]
