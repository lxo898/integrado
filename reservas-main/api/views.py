# api/views.py
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView
from django.core.cache import cache

from .forms import (
    ReservationForm, ApprovalForm, LoginForm,
    SpaceForm, ResourceForm, ProfileForm,
    AreaForm, CarreraForm
)
from .models import Reservation, Approval, Space, Resource, Notification, Profile, Area, Carrera
from .utils import is_coordinator
import csv
import json


# ---------- Helpers / utilidades ----------
class StaffRequiredMixin(UserPassesTestMixin):
    """Permite solo a usuarios con is_staff=True."""
    def test_func(self):
        # Staff real (admin) - se relaja la restricción para evitar bloqueos
        return self.request.user.is_staff

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied  # 403 si está logueado pero no es staff
        return super().handle_no_permission()


def is_staff(user):
    return user.is_staff




def can_export_reports(user):
    """Puede exportar reportes: Administrador (staff) o Coordinador."""
    return bool(user.is_authenticated and (user.is_staff or is_coordinator(user)))


def _notify_user(user, message: str):
    """Crea una notificación para un usuario."""
    if user:
        Notification.objects.create(user=user, message=message)


def _notify_group(group_name: str, message: str):
    """
    Notifica a todos los usuarios de un grupo (por ej. 'aseo').
    Si el grupo no existe, no hace nada (fail-safe).
    """
    try:
        grp = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return
    users = grp.user_set.all()
    for u in users:
        Notification.objects.create(user=u, message=message)


def notify_cleaning_staff(message: str):
    """
    Notifica al equipo de aseo / preparación del espacio.
    Nombre del grupo configurable por settings.CLEANING_GROUP_NAME (default 'aseo').
    """
    group_name = getattr(settings, "CLEANING_GROUP_NAME", "aseo")
    _notify_group(group_name, message)


# ---------- Autenticación ----------
class UserLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = LoginForm  # login por correo institucional (o username como compatibilidad)

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip

    def post(self, request, *args, **kwargs):
        ip = self.get_client_ip()
        cache_key_block = f'login_block_{ip}'
        
        # 1. Check if blocked
        if cache.get(cache_key_block):
            messages.error(request, "Demasiados intentos fallidos. Por seguridad, espera 5 minutos.")
            return render(request, self.template_name, {'form': self.get_form()})
            
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        # 2. Increment failure count
        ip = self.get_client_ip()
        cache_key_attempts = f'login_attempts_{ip}'
        cache_key_block = f'login_block_{ip}'
        
        attempts = cache.get(cache_key_attempts, 0) + 1
        cache.set(cache_key_attempts, attempts, 300) # Reset expiry to 5 min on new attempt

        if attempts >= 5:
            cache.set(cache_key_block, True, 300) # Block for 5 minutes
            messages.error(self.request, "Has excedido el número máximo de intentos. Tu acceso ha sido bloqueado temporalmente.")
        
        return super().form_invalid(form)

    def form_valid(self, form):
        # 3. Success - clear failures
        ip = self.get_client_ip()
        cache.delete(f'login_attempts_{ip}')
        return super().form_valid(form)

    def get_success_url(self):
        user = self.request.user
        # Si es staff y NO es coordinador -> Admin Dashboard
        if user.is_staff and not is_coordinator(user):
            return reverse_lazy("dashboard_admin")
        # De lo contrario -> User Dashboard (default)
        return reverse_lazy("dashboard_user")





class UserLogoutView(LogoutView):
    # En Django 5, usar POST desde la plantilla (ya está resuelto en base.html)
    pass


@login_required
@user_passes_test(lambda u: u.is_staff and not is_coordinator(u))
def admin_user_new(request):
    """Vista para que administradores creen usuarios manualmente con rol."""
    from .forms import AdminUserForm  # Importación local para evitar ciclos
    if request.method == "POST":
        form = AdminUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Asegurar perfil
            Profile.objects.get_or_create(user=user)
            role_name = form.cleaned_data.get("rol")
            messages.success(request, f"Usuario {user.username} creado exitosamente con rol {role_name}.")
            return redirect("dashboard_admin")
    else:
        form = AdminUserForm()
    return render(request, "admin/user_new.html", {"form": form})


