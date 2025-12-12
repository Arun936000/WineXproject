from .models import CartItem
from django.db.models import Sum

def cart_count(request):
    cart_count = 0

    try:
        if request.user.is_authenticated:
            cart_count = CartItem.objects.filter(
                cart__user=request.user
            ).aggregate(total=Sum('quantity'))['total'] or 0
        else:
            session_key = request.session.session_key
            if session_key:
                cart_count = CartItem.objects.filter(
                    cart__session_key=session_key
                ).aggregate(total=Sum('quantity'))['total'] or 0

    except Exception as e:
        cart_count = 0
        print("Cart Count Error:", e)   # ✅ For debugging

    return {
        'cart_count': cart_count
    }
