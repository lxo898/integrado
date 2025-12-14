from .utils import is_coordinator
from .models import Notification

def notifications(request):
    """
    Agrega a todas las plantillas:
    - notif_unread_count: cantidad de no leídas
    - notif_unread_list: últimas 3 no leídas (para toasts)
    - is_coordinator: booleano
    """
    ctx = {
        "is_coordinator": is_coordinator(request.user),
        "notif_unread_count": 0,
        "notif_unread_list": []
    }
    
    if request.user.is_authenticated:
        qs = Notification.objects.filter(user=request.user, is_read=False).order_by("-created_at")
        ctx["notif_unread_count"] = qs.count()
        ctx["notif_unread_list"] = qs[:3]
        
    return ctx