# ---------- Dashboards ----------
@login_required
def dashboard_user(request):
    # Si es administrador (staff y no coordinador), redirigir al dashboard de admin
    if request.user.is_staff and not is_coordinator(request.user):
        return redirect("dashboard_admin")

    my_pending = Reservation.objects.filter(
        user=request.user, status=Reservation.PENDING
    )[:5]
    upcoming = Reservation.objects.filter(
        user=request.user, status=Reservation.APPROVED, start__gte=timezone.now()
    )[:5]
    unread = request.user.notifications.filter(is_read=False).count()
    return render(request, "dashboard/user.html", {
        "my_pending": my_pending,
        "upcoming": upcoming,
        "unread": unread,
        # Permisos para la UI
        "can_create_reservation": True,
        "can_see_history": True,
        "can_see_spaces": True,
        "can_see_resources": True,
        "can_see_notifications": True,
        "can_see_calendar": True,
        # Solo staff/coordinadores ven reportes/usuarios en su dashboard si quisieran
        "can_export_reports": can_export_reports(request.user),
        "can_see_statistics": request.user.is_staff,
        "can_manage_users": request.user.is_staff and not is_coordinator(request.user),
        "user_role": "Coordinador" if is_coordinator(request.user) else ("Administrador" if request.user.is_staff else "Usuario"),
    })


from django.db.models import Count
from django.db.models.functions import TruncMonth

@user_passes_test(lambda u: u.is_staff and not is_coordinator(u))
def dashboard_admin(request):
    pending = Reservation.objects.filter(status=Reservation.PENDING)
    unread = request.user.notifications.filter(is_read=False).count() if request.user.is_authenticated else 0
    
    # Calculate daily stats
    # ERROR FIX: timezone.now().date() returns UTC date (which might be tomorrow).
    # We need the LOCAL date to match decided_at__date (which converts to local).
    today = timezone.localdate() 
    approved_today = Approval.objects.filter(decision="APPR", decided_at__date=today).count()
    rejected_today = Approval.objects.filter(decision="REJ", decided_at__date=today).count()

    context = {
        "pending": pending, 
        "unread": unread,
        "approved_today": approved_today,
        "rejected_today": rejected_today,
    }
    return render(request, "dashboard/admin.html", context)


