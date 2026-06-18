from .models import Notification

def unread_notifications(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
    else:
        count = 0

    return {"notifications_unread": count}
from .models import CartItem

def cart_count(request):
    if request.user.is_authenticated:
        count = CartItem.objects.filter(user_id=request.user.id).count()
    else:
        count = 0
    return {'cart_count': count}

