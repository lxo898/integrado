from django.urls import path
from django.contrib.auth import views as auth_views

from .views import (
    UserLoginView, UserLogoutView,
    dashboard_user, dashboard_admin, dashboard_statistics,
    availability_json, resource_availability, resource_availability_bulk,
    ReservationCreateView, ReservationDetailView, my_history, cancel_reservation,
    approvals_pending, approve_or_reject,
    SpaceListView, SpaceCreateView, SpaceUpdateView, SpaceDeleteView,
    ResourceListView, ResourceCreateView, ResourceUpdateView, ResourceDeleteView,
    CarreraListView, CarreraCreateView, CarreraUpdateView, CarreraDeleteView,
    AreaListView, AreaCreateView, AreaUpdateView, AreaDeleteView,
    notifications_view, export_reservations_csv, profile_view,
    calendar_view, reports_view,
)

urlpatterns = [
    # Auth
    path("login/",  UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    # path("register/", register, name="register"),

    # ---- Password reset (nombres estándar que usa la plantilla) ----
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="auth/password_reset_form.html",
            email_template_name="auth/password_reset_email.html",
            subject_template_name="auth/password_reset_subject.txt",
            success_url="/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="auth/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="auth/password_reset_confirm.html",
            success_url="/reset/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="auth/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    # -----------------------------------------------------------------

    # Dashboards
    path("", dashboard_user, name="dashboard_user"),
    path("admin-dashboard/", dashboard_admin, name="dashboard_admin"),
    path("admin-statistics/", dashboard_statistics, name="dashboard_statistics"),

    # Calendario / disponibilidad
    path("availability/", availability_json, name="availability_json"),
    path("api/resource-availability/", resource_availability, name="resource_availability"),
    path("api/resource-availability/bulk/", resource_availability_bulk, name="resource_availability_bulk"),
    path("calendario/", calendar_view, name="calendar"),

    # Reservas
    path("reservas/nueva/", ReservationCreateView.as_view(), name="reservation_new"),
    path("reservas/<int:pk>/", ReservationDetailView.as_view(), name="reservation_detail"),
    path("reservas/<int:pk>/cancelar/", cancel_reservation, name="reservation_cancel"),
    path("historial/", my_history, name="history"),

    # Aprobaciones (solo staff/admin)
    path("aprobaciones/", approvals_pending, name="approvals_pending"),
    path("aprobaciones/<int:pk>/decidir/", approve_or_reject, name="approve_or_reject"),

    # Espacios (solo staff/admin para crear/editar/eliminar; listado visible si usas la vista sin restricción)
    path("espacios/", SpaceListView.as_view(), name="spaces_list"),
    path("espacios/nuevo/", SpaceCreateView.as_view(), name="space_new"),
    path("espacios/<int:pk>/editar/", SpaceUpdateView.as_view(), name="space_edit"),
    path("espacios/<int:pk>/eliminar/", SpaceDeleteView.as_view(), name="space_delete"),

    # Recursos (solo staff/admin para crear/editar/eliminar)
    path("recursos/", ResourceListView.as_view(), name="resources_list"),
    path("recursos/nuevo/", ResourceCreateView.as_view(), name="resource_new"),
    path("recursos/<int:pk>/editar/", ResourceUpdateView.as_view(), name="resource_edit"),
    path("recursos/<int:pk>/eliminar/", ResourceDeleteView.as_view(), name="resource_delete"),

    # Carreras
    path("carreras/", CarreraListView.as_view(), name="carreras_list"),
    path("carreras/nueva/", CarreraCreateView.as_view(), name="carrera_new"),
    path("carreras/<int:pk>/editar/", CarreraUpdateView.as_view(), name="carrera_edit"),
    path("carreras/<int:pk>/eliminar/", CarreraDeleteView.as_view(), name="carrera_delete"),

    # Areas
    path("areas/", AreaListView.as_view(), name="areas_list"),
    path("areas/nueva/", AreaCreateView.as_view(), name="area_new"),
    path("areas/<int:pk>/editar/", AreaUpdateView.as_view(), name="area_edit"),
    path("areas/<int:pk>/eliminar/", AreaDeleteView.as_view(), name="area_delete"),

    # Notificaciones, Reportes, Perfil
    path("notificaciones/", notifications_view, name="notifications"),
    path("reportes/", reports_view, name="reports_view"),
    path("reportes/reservas.csv", export_reservations_csv, name="export_reservations_csv"),
    path("perfil/", profile_view, name="profile"),
]