@user_passes_test(lambda u: u.is_staff)
def dashboard_statistics(request):
    # --- Statistics for Charts ---
    # 1. Monthly Reservations (Last 6 months)
    six_months_ago = timezone.now() - timezone.timedelta(days=180)
    monthly_stats = (
        Reservation.objects.filter(start__gte=six_months_ago)
        .annotate(month=TruncMonth('start'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    months_labels = [entry['month'].strftime('%B') for entry in monthly_stats]
    months_data = [entry['count'] for entry in monthly_stats]

    # 2. Status Distribution
    status_stats = (
        Reservation.objects.values('status')
        .annotate(count=Count('id'))
    )
    status_map = dict(Reservation.STATUS_CHOICES)
    status_labels = [status_map.get(entry['status'], entry['status']) for entry in status_stats]
    status_data = [entry['count'] for entry in status_stats]

    # 3. Reservations by Career
    career_stats = (
        Reservation.objects
        .values('user__profile__carrera__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    # Handle None/Empy defaults
    career_labels = [entry['user__profile__carrera__name'] or 'Sin Carrera' for entry in career_stats]
    career_data = [entry['count'] for entry in career_stats]

    # 4. Reservations by Area
    area_stats = (
        Reservation.objects
        .values('user__profile__area__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    area_labels = [entry['user__profile__area__name'] or 'Sin Área' for entry in area_stats]
    area_data = [entry['count'] for entry in area_stats]

    context = {
        "months_labels": json.dumps(months_labels),
        "months_data": json.dumps(months_data),
        "status_labels": json.dumps(status_labels),
        "status_data": json.dumps(status_data),
        "career_labels": json.dumps(career_labels),
        "career_data": json.dumps(career_data),
        "area_labels": json.dumps(area_labels),
        "area_data": json.dumps(area_data),
        "is_coordinator": is_coordinator(request.user),
    }
    return render(request, "dashboard/statistics.html", context)


# ---------- Calendario / Disponibilidad ----------
@login_required
def availability_json(request):
    """
    Devuelve reservas (APROBADAS/PENDIENTES) para un space opcional en formato FullCalendar,
    con color por estado.
    """
    qs = Reservation.objects.filter(status__in=[Reservation.PENDING, Reservation.APPROVED])
    space_id = request.GET.get("space")
    if space_id:
        qs = qs.filter(space_id=space_id)

    def event_for(r: Reservation):
        # Colores: aprobado=verde, pendiente=amarillo
        if r.status == Reservation.APPROVED:
            bg = "#198754"  # success
            bd = "#198754"
            fc = "#ffffff"
        else:
            bg = "#ffc107"  # warning
            bd = "#ffc107"
            fc = "#212529"
        return {
            "id": r.id,
            "title": f"{r.space.name} ({r.get_status_display()})",
            "start": r.start.isoformat(),
            "end": r.end.isoformat(),
            "extendedProps": {"status": r.status},
            "backgroundColor": bg,
            "borderColor": bd,
            "textColor": fc,
        }

    events = [event_for(r) for r in qs]
    return JsonResponse(events, safe=False)


# ---------- Reservas ----------
class ReservationCreateView(LoginRequiredMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "reservations/form.html"
    success_url = reverse_lazy("dashboard_user")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Lista de recursos existentes para que el usuario pueda solicitarlos
        ctx["resources_all"] = Resource.objects.filter(is_active=True).order_by("name")
        return ctx

    def form_valid(self, form):
        form.instance.user = self.request.user
        
        # Validar disponibilidad de recursos antes de guardar
        # Obtenemos fechas del form (limpiadas)
        # Ojo: form.cleaned_data tiene fechas, pero para disponibilidad exacta necesitamos lo que hizo clean()
        # clean() ya validó slots, pero aquí reconstruimos para checkear recursos
        
        # Estrategia: Guardamos primero (si no hay conflicto de items) o checkeamos "en caliente"
        # Para simplificar y ser robusto:
        # 1. Recuperar datos
        resource_ids = self.request.POST.getlist("resources")
        from .models import ReservationResource, Resource
        from .utils import check_resource_availability
        
        # Construir timestamps para verificación (esto ya lo hizo el form, pero lo necesitamos)
        # Accedemos a cleaned_data
        date = form.cleaned_data.get("date")
        s_slot = form.cleaned_data.get("start_slot")
        e_slot = form.cleaned_data.get("end_slot")
        
        if date and s_slot and e_slot:
            # Re-construir dts aware
            tz = timezone.get_current_timezone()
            from datetime import datetime
            dt_s = timezone.make_aware(datetime.strptime(f"{date} {s_slot}", "%Y-%m-%d %H:%M"), tz)
            dt_e = timezone.make_aware(datetime.strptime(f"{date} {e_slot}", "%Y-%m-%d %H:%M"), tz)
            
            # Verificar cada recurso
            for r_id in resource_ids:
                try:
                    res_obj = Resource.objects.get(pk=r_id)
                    qty_requested = int(self.request.POST.get(f"quantity_{r_id}", 1))
                    if qty_requested < 1: continue 
                    
                    available = check_resource_availability(res_obj, dt_s, dt_e)
                    if available < qty_requested:
                        form.add_error(None, f"No hay suficiente stock de {res_obj.name} (Solicitado: {qty_requested}, Disponible: {available}).")
                        return self.form_invalid(form)
                except Resource.DoesNotExist:
                    pass

        # Si pasa la validación, procesamos texto (legacy)
        resources_notes = (self.request.POST.get("resources_notes") or "").strip()
        
        # --- Logic Legacy: Append to purpose ---
        if resource_ids or resources_notes:
            partes = []
            if resource_ids:
                res_details = []
                # Iteramos para texto
                for r_id in resource_ids:
                    r = Resource.objects.get(pk=r_id)
                    qty = self.request.POST.get(f"quantity_{r.id}", "1")
                    res_details.append(f"{r.name} (x{qty})")
                partes.append("Recursos solicitados: " + ", ".join(res_details))

            if resources_notes:
                partes.append("Detalle recursos: " + resources_notes)
            
            extra = " | ".join(partes)
            form.instance.purpose = (form.instance.purpose + " | " + extra).strip(" |") if form.instance.purpose else extra

        # Guardamos la reserva (super)
        response = super().form_valid(form)
        
        # CREAR OBJETOS ReservationResource REALES
        self.object = form.instance # Asegurar referencia
        for r_id in resource_ids:
            try:
                res_obj = Resource.objects.get(pk=r_id)
                qty = int(self.request.POST.get(f"quantity_{r_id}", 1))
                if qty > 0:
                    ReservationResource.objects.create(
                        reservation=self.object,
                        resource=res_obj,
                        quantity=qty
                    )
            except:
                pass


        messages.info(self.request, "Reserva creada y enviada a aprobación.")

        # Notificar a admins
        notif_msg = "Nueva reserva pendiente de aprobación."
        if resource_ids: notif_msg += " (Incluye solicitud de recursos)"
        
        for admin in Profile.objects.filter(user__is_staff=True):
            Notification.objects.create(user=admin.user, message=notif_msg)

        return response


class ReservationDetailView(DetailView):
    model = Reservation
    template_name = "reservations/detail.html"

    def get_context_data(self, **kwargs):
        """
        Incluimos aprobación (si existe) para facilitar mostrar notas/decisión al usuario.
        """
        ctx = super().get_context_data(**kwargs)
        try:
            ctx["approval"] = self.object.approval  # OneToOne, puede no existir
        except Approval.DoesNotExist:
            ctx["approval"] = None
        return ctx


@login_required
def my_history(request):
    qs = Reservation.objects.filter(user=request.user).order_by("-start")
    return render(request, "reservations/history.html", {"reservations": qs})


@login_required
def cancel_reservation(request, pk):
    """
    Cancela una reserva por el dueño via POST.
    Respeta la ventana mínima definida en settings.MIN_CANCEL_WINDOW_HOURS (lógica en el modelo).
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

    if not reservation.can_cancel():
        messages.error(
            request,
            "No puedes cancelar esta reserva (ya comenzó, está dentro de la ventana mínima o su estado no lo permite)."
        )
        return redirect("history")

    reason = (request.POST.get("reason") or "").strip()[:255]
    reservation.cancel_by_user(reason=reason, actor=request.user)
    messages.success(request, "Reserva cancelada correctamente.")

    # Avisar a equipo de aseo que ya NO se requiere preparación
    msg = (
        f"Reserva CANCELADA · {reservation.space} · "
        f"{reservation.start:%d/%m/%Y %H:%M} - {reservation.end:%H:%M} · "
        f"Solicitante: {reservation.user.username}"
        + (f" · Motivo: {reason}" if reason else "")
    )
    notify_cleaning_staff(msg)

    return redirect("history")


# ---------- Aprobaciones ----------
@login_required
@user_passes_test(is_staff)
def approvals_pending(request):
    qs = Reservation.objects.filter(status=Reservation.PENDING)
    return render(request, "approvals/pending.html", {"reservations": qs})


@login_required
@user_passes_test(is_staff)
def approve_or_reject(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)

    if request.method == "POST":
        post_data = request.POST.copy()
        btn_decision = post_data.get("decision")
        if btn_decision in {"approve", "reject"}:
            btn_decision = "APPR" if btn_decision == "approve" else "REJ"
            post_data["decision"] = btn_decision

        form = ApprovalForm(post_data)

        if form.is_valid():
            decision = form.cleaned_data["decision"]  # "APPR" | "REJ"
            notes = form.cleaned_data.get("notes", "")

            # ⛔ Si se va a APROBAR, verifica choque con APROBADAS existentes
            if decision == "APPR":
                conflict = Reservation.objects.filter(
                    space=reservation.space,
                    status=Reservation.APPROVED
                ).exclude(pk=reservation.pk).filter(
                    start__lt=reservation.end,
                    end__gt=reservation.start
                ).exists()
                if conflict:
                    messages.error(request, "No se puede aprobar: ya existe otra reserva APROBADA en ese horario.")
                    return render(
                        request, "approvals/decision_form.html",
                        {"reservation": reservation, "form": form}
                    )

            Approval.objects.update_or_create(
                reservation=reservation,
                defaults={"approver": request.user, "decision": decision, "notes": notes}
            )

            # Actualiza estado de la reserva y notifica
            if decision == "APPR":
                reservation.status = Reservation.APPROVED
                messages.success(request, "Reserva aprobada.")
                _notify_user(
                    reservation.user,
                    f"Tu reserva '{reservation}' fue aprobada."
                    + (f" Notas: {notes}" if notes else "")
                )

                # Avisar a equipo de aseo para preparar el espacio
                msg = (
                    f"RESERVA APROBADA · Preparar espacio · {reservation.space} · "
                    f"{reservation.start:%d/%m/%Y %H:%M} - {reservation.end:%H:%M} · "
                    f"Solicitante: {reservation.user.username}"
                    + (f" · Notas: {notes}" if notes else "")
                )
                notify_cleaning_staff(msg)

            else:
                reservation.status = Reservation.REJECTED
                messages.warning(request, "Reserva rechazada.")
                _notify_user(
                    reservation.user,
                    f"Tu reserva '{reservation}' fue rechazada."
                    + (f" Motivo: {notes}" if notes else "")
                )

            reservation.save()
            return redirect("approvals_pending")
        else:
            messages.error(request, "Revisa los errores del formulario.")
    else:
        form = ApprovalForm()

    return render(
        request, "approvals/decision_form.html",
        {"reservation": reservation, "form": form}
    )


# ---------- CRUD Espacios ----------
class SpaceListView(ListView):
    model = Space
    template_name = "spaces/list.html"


class SpaceCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = Space
    form_class = SpaceForm
    template_name = "spaces/form.html"
    success_url = reverse_lazy("spaces_list")


class SpaceUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = Space
    form_class = SpaceForm
    template_name = "spaces/form.html"
    success_url = reverse_lazy("spaces_list")


class SpaceDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    model = Space
    template_name = "spaces/confirm_delete.html"
    success_url = reverse_lazy("spaces_list")


# ---------- CRUD Recursos ----------
class ResourceListView(ListView):
    model = Resource
    template_name = "resources/list.html"


class ResourceCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = Resource
    form_class = ResourceForm
    template_name = "resources/form.html"
    success_url = reverse_lazy("resources_list")


class ResourceUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = Resource
    form_class = ResourceForm
    template_name = "resources/form.html"
    success_url = reverse_lazy("resources_list")


class ResourceDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    model = Resource
    template_name = "resources/confirm_delete.html"
    success_url = reverse_lazy("resources_list")


# ---------- CRUD Carreras ----------
# ---------- CRUD Carreras ----------
class CarreraListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    model = Carrera
    template_name = "carreras/list.html"
    context_object_name = "object_list"

class CarreraCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = Carrera
    form_class = CarreraForm
    template_name = "carreras/form.html"
    success_url = reverse_lazy("carreras_list")

class CarreraUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = Carrera
    form_class = CarreraForm
    template_name = "carreras/form.html"
    success_url = reverse_lazy("carreras_list")

class CarreraDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    model = Carrera
    template_name = "carreras/confirm_delete.html"
    success_url = reverse_lazy("carreras_list")
    context_object_name = "object"


# ---------- CRUD Areas ----------
class AreaListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    model = Area
    template_name = "areas/list.html"
    context_object_name = "object_list"

class AreaCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = Area
    form_class = AreaForm
    template_name = "areas/form.html"
    success_url = reverse_lazy("areas_list")

class AreaUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = Area
    form_class = AreaForm
    template_name = "areas/form.html"
    success_url = reverse_lazy("areas_list")

class AreaDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    model = Area
    template_name = "areas/confirm_delete.html"
    success_url = reverse_lazy("areas_list")
    context_object_name = "object"


# ---------- Notificaciones ----------
@login_required
def notifications_view(request):
    qs = request.user.notifications.order_by("-created_at")
    if request.method == "POST":
        qs.update(is_read=True)
        return redirect("notifications")
    return render(request, "notifications/list.html", {"notifications": qs})


# ---------- Reportes (CSV con comentario y notas de aprobación) ----------
@login_required
@user_passes_test(can_export_reports)
def reports_view(request):
    """Vista para renderizar el formulario de reportes."""
    # Pasamos los espacios para el filtro
    context = {
        "spaces": Space.objects.all().order_by("name"),
        "is_coordinator": is_coordinator(request.user),
    }
    return render(request, "reports/index.html", context)

@login_required
@user_passes_test(can_export_reports)
def export_reservations_csv(request):
    """
    Exporta reservas a CSV separando 'Recursos solicitados' y 'Detalle recursos'
    del campo purpose (si vienen embebidos con ese formato).
    ?sep=semicolon (defecto) | comma | tab
    Filtros opcionales: start_date, end_date, status, space
    """
    sep = (request.GET.get("sep") or "semicolon").lower()
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    status_filter = request.GET.get("status")
    space_id = request.GET.get("space")

    if sep == "comma":
        delimiter = ","
    elif sep == "tab":
        delimiter = "\t"
    else:
        delimiter = ";"  # Excel en es-CL suele abrir mejor con ';'

    filename = f"reservas_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")  # BOM para Excel

    # Quote todo para evitar que ; o , rompan celdas
    writer = csv.writer(response, delimiter=delimiter, quoting=csv.QUOTE_ALL)

    # Metadata del reporte
    writer.writerow(["Reporte generado por", request.user.username])
    writer.writerow(["Fecha de generación", timezone.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])  # Línea en blanco separadora

    writer.writerow([
        "ID", "Usuario", "Area", "Carrera", "Espacio", "Inicio", "Fin", "Estado",
        "Motivo de solicitud", "Asistentes", "Recursos", "Notas aprobación/Rechazo", "Motivo Cancelación"
    ])

    def split_clean_purpose(purpose_raw: str):
        """
        Limpia el purpose quitando partes de legado (Resources/Detalle) para mostrar solo el motivo real.
        """
        if not purpose_raw:
            return ""
        base_parts = []
        for part in map(lambda s: s.strip(), purpose_raw.split("|")):
            low = part.lower()
            if low.startswith("recursos solicitados:") or low.startswith("detalle recursos:") or low.startswith("[cancelada por"):
                continue
            base_parts.append(part)
        return " | ".join(base_parts).strip(" |")

    # Optimización: incluir profile y sus relaciones + recursos
    qs = Reservation.objects.select_related(
        "user", "space", "user__profile", "user__profile__area", "user__profile__carrera"
    ).prefetch_related("resources_used", "resources_used__resource").all().order_by("start")

    # Aplicar filtros
    if start_date:
        qs = qs.filter(start__date__gte=start_date)
    if end_date:
        qs = qs.filter(end__date__lte=end_date)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if space_id:
        qs = qs.filter(space_id=space_id)

    for r in qs:
        # Limpiar motivo
        main_purpose = split_clean_purpose(r.purpose or "")
        main_purpose = main_purpose.replace("\r", " ").replace("\n", " ").strip()

        # Obtener recursos reales de la relación
        res_items = [str(rr) for rr in r.resources_used.all()]
        resources_str = ", ".join(res_items)

        # Notas admin
        appr = Approval.objects.filter(reservation=r).order_by("-id").first()
        approval_notes = (appr.notes or "") if appr else ""
        approval_notes = approval_notes.replace("\r", " ").replace("\n", " ").strip()
        
        # Motivo cancelación
        cancel_reason = (r.cancel_reason or "").replace("\r", " ").replace("\n", " ").strip()

        # Obtener Area/Carrera de forma segura
        area_name = "-"
        carrera_name = "-"
        if hasattr(r.user, 'profile') and r.user.profile:
            if r.user.profile.area:
                area_name = r.user.profile.area.name
            if r.user.profile.carrera:
                carrera_name = r.user.profile.carrera.name

        writer.writerow([
            r.id,
            r.user.username,
            area_name,
            carrera_name,
            r.space.name,
            r.start.strftime("%Y-%m-%d %H:%M"),
            r.end.strftime("%Y-%m-%d %H:%M"), # Full datetime for End
            r.get_status_display(),
            main_purpose,
            r.attendees_count,
            resources_str,
            approval_notes,
            cancel_reason
        ])

    return response

def resource_availability(request):
    """
    API para consultar disponibilidad de un recurso en un horario dado.
    GET params: resource_id, date (YYYY-MM-DD), end_date (opt), start (HH:MM), end (HH:MM)
    """
    resource_id = request.GET.get('resource_id')
    date_str = request.GET.get('date')
    end_date_str = request.GET.get('end_date') or date_str
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    if not all([resource_id, date_str, start_str, end_str]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        from .utils import check_resource_availability
        from datetime import datetime
        
        # Parse dates
        tz = timezone.get_current_timezone()
        
        # Helper para parsear
        def make_dt(d_str, t_str):
            full_str = f"{d_str} {t_str}"
            dt_naive = datetime.strptime(full_str, "%Y-%m-%d %H:%M")
            return timezone.make_aware(dt_naive, tz)
            
        start_dt = make_dt(date_str, start_str)
        end_dt = make_dt(end_date_str, end_str)
        
        resource = Resource.objects.get(pk=resource_id)
        available = check_resource_availability(resource, start_dt, end_dt)
        
        return JsonResponse({'available': available, 'total': resource.quantity})
        
    except Resource.DoesNotExist:
        return JsonResponse({'error': 'Resource not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def resource_availability_bulk(request):
    """
    API para consultar disponibilidad de TODOS los recursos activos.
    GET params: date (YYYY-MM-DD), end_date (opt), start (HH:MM), end (HH:MM)
    Returns: { "resources": { id: { "available": X, "total": Y }, ... } }
    """
    date_str = request.GET.get('date')
    end_date_str = request.GET.get('end_date') or date_str
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    if not all([date_str, start_str, end_str]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        from .utils import check_resource_availability
        from datetime import datetime
        
        tz = timezone.get_current_timezone()
        def make_dt(d_str, t_str):
            full_str = f"{d_str} {t_str}"
            dt_naive = datetime.strptime(full_str, "%Y-%m-%d %H:%M")
            return timezone.make_aware(dt_naive, tz)

        start_dt = make_dt(date_str, start_str)
        end_dt = make_dt(end_date_str, end_str)

        data = {}
        for res in Resource.objects.filter(is_active=True):
            available = check_resource_availability(res, start_dt, end_dt)
            data[res.id] = {
                "available": available,
                "total": res.quantity
            }
        
        return JsonResponse({'resources': data})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

        writer.writerow([
            r.id,
            f"{r.user.first_name} {r.user.last_name} ({r.user.username})",
            r.space.name,
            timezone.localtime(r.start).strftime("%Y-%m-%d %H:%M"),
            timezone.localtime(r.end).strftime("%Y-%m-%d %H:%M"),
            r.get_status_display(),
            main_purpose,
            r.attendees_count,
            resources_str,
            details_str,
            approval_notes
        ])

    return response


# ---------- Configuración (perfil) ----------
@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Preferencias guardadas.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "account/profile.html", {"form": form})


# --- Calendario de reservas (pantalla completa) ---
@login_required
def calendar_view(request):
    """Pantalla con calendario mensual/semanal de reservas.
    Usa availability_json para cargar eventos (opcionalmente filtrados por espacio).
    """
    spaces = Space.objects.filter(is_active=True).order_by("name")
    return render(request, "calendar/index.html", {"spaces": spaces})
