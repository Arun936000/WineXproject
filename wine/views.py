from decimal import Decimal
import json
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
from datetime import timedelta
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import Product, ComboOffer, Cart, CartItem, Order, OrderItem, Payment, CustomUser, Offer
import random
import string
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


# Utility functions
def get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key, user=None)
    return cart

def admin_required(function=None):
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and u.user_type == 'admin',
        login_url='/auth/admin-login/'
    )
    if function:
        return actual_decorator(function)
    return actual_decorator

# Staff Required Decorator
def staff_required(function=None):
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and u.user_type in ['staff', 'admin'],
        login_url='/auth/staff-login/'
    )
    if function:
        return actual_decorator(function)
    return actual_decorator

# Home Page
def home(request):
    return render(request, 'base.html')

# Authentication Views
def admin_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.user_type == 'admin':
            login(request, user)
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid admin credentials")
            return redirect('admin_login') 

    return render(request, 'wine/auth/admin_login.html')

def is_staff_user(user):
    """Check if user is staff"""
    return user.is_authenticated and user.is_staff

# Staff Login View
def staff_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        print(f"\n{'='*50}")
        print(f"STAFF LOGIN ATTEMPT:")
        print(f"Username: {username}")
        print(f"Password length: {len(password)}")
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            print(f"✓ Authentication successful")
            print(f"User type: {user.user_type}")
            print(f"User is active: {user.is_active}")
            
            if user.user_type == 'staff':
                login(request, user)
                print(f"✓ Login successful! Redirecting to dashboard...")
                print(f"Session: {request.session.session_key}")
                return redirect('staff_dashboard')
            else:
                print(f"✗ User is not staff (type: {user.user_type})")
                messages.error(request, "This account is not authorized for staff access.")
        else:
            print(f"✗ Authentication failed")
            # Try to find user to see if they exist
            try:
                user = CustomUser.objects.get(username=username)
                print(f"User exists but password incorrect")
            except CustomUser.DoesNotExist:
                print(f"User does not exist")
            
            messages.error(request, "Invalid username or password.")
        
        return redirect('staff_login')
    
    return render(request, 'wine/auth/staff_login.html')


# Staff Login View
def staff_login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('staff_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_staff:
            login(request, user)
            if request.POST.get('remember'):
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # Browser session
            return redirect('staff_dashboard')
        else:
            context = {'error': 'Invalid staff credentials. Please try again.'}
            return render(request, 'staff/login.html', context)
    
    return render(request, 'staff/login.html')

# Staff Logout View
@login_required
@user_passes_test(is_staff_user)
def staff_logout_view(request):
    logout(request)
    return redirect('staff_login')



# Quick Status Update (AJAX)
@login_required
@user_passes_test(is_staff_user)
@require_POST
def quick_status_update(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('status')
        
        from .models import Order
        
        order = Order.objects.get(id=order_id)
        order.status = new_status
        order.updated_by = request.user.username  # Track which staff updated
        order.save()
        
        # Get updated counts
        counts = {
            'all': Order.objects.count(),
            'pending': Order.objects.filter(status='pending').count(),
            'preparing': Order.objects.filter(status='preparing').count(),
            'ready': Order.objects.filter(status='ready').count(),
        }
        
        return JsonResponse({
            'success': True,
            'status_display': order.get_status_display(),
            'new_counts': counts
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Get Order Counts (AJAX)
@login_required
@user_passes_test(is_staff_user)
def get_order_counts(request):
    from .models import Order
    
    counts = {
        'all': Order.objects.count(),
        'pending': Order.objects.filter(status='pending').count(),
        'preparing': Order.objects.filter(status='preparing').count(),
        'ready': Order.objects.filter(status='ready').count(),
    }
    return JsonResponse(counts)

# Get New Order Count (AJAX)
@login_required
@user_passes_test(is_staff_user)
def get_new_order_count(request):
    from .models import Order
    from django.utils import timezone
    from datetime import timedelta
    
    # Get orders created in the last minute
    one_minute_ago = timezone.now() - timedelta(minutes=1)
    new_orders_count = Order.objects.filter(
        status='pending',
        created_at__gte=one_minute_ago
    ).count()
    
    return JsonResponse({'new_orders': new_orders_count})



from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
import json

def customer_login(request):
    # If user is already authenticated, redirect based on user type
    if request.user.is_authenticated:
        if hasattr(request.user, 'user_type'):
            if request.user.user_type == 'customer':
                return redirect('customer_dashboard')
        return redirect('shop_home')
    
    # Store messages in session for JavaScript to access
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        # Validate input
        if not username:
            messages.error(request, 'Please enter your username or email')
        elif not password:
            messages.error(request, 'Please enter your password')
        else:
            # Try to authenticate
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # Check if user is a customer
                if hasattr(user, 'user_type') and user.user_type == 'customer':
                    login(request, user)
                    next_url = request.GET.get('next', 'customer_dashboard')
                    messages.success(request, f'Welcome back, {user.username}!')
                    return redirect(next_url)
                else:
                    messages.error(request, 'This account is not a customer account')
            else:
                messages.error(request, 'Invalid username or password')
    
    # Get messages as a list for JavaScript
    message_list = []
    for message in messages.get_messages(request):
        message_list.append({
            'text': str(message),
            'tags': message.tags
        })
    
    # Pass messages as JSON to template
    context = {
        'django_messages_json': json.dumps(message_list)
    }
    
    return render(request, 'wine/auth/customer_login.html', context)

def customer_signup(request):
    if request.user.is_authenticated:
        if request.user.user_type == 'customer':
            return redirect('customer_dashboard')
        else:
            return redirect('shop_home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        full_name = request.POST.get('full_name')
        
        # Validation
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request, 'wine/auth/customer_signup.html')
        
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return render(request, 'wine/auth/customer_signup.html')
        
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered')
            return render(request, 'wine/auth/customer_signup.html')
        
        # Create user but DON'T login automatically
        try:
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                user_type='customer'
            )
            
            # Send verification email or success message
            messages.success(request, 'Account created successfully! Please login to continue.')
            
            # Redirect to login page instead of auto-login
            return redirect('customer_login')
            
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
            return render(request, 'wine/auth/customer_signup.html')
    
    return render(request, 'wine/auth/customer_signup.html')

from django.contrib.auth.decorators import login_required
from django.db.models import Q

@login_required
def customer_dashboard(request):
    # Only allow customers to access this view
    if request.user.user_type != 'customer':
        return redirect('shop_home')
    
    # Get customer's orders
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    recent_orders = orders[:5]
    order_count = orders.count()
    completed_orders = orders.filter(status='completed').count()
    
    # Get customer's cart info
    cart = get_or_create_cart(request)
    cart_items = cart.items.all()
    cart_item_count = cart_items.count()
    cart_total = sum(item.get_total_price() for item in cart_items)
    
    # Get recommended products (based on order history or random)
    ordered_products = OrderItem.objects.filter(
        order__user=request.user
    ).values_list('product__category', flat=True).distinct()
    
    if ordered_products:
        recommended_products = Product.objects.filter(
            category__in=ordered_products,
            is_active=True
        ).exclude(stock=0).order_by('?')[:4]
    else:
        # Show random popular products for new customers
        recommended_products = Product.objects.filter(
            is_active=True,
            stock__gt=0
        ).order_by('?')[:4]
    
    context = {
        'recent_orders': recent_orders,
        'order_count': order_count,
        'completed_orders': completed_orders,
        'cart_item_count': cart_item_count,
        'cart_total': cart_total,
        'recommended_products': recommended_products,
    }
    
    return render(request, 'wine/customer/customer_dashboard.html', context)


@login_required
def customer_order_detail(request, order_id):
    # Only allow customers to access their own orders
    if request.user.user_type != 'customer':
        return redirect('shop_home')
    
    try:
        # Get the order and verify it belongs to the current user
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product', 'items__combo'), 
            id=order_id, 
            user=request.user
        )
        
        # Get all order items with details
        order_items = []
        for item in order.items.all():
            if item.product:
                item_name = item.product.name
                item_image = item.product.image.url if item.product.image else None
                item_category = item.product.category
            elif item.combo:
                item_name = f"{item.combo.name} (Combo)"
                item_image = item.combo.image.url if item.combo.image else None
                item_category = "Combo"
            else:
                item_name = "Item"
                item_image = None
                item_category = "Unknown"
            
            order_items.append({
                'id': item.id,
                'name': item_name,
                'quantity': item.quantity,
                'price': item.price,
                'total': item.get_total_price(),
                'image': item_image,
                'category': item_category,
            })
        
        context = {
            'order': order,
            'order_items': order_items,
        }
        
        return render(request, 'wine/customer/order_detail.html', context)
        
    except Order.DoesNotExist:
        messages.error(request, 'Order not found or you do not have permission to view it.')
        return redirect('customer_dashboard')


@login_required
def api_customer_order_detail(request, order_id):
    if request.user.user_type != 'customer':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        order_items = []
        
        for item in order.items.all():
            if item.product:
                item_name = item.product.name
            elif item.combo:
                item_name = f"{item.combo.name} (Combo)"
            else:
                item_name = "Item"
            
            order_items.append({
                'name': item_name,
                'quantity': item.quantity,
                'price': float(item.price),
                'total': float(item.get_total_price())
            })
        
        data = {
            'order_number': f"ORD-{str(order.id)[:8].upper()}",
            'status': order.status,
            'status_display': order.get_status_display(),
            'created_at': order.created_at.isoformat(),
            'total_amount': float(order.total_amount),
            'items': order_items,
        }
        
        return JsonResponse(data)
        
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)

        
@login_required
def user_logout(request):
    user_type = getattr(request.user, "user_type", None)

    logout(request)

    messages.success(request, "You have been logged out successfully.")

    if user_type == 'admin':
        return redirect('admin_login')
    elif user_type == 'staff':
        return redirect('staff_login')
    elif user_type == 'customer':
        return redirect('customer_login') 
    else:
        return redirect('home')

def get_dashboard_context():
    total_products = Product.objects.count()
    low_stock_products = Product.objects.filter(stock__lt=10).count()
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()

    end_date = timezone.now()
    start_date = end_date - timedelta(days=7)

    recent_orders = Order.objects.filter(
        created_at__gte=start_date,
        status__in=['completed', 'ready']
    )

    total_revenue = recent_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    top_products = Product.objects.annotate(
        total_sold=Sum('orderitem__quantity')
    ).order_by('-total_sold')[:5]

    products = Product.objects.all()
    staff_members = CustomUser.objects.filter(user_type='staff')

    offers = Offer.objects.all().order_by('-created_at')
    
    # Get out of stock products
    out_of_stock_products = Product.objects.filter(stock=0).count()

    return {
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_revenue': total_revenue,
        'top_products': top_products,
        'products': products,
        'staff_members': staff_members,
        'offers': offers, 
    }

@admin_required
def admin_dashboard(request):
    context = get_dashboard_context()
    context['active_section'] = request.GET.get('section', 'dashboard')
    return render(request, 'wine/admin_dashboard/dashboard.html', context)

@admin_required
def manage_products(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        if product_id:
            product = get_object_or_404(Product, id=product_id)
        else:
            product = Product()

        product.name = request.POST.get('name')
        product.description = request.POST.get('description')
        product.price = request.POST.get('price')
        product.stock = request.POST.get('stock')
        product.category = request.POST.get('category')

        if 'image' in request.FILES:
            product.image = request.FILES['image']

        try:
            product.save()
            messages.success(request, 'Product saved successfully!')
            return redirect(f"{reverse('manage_products')}?section=products")
        except Exception as e:
            messages.error(request, f'Error saving product: {str(e)}')

    context = get_dashboard_context()
    context['active_section'] = request.GET.get('section', 'products')
    return render(request, 'wine/admin_dashboard/dashboard.html', context)

@csrf_exempt
@admin_required
def delete_product(request, product_id):
    if request.method == "POST":
        try:
            product = Product.objects.get(id=product_id)
            product.delete()
            return JsonResponse({"success": True})
        except Product.DoesNotExist:
            return JsonResponse({"error": "Product not found"}, status=404)
    return JsonResponse({"error": "Invalid request"}, status=400)

@admin_required
def manage_staff(request):
    staff_members = CustomUser.objects.filter(user_type='staff')

    if request.method == 'POST':
        staff_id = request.POST.get('staff_id')
        username = request.POST.get('username')
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        password = request.POST.get('password')

        try:
            if staff_id:  
                staff = get_object_or_404(CustomUser, id=staff_id, user_type='staff')
                staff.username = username
                staff.email = email
                staff.full_name = full_name
                if password:
                    staff.set_password(password)
                    staff.raw_password = password   
            else:  
                if CustomUser.objects.filter(username=username).exists():
                    messages.error(request, f"Username '{username}' already exists.")
                    return redirect(reverse('admin_dashboard') + '?section=staff')

                staff = CustomUser(
                    username=username,
                    email=email,
                    full_name=full_name,
                    user_type='staff',
                )
                if password:
                    staff.set_password(password)
                    staff.raw_password = password   
                else:
                    password = "default123"
                    staff.set_password(password)
                    staff.raw_password = password  

            staff.save()
            messages.success(request, "Staff saved successfully!")

        except Exception as e:
            messages.error(request, f"Error saving staff: {str(e)}")
        
        return redirect(reverse('admin_dashboard') + '?section=staff')

    context = {
        'staff_members': staff_members,
        'active_section': 'staff'
    }
    return render(request, 'wine/admin_dashboard/dashboard.html', context)

@admin_required
def sales_report(request):
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        start_date = timezone.datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d')
    
    if request.GET.get('end_date'):
        end_date = timezone.datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d')
    
    orders = Order.objects.filter(
        created_at__range=[start_date, end_date],
        status__in=['completed', 'ready']
    )
    
    total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_orders = orders.count()
    
    daily_sales = orders.extra(
        select={'day': 'date(created_at)'}
    ).values('day').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('day')
    
    context = {
        'orders': orders,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'daily_sales': list(daily_sales),
    }
    
    return render(request, 'wine/admin_dashboard/sales_report.html', context)

@staff_required
def staff_dashboard(request):
    """Main staff dashboard view"""
    # Get counts
    all_orders = Order.objects.all()
    pending_count = all_orders.filter(status='pending').count()
    preparing_count = all_orders.filter(status='preparing').count()
    ready_count = all_orders.filter(status='ready').count()
    completed_count = all_orders.filter(status='completed').count()
    cancelled_count = all_orders.filter(status='cancelled').count()
    all_count = all_orders.count()
    
    # Get recent orders (last 20)
    recent_orders = Order.objects.all().order_by('-created_at')[:20]
    
    # Get products count
    products_count = Product.objects.filter(is_active=True).count()
    
    # Get customers count
    customers_count = CustomUser.objects.filter(user_type='customer').count()
    
    # Get today's summary for reports
    today = timezone.now().date()
    today_orders = Order.objects.filter(created_at__date=today).count()
    total_revenue = Order.objects.filter(
        created_at__date=today,
        status='completed'
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    context = {
        'all_count': all_count,
        'pending_count': pending_count,
        'preparing_count': preparing_count,
        'ready_count': ready_count,
        'completed_count': completed_count,
        'cancelled_count': cancelled_count,
        'recent_orders': recent_orders,
        'products_count': products_count,
        'customers_count': customers_count,
        'today_orders': today_orders,
        'total_revenue': total_revenue,
    }
    
    return render(request, 'wine/staff_dashboard/dashboard.html', context)

# API endpoint for dashboard stats
@staff_required
def api_dashboard_stats(request):
    """API endpoint for dashboard statistics"""
    try:
        all_orders = Order.objects.all()
        
        data = {
            'total_orders': all_orders.count(),
            'pending': all_orders.filter(status='pending').count(),
            'preparing': all_orders.filter(status='preparing').count(),
            'ready': all_orders.filter(status='ready').count(),
            'completed': all_orders.filter(status='completed').count(),
            'cancelled': all_orders.filter(status='cancelled').count(),
        }
        
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@staff_required
def api_orders(request):
    try:
        status_filter = request.GET.get('status', 'all')
        order_type_filter = request.GET.get('type', 'all')
        date_filter = request.GET.get('date', 'all')
        search_query = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 12))

        orders = Order.objects.all().order_by('-created_at')

        if status_filter != 'all':
            orders = orders.filter(status=status_filter)

        if order_type_filter != 'all':
            orders = orders.filter(order_type=order_type_filter)

        if date_filter != 'all':
            today = timezone.now().date()
            if date_filter == 'today':
                orders = orders.filter(created_at__date=today)
            elif date_filter == 'yesterday':
                yesterday = today - timedelta(days=1)
                orders = orders.filter(created_at__date=yesterday)
            elif date_filter == 'week':
                week_ago = today - timedelta(days=7)
                orders = orders.filter(created_at__date__gte=week_ago)
            elif date_filter == 'month':
                month_ago = today - timedelta(days=30)
                orders = orders.filter(created_at__date__gte=month_ago)

        if search_query:
            orders = orders.filter(
                Q(phone_number__icontains=search_query) |
                Q(token_number__icontains=search_query) |
                Q(id__icontains=search_query)
            )

        total = orders.count()
        pages = (total + limit - 1) // limit
        start = (page - 1) * limit
        end = start + limit

        paginated_orders = orders[start:end]

        orders_data = []

        for order in paginated_orders:
            customer_name = "Guest Customer"
            if order.user:
                customer_name = order.user.get_full_name() or order.user.username
            elif order.phone_number:
                customer_name = f"Customer {order.phone_number[-4:]}"

            orders_data.append({
                'id': str(order.id),
                'order_number': f"ORD-{str(order.id)[:8].upper()}",
                'customer_name': customer_name,
                'phone_number': order.phone_number or "N/A",
                'token_number': order.token_number or "",
                'order_type': order.order_type,
                'status': order.status,
                'status_display': order.get_status_display(),
                'total_amount': float(order.total_amount),
                'payment_method': getattr(order, 'payment_method', 'Cash'),
                'created_at': order.created_at.isoformat(),
                'items_count': order.items.count(),
                'items': [
                    {
                        'name': item.product.name if item.product else
                               item.combo.name if item.combo else "Item",
                        'quantity': item.quantity,
                        'price': float(item.price)
                    }
                    for item in order.items.all()
                ]
            })

        return JsonResponse({
            'success': True,
            'orders': orders_data,
            'total': total,
            'pages': pages,
            'current_page': page
        })

    except Exception as e:
        print("API ORDERS ERROR:", str(e))
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Error fetching orders'
        }, status=500)


@staff_required
def api_order_detail(request, order_id):
    """API endpoint for single order detail"""
    try:
        order = get_object_or_404(Order.objects.prefetch_related('items__product', 'items__combo'), id=order_id)
        
        # Get customer name
        customer_name = "Guest Customer"
        if order.user:
            if order.user.get_full_name():
                customer_name = order.user.get_full_name()
            else:
                customer_name = order.user.username
        
        # Prepare order items
        order_items = []
        for item in order.items.all():
            item_name = ""
            if item.product:
                item_name = f"{item.product.name}"
            elif item.combo:
                item_name = f"{item.combo.name} (Combo)"
            else:
                item_name = "Item"
            
            order_items.append({
                'name': item_name,
                'quantity': item.quantity,
                'price': float(item.price),
                'total': float(item.quantity * item.price)
            })
        
        data = {
            'id': str(order.id),
            'order_number': f"ORD-{str(order.id)[:8].upper()}",
            'customer_name': customer_name,
            'phone_number': order.phone_number or "N/A",
            'token_number': order.token_number or "",
            'order_type': order.order_type,
            'status': order.status,
            'status_display': order.get_status_display(),
            'total_amount': float(order.total_amount),
            'payment_method': getattr(order, 'payment_method', 'Cash'),
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat() if order.updated_at else None,
            'items_count': order.items.count(),
            'items': order_items,
            'notes': getattr(order, 'notes', "")
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'message': 'Failed to load order details'
        }, status=500)

# API endpoint for order receipt
@staff_required
def api_order_receipt(request, order_id):
    """API endpoint for order receipt"""
    try:
        order = get_object_or_404(Order.objects.prefetch_related('items__product', 'items__combo'), id=order_id)
        
        # Get customer name
        customer_name = "Guest Customer"
        if order.user:
            if order.user.get_full_name():
                customer_name = order.user.get_full_name()
            else:
                customer_name = order.user.username
        
        # Prepare receipt data
        receipt_data = {
            'order': order,
            'order_number': f"ORD-{str(order.id)[:8].upper()}",
            'customer_name': customer_name,
            'order_items': [],
            'subtotal': 0,
            'tax': 0,
            'total': float(order.total_amount),
            'created_at': order.created_at.strftime('%d/%m/%Y %H:%M'),
            'now': timezone.now().strftime('%d/%m/%Y %H:%M')
        }
        
        # Calculate items and subtotal
        for item in order.items.all():
            item_name = ""
            if item.product:
                item_name = f"{item.product.name}"
            elif item.combo:
                item_name = f"{item.combo.name} (Combo)"
            else:
                item_name = "Item"
            
            item_total = float(item.quantity * item.price)
            receipt_data['subtotal'] += item_total
            
            receipt_data['order_items'].append({
                'name': item_name,
                'quantity': item.quantity,
                'price': float(item.price),
                'total': item_total,
                'notes': item.notes if hasattr(item, 'notes') else ""
            })
        
        # Calculate tax (assuming 10% tax)
        receipt_data['tax'] = receipt_data['subtotal'] * 0.1
        
        # Try to render receipt template
        try:
            receipt_html = render_to_string('wine/receipts/order_receipt.html', receipt_data)
        except:
            # Fallback template
            receipt_html = f"""
            <div style="font-family: 'Courier New', monospace; padding: 20px;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <h2 style="margin: 0;">WINE X</h2>
                    <p style="margin: 5px 0;">Wine Shop & Bar</p>
                    <p style="margin: 5px 0;">123 Wine Street, City</p>
                    <p style="margin: 5px 0;">Phone: +91 9876543210</p>
                </div>
                <hr>
                <div style="margin-bottom: 15px;">
                    <p><strong>Order #:</strong> {receipt_data['order_number']}</p>
                    <p><strong>Date:</strong> {receipt_data['created_at']}</p>
                    {f'<p><strong>Token #:</strong> {order.token_number}</p>' if order.token_number else ''}
                    <p><strong>Customer:</strong> {receipt_data['customer_name']}</p>
                    <p><strong>Phone:</strong> {order.phone_number or 'N/A'}</p>
                </div>
                <hr>
                <div style="margin: 15px 0;">
                    <h4>Items:</h4>
                    {''.join([f'<p>{item["name"]} x{item["quantity"]} = ₹{item["total"]:.2f}</p>' for item in receipt_data['order_items']])}
                </div>
                <hr>
                <div style="text-align: right; font-size: 18px; margin-top: 20px;">
                    <p><strong>TOTAL: ₹{receipt_data['total']:.2f}</strong></p>
                </div>
                <div style="text-align: center; margin-top: 30px; font-size: 14px;">
                    <p>Thank you for your order!</p>
                    <p>Visit again!</p>
                </div>
                <div style="text-align: center; margin-top: 20px; padding-top: 10px; border-top: 1px dashed #000;">
                    <p style="font-size: 12px;">Receipt ID: {str(order.id)[:8].upper()}</p>
                    <p style="font-size: 12px;">Printed: {receipt_data['now']}</p>
                </div>
            </div>
            """
        
        return JsonResponse({
            'success': True,
            'receipt_html': receipt_html,
            'order_number': receipt_data['order_number'],
            'total': receipt_data['total']
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Failed to generate receipt'
        }, status=500)

# views.py
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

@login_required
@require_POST
def api_update_order_status(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
        new_status = request.POST.get('status') or json.loads(request.body).get('status')
        
        # Validate status transition
        valid_transitions = {
            'pending': ['preparing', 'cancelled'],
            'preparing': ['ready', 'pending', 'cancelled'],
            'ready': ['completed', 'preparing', 'cancelled'],
            'completed': ['ready'],
            'cancelled': ['pending']
        }
        
        if new_status not in valid_transitions.get(order.status, []):
            return JsonResponse({
                'success': False,
                'error': f'Invalid status transition from {order.status} to {new_status}'
            }, status=400)
        
        order.status = new_status
        order.save()
        
        # Update TV display if needed
        # broadcast_order_update(order)
        
        return JsonResponse({
            'success': True,
            'message': f'Order status updated to {new_status}',
            'order': {
                'id': str(order.id),
                'status': order.status,
                'status_display': order.get_status_display()
            }
        })
        
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Add this import at the top
import json
from django.core.serializers import serialize
from django.http import JsonResponse, HttpResponse
from decimal import Decimal

# Add these API endpoints in views.py:

@staff_required
def api_products(request):
    """API endpoint for products (for staff dashboard)"""
    try:
        products = Product.objects.filter(is_active=True).order_by('name')
        
        products_data = []
        for product in products:
            products_data.append({
                'id': str(product.id),
                'name': product.name,
                'description': product.description or '',
                'price': float(product.price),
                'category': product.category,
                'stock': product.stock,
                'image': request.build_absolute_uri(product.image.url) if product.image else None,
                'is_active': product.is_active,
                'is_available': product.is_in_stock()
            })
        
        return JsonResponse(products_data, safe=False)
    except Exception as e:
        print(f"API Products Error: {str(e)}")
        return JsonResponse({'error': str(e), 'success': False}, status=500, safe=False)

@staff_required
def api_all_products(request):
    """API endpoint for all products including inactive (for billing)"""
    try:
        products = Product.objects.all().order_by('name')
        
        products_data = []
        for product in products:
            products_data.append({
                'id': str(product.id),
                'name': product.name,
                'description': product.description or '',
                'price': float(product.price),
                'category': product.category,
                'stock': product.stock,
                'image': request.build_absolute_uri(product.image.url) if product.image else None,
                'is_active': product.is_active,
                'is_available': product.is_in_stock(),
                'category_display': product.get_category_display()
            })
        
        return JsonResponse(products_data, safe=False)
    except Exception as e:
        print(f"API All Products Error: {str(e)}")
        return JsonResponse({'error': str(e), 'success': False}, status=500, safe=False)

@staff_required
def api_offers(request):
    """API endpoint for offers (for staff dashboard)"""
    try:
        offers = Offer.objects.filter(is_active=True).order_by('-created_at')
        
        offers_data = []
        for offer in offers:
            offers_data.append({
                'id': str(offer.id),
                'title': offer.title,
                'description': offer.description,
                'offer_type': offer.offer_type,
                'discount_percentage': float(offer.discount_percentage) if offer.discount_percentage else 0,
                'start_date': offer.start_date.isoformat(),
                'end_date': offer.end_date.isoformat(),
                'image': request.build_absolute_uri(offer.image.url) if offer.image else None,
                'products': [{'id': str(p.id), 'name': p.name} for p in offer.products.all()],
                'combo_offers': [{'id': str(c.id), 'name': c.name} for c in offer.combo_offers.all()],
                'total_original_price': float(offer.total_original_price) if hasattr(offer, 'total_original_price') else 0,
                'total_discounted_price': float(offer.total_discounted_price) if hasattr(offer, 'total_discounted_price') else 0,
                'is_valid': offer.is_valid()
            })
        
        return JsonResponse(offers_data, safe=False)
    except Exception as e:
        print(f"API Offers Error: {str(e)}")
        return JsonResponse({'error': str(e), 'success': False}, status=500, safe=False)

@staff_required
def api_combos(request):
    """API endpoint for combo offers"""
    try:
        combos = ComboOffer.objects.filter(is_active=True).order_by('name')
        
        combos_data = []
        for combo in combos:
            combo_items = []
            for item in combo.combo_items.all():
                combo_items.append({
                    'product_id': str(item.product.id),
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.product.price)
                })
            
            combos_data.append({
                'id': str(combo.id),
                'name': combo.name,
                'description': combo.description,
                'discount_percentage': float(combo.discount_percentage),
                'discounted_price': float(combo.get_discounted_price()),
                'image': request.build_absolute_uri(combo.image.url) if combo.image else None,
                'items': combo_items,
                'is_active': combo.is_active
            })
        
        return JsonResponse(combos_data, safe=False)
    except Exception as e:
        print(f"API Combos Error: {str(e)}")
        return JsonResponse({'error': str(e), 'success': False}, status=500, safe=False)

import random
from django.utils import timezone
from django.db import transaction

@staff_required
@require_POST
@transaction.atomic
def api_create_manual_order(request):
    """API endpoint for creating manual billing orders"""
    try:
        data = json.loads(request.body)
        
        customer_name = data.get('customer_name', 'Walk-in Customer')
        phone_number = data.get('phone_number', '')
        order_type = data.get('order_type', 'pickup')
        payment_method = data.get('payment_method', 'cash')
        status = data.get('status', 'completed')
        items = data.get('items', [])
        subtotal = Decimal(str(data.get('subtotal', 0)))
        tax = Decimal(str(data.get('tax', 0)))
        total_amount = Decimal(str(data.get('total_amount', 0)))
        amount_received = Decimal(str(data.get('amount_received', 0)))
        change_given = Decimal(str(data.get('change_given', 0)))
        
        # Generate token number for pickup orders
        token_number = None
        if order_type == 'pickup':
            # Generate a 4-digit token number
            token_number = str(random.randint(1000, 9999))
            
            # Check if token already exists for today
            today = timezone.now().date()
            existing_tokens = Order.objects.filter(
                token_number=token_number,
                created_at__date=today,
                order_type='pickup'
            ).exists()
            
            # If token exists, generate a new one
            while existing_tokens:
                token_number = str(random.randint(1000, 9999))
                existing_tokens = Order.objects.filter(
                    token_number=token_number,
                    created_at__date=today,
                    order_type='pickup'
                ).exists()
        
        # Create order with token number
        order = Order.objects.create(
            phone_number=phone_number,
            order_type=order_type,
            total_amount=total_amount,
            status=status,
            token_number=token_number
        )
        
        # Add customer name to delivery_address field (or create a new field)
        if customer_name != 'Walk-in Customer':
            order.delivery_address = f"Customer: {customer_name}"
            order.save()
        
        # Create order items
        for item in items:
            product_id = item.get('product_id')
            product_name = item.get('product_name', 'Product')
            quantity = item.get('quantity', 1)
            price = Decimal(str(item.get('price', 0)))
            
            try:
                product = Product.objects.get(id=product_id)
                
                # Create order item
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=price
                )
                
                # Update stock
                if product.stock >= quantity:
                    product.stock = product.stock - quantity
                    product.save()
                else:
                    raise Exception(f"Insufficient stock for {product.name}")
                
            except Product.DoesNotExist:
                # Create order item without product reference
                OrderItem.objects.create(
                    order=order,
                    quantity=quantity,
                    price=price
                )
        
        # Create payment record
        Payment.objects.create(
            order=order,
            amount=total_amount,
            status='completed',
            payment_method=payment_method,
            transaction_id=f'CASH-{order.id.hex[:8].upper()}'
        )
        
        return JsonResponse({
            'success': True,
            'order_id': str(order.id),
            'order_number': f"ORD-{str(order.id)[:8].upper()}",
            'token_number': token_number,
            'message': f'Manual order created successfully{" with token #" + token_number if token_number else ""}'
        })
        
    except Exception as e:
        print(f"Create Manual Order Error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    
@staff_required
def api_recent_orders(request):
    """API endpoint for recent orders"""
    try:
        recent_orders = Order.objects.all().order_by('-created_at')[:10]
        
        orders_data = []
        for order in recent_orders:
            customer_name = "Guest Customer"
            if order.user:
                customer_name = order.user.get_full_name() or order.user.username
            elif order.phone_number:
                customer_name = f"Customer {order.phone_number[-4:]}"
            
            orders_data.append({
                'id': str(order.id),
                'order_number': f"ORD-{str(order.id)[:8].upper()}",
                'customer_name': customer_name,
                'phone_number': order.phone_number or "N/A",
                'token_number': order.token_number or "",
                'order_type': order.order_type,
                'status': order.status,
                'status_display': order.get_status_display(),
                'total_amount': float(order.total_amount),
                'created_at': order.created_at.isoformat(),
                'items_count': order.items.count()
            })
        
        return JsonResponse({'success': True, 'orders': orders_data})
    except Exception as e:
        print(f"Recent Orders Error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# API endpoint for customers
@staff_required
def api_customers(request):
    """API endpoint for customers"""
    try:
        customers = CustomUser.objects.filter(user_type='customer').order_by('-date_joined')
        
        customers_data = []
        for customer in customers:
            # Get order stats for this customer
            orders = Order.objects.filter(user=customer)
            total_orders = orders.count()
            total_spent = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            
            customers_data.append({
                'id': str(customer.id),
                'name': customer.get_full_name() or customer.username,
                'email': customer.email,
                'phone': customer.phone or '',
                'address': customer.address or '',
                'total_orders': total_orders,
                'total_spent': float(total_spent),
                'date_joined': customer.date_joined.strftime('%Y-%m-%d')
            })
        
        return JsonResponse(customers_data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# API endpoint for today's reports
@staff_required
def api_reports_today(request):
    """API endpoint for today's reports"""
    try:
        today = timezone.now().date()
        
        # Get today's orders
        today_orders = Order.objects.filter(created_at__date=today)
        total_orders = today_orders.count()
        
        # Calculate total revenue
        completed_orders = today_orders.filter(status='completed')
        total_revenue = completed_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Calculate average order value
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        data = {
            'total_orders': total_orders,
            'total_revenue': float(total_revenue),
            'average_order': float(avg_order_value),
            'pending_orders': today_orders.filter(status='pending').count(),
            'preparing_orders': today_orders.filter(status='preparing').count(),
            'ready_orders': today_orders.filter(status='ready').count(),
            'completed_orders': completed_orders.count()
        }
        
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from datetime import timedelta
from wine.models import Order, Product, CustomUser
# from wine.decorators import staff_required
from django.contrib.admin.views.decorators import staff_member_required

@staff_required
def manage_orders(request):
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    order_type_filter = request.GET.get('type', 'all')
    date_filter = request.GET.get('date', 'all')
    search_query = request.GET.get('search', '')
    
    # Start with all orders
    orders = Order.objects.all().order_by('-created_at')
    
    # Debug: Print initial count
    print(f"Initial orders count: {orders.count()}")
    
    # Apply status filter (only if not 'all')
    if status_filter and status_filter != 'all':
        orders = orders.filter(status=status_filter)
        print(f"After status filter ({status_filter}): {orders.count()}")
    
    # Apply order type filter (only if not 'all')
    if order_type_filter and order_type_filter != 'all':
        orders = orders.filter(order_type=order_type_filter)
        print(f"After order type filter ({order_type_filter}): {orders.count()}")
    
    # Apply date filter (only if not 'all')
    if date_filter and date_filter != 'all':
        if date_filter == 'today':
            orders = orders.filter(created_at__date=timezone.now().date())
        elif date_filter == 'yesterday':
            yesterday = timezone.now().date() - timedelta(days=1)
            orders = orders.filter(created_at__date=yesterday)
        elif date_filter == 'week':
            week_ago = timezone.now().date() - timedelta(days=7)
            orders = orders.filter(created_at__date__gte=week_ago)
        print(f"After date filter ({date_filter}): {orders.count()}")
    
    # Apply search filter
    if search_query:
        orders = orders.filter(
            Q(phone_number__icontains=search_query) |
            Q(token_number__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__full_name__icontains=search_query) |
            Q(id__icontains=search_query)
        )
        print(f"After search filter: {orders.count()}")
    
    # Get counts for ALL orders (unfiltered)
    all_orders = Order.objects.all()
    all_count = all_orders.count()
    pending_count = all_orders.filter(status='pending').count()
    preparing_count = all_orders.filter(status='preparing').count()
    ready_count = all_orders.filter(status='ready').count()
    completed_count = all_orders.filter(status='completed').count()
    cancelled_count = all_orders.filter(status='cancelled').count()
    
    # Get count for current filtered view (before pagination)
    filtered_count = orders.count()
    
    # Pagination
    paginator = Paginator(orders, 20)  # Show 20 orders per page
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)
    
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        status = request.POST.get('status')
        
        if order_id and status:
            order = get_object_or_404(Order, id=order_id)
            order.status = status
            order.save()
            
            messages.success(request, f'Order #{order.id} status updated to {status}')
            return redirect('manage_orders')
    
    # Get choices
    status_choices = [
        ('pending', 'Pending'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    order_type_choices = [
        ('delivery', 'Home Delivery'),
        ('pickup', 'Pickup from Store'),
    ]
    
    context = {
        'orders': page_obj,  # Paginated orders
        'page_obj': page_obj,  # Also pass for pagination controls
        'all_count': all_count,
        'pending_count': pending_count,
        'preparing_count': preparing_count,
        'ready_count': ready_count,
        'completed_count': completed_count,
        'cancelled_count': cancelled_count,
        'filtered_count': filtered_count,
        'status_filter': status_filter,
        'order_type_filter': order_type_filter,
        'date_filter': date_filter,
        'search_query': search_query,
        'status_choices': status_choices,
        'order_type_choices': order_type_choices,
    }
    
    print(f"Total filtered orders: {filtered_count}")
    print(f"Orders on current page: {page_obj.object_list.count()}")
    print(f"Date filter value: {date_filter}")
    print(f"Status filter value: {status_filter}")
    
    return render(request, 'wine/staff_dashboard/manage_orders.html', context)

@staff_required
def order_detail(request, order_id):
    """View for detailed order information"""
    order = get_object_or_404(Order.objects.prefetch_related('items__product', 'items__combo'), id=order_id)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        if status and status != order.status:
            order.status = status
            order.save()
            
            messages.success(request, f'Order status updated to {status}')
            return redirect('order_detail', order_id=order.id)
    
    # Get item names for each order item
    order_items_with_names = []
    for item in order.items.all():
        item_name = ""
        if item.product:
            item_name = f"{item.product.name}"
        elif item.combo:
            item_name = f"{item.combo.name} (Combo)"
        else:
            item_name = f"Item #{item.id}"
        
        order_items_with_names.append({
            'item': item,
            'name': item_name,
            'quantity': item.quantity,
            'price': item.price,
            'total': item.get_total_price(),
            'notes': item.notes if hasattr(item, 'notes') else ""
        })
    
    context = {
        'order': order,
        'order_items_with_names': order_items_with_names,
    }
    
    return render(request, 'wine/staff_dashboard/order_detail.html', context)

@staff_required
def view_products(request):
    # Staff can view products but not edit
    products = Product.objects.filter(is_active=True).order_by('category', 'name')
    
    # Get categories
    categories = Product.objects.values_list('category', flat=True).distinct()
    
    context = {
        'products': products,
        'categories': categories,
    }
    return render(request, 'wine/staff_dashboard/view_products.html', context)

@staff_required
def manage_customers(request):
    # Get customers with orders
    customers = CustomUser.objects.filter(user_type='customer').order_by('-date_joined')
    
    # Get search filter
    search_query = request.GET.get('search', '')
    if search_query:
        customers = customers.filter(
            Q(username__icontains=search_query) |
            Q(full_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    context = {
        'customers': customers,
        'search_query': search_query,
    }
    return render(request, 'wine/staff_dashboard/manage_customers.html', context)

@staff_required
def customer_orders(request, customer_id):
    customer = get_object_or_404(CustomUser, id=customer_id, user_type='customer')
    orders = Order.objects.filter(user=customer).order_by('-created_at')
    
    context = {
        'customer': customer,
        'orders': orders,
    }
    return render(request, 'wine/staff_dashboard/customer_orders.html', context)

@csrf_exempt
@staff_required
def quick_status_update(request):
    """AJAX endpoint for quick status updates"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order_id = data.get('order_id')
            status = data.get('status')
            
            order = get_object_or_404(Order, id=order_id)
            order.status = status
            order.save()
            
            return JsonResponse({
                'success': True,
                'order_id': str(order.id),
                'status': status,
                'status_display': order.get_status_display(),
                'message': f'Order #{order.id} updated to {status}'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@staff_required
def print_receipt(request, order_id):
    """View for printing order receipt"""
    order = get_object_or_404(Order.objects.prefetch_related('items__product', 'items__combo'), id=order_id)
    
    context = {
        'order': order,
    }
    
    return render(request, 'wine/staff_dashboard/print_receipt.html', context)

from django.db.models import Q, Sum
from django.utils import timezone

def shop_home(request):
    # Get all active products
    products = Product.objects.filter(is_active=True)

    # Get active and valid offers with prefetch for performance
    current_offers = Offer.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).prefetch_related('products', 'combo_offers')

    # Get category choices from model
    product_categories = Product.CATEGORY_CHOICES

    # Get filter parameters from request
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('search', '')
    offer_type = request.GET.get('offer_type', '')

    # Apply filters if provided
    if category_filter:
        products = products.filter(category=category_filter)

    if offer_type:
        # Filter offers by type and also show products from those offers
        current_offers = current_offers.filter(offer_type=offer_type)
        # Get product IDs from the filtered offers
        offer_product_ids = current_offers.values_list('products__id', flat=True).distinct()
        # Filter products to show only those included in the offers
        products = products.filter(id__in=offer_product_ids)

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
        # Also filter offers by search query
        current_offers = current_offers.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Get cart using the utility function
    cart = get_or_create_cart(request)
    cart_items = cart.items.all()
    cart_count = cart_items.count()  # Use count() instead of Sum
    
    # Show dashboard link if customer is logged in
    if request.user.is_authenticated and request.user.user_type == 'customer':
        # Only show message if not already shown
        if not request.GET.get('added'):
            messages.info(request, f"Welcome back! Check your <a href='{reverse('customer_dashboard')}' class='alert-link'>dashboard</a> for personalized recommendations.", extra_tags='safe')

    context = {
        'products': products,
        'current_offers': current_offers,
        'product_categories': product_categories,
        'selected_category': category_filter,
        'search_query': search_query,
        'offer_type': offer_type,
        'cart_count': cart_count,
        'user_type': request.user.user_type if request.user.is_authenticated else None,
    }
    return render(request, 'wine/shop/home.html', context)

def combo_detail(request, combo_id):
    combo = get_object_or_404(ComboOffer, id=combo_id, is_active=True)
    
    context = {
        'combo': combo,
    }
    return render(request, 'wine/shop/combo_detail.html', context)

# Cart Views
def view_cart(request):
    cart = get_or_create_cart(request)
    cart_items = cart.items.all()
    
    # Calculate totals using Decimal
    subtotal = sum(item.get_total_price() for item in cart_items)
    tax = subtotal * Decimal('0.05')  # 5% GST as Decimal
    service_fee = Decimal('39.00')
    total = subtotal + tax + service_fee
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'tax': tax,
        'service_fee': service_fee,
        'total': total,
    }
    return render(request, 'wine/shop/cart.html', context)

@require_POST
def add_to_cart(request, product_id):
    try:
        # Try to get product by UUID
        product = get_object_or_404(Product, id=product_id, is_active=True)
    except ValueError:
        # If product_id is not a valid UUID, try as integer
        product = get_object_or_404(Product, pk=product_id, is_active=True)
    
    # Check stock availability
    if product.stock < 1:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f'Sorry, {product.name} is out of stock!'
            })
        messages.error(request, f'Sorry, {product.name} is out of stock!')
        return redirect('shop_home')
    
    cart = get_or_create_cart(request)
    
    # Check if product already in cart
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    
    if not created:
        # Check if adding more would exceed stock
        if cart_item.quantity + 1 > product.stock:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f'Only {product.stock} units of {product.name} available!'
                })
            messages.error(request, f'Only {product.stock} units of {product.name} available!')
            return redirect('view_cart')
        cart_item.quantity += 1
        cart_item.save()
    
    # Get updated cart count
    cart_count = cart.items.count()
    
    # If it's an AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'{product.name} added to cart!',
            'cart_count': cart_count
        })
    
    messages.success(request, f'{product.name} added to cart!')
    
    # Return to the same page with product filters preserved
    referer = request.META.get('HTTP_REFERER', 'shop_home')
    return redirect(f"{referer}?added=true")

# ADD THE MISSING DECREASE_QUANTITY FUNCTION
@require_POST
def decrease_quantity(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart=get_or_create_cart(request))
    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
    else:
        cart_item.delete()
        messages.success(request, 'Item removed from cart')
    return redirect('view_cart')

# ADD THE MISSING INCREASE_QUANTITY FUNCTION
@require_POST
def increase_quantity(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart=get_or_create_cart(request))
    
    if cart_item.product:
        # Check stock before increasing
        if cart_item.quantity + 1 > cart_item.product.stock:
            messages.error(request, f'Only {cart_item.product.stock} units available!')
            return redirect('view_cart')
    
    cart_item.quantity += 1
    cart_item.save()
    return redirect('view_cart')

@require_POST
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart=get_or_create_cart(request))
    cart_item.delete()
    messages.success(request, 'Item removed from cart')
    return redirect('view_cart')

# Checkout Views
def checkout(request):
    cart = get_or_create_cart(request)
    cart_items = cart.items.all()
    
    if not cart_items.exists():
        return redirect('view_cart')
    
    # Validate stock before checkout
    for item in cart_items:
        if item.product and item.product.stock < item.quantity:
            messages.error(request, f'Not enough stock for {item.product.name}. Only {item.product.stock} available.')
            return redirect('view_cart')
        elif item.combo:
            for combo_item in item.combo.combo_items.all():
                required_stock = item.quantity * combo_item.quantity
                if combo_item.product.stock < required_stock:
                    messages.error(request, f'Not enough stock for {combo_item.product.name} in combo.')
                    return redirect('view_cart')
    
    # Calculate totals using Decimal
    subtotal = sum(item.get_total_price() for item in cart_items)
    tax = subtotal * Decimal('0.05')
    service_fee = Decimal('39.00')
    total = subtotal + tax + service_fee
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'tax': tax,
        'service_fee': service_fee,
        'total': total,
    }
    return render(request, 'wine/shop/checkout.html', context)

@csrf_exempt
def process_order(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'})

    try:
        data = json.loads(request.body)

        phone_number = data.get('phone_number')
        payment_method = data.get('payment_method')
        order_type = data.get('order_type')
        delivery_address = data.get('delivery_address')

        cart = get_or_create_cart(request)

        if not cart.items.exists():
            return JsonResponse({'success': False, 'message': 'Cart is empty'})

        total_amount = sum(item.get_total_price() for item in cart.items.all())

        # Delivery validation
        if order_type == "delivery" and not delivery_address:
            return JsonResponse({'success': False, 'message': 'Delivery address required'})

        with transaction.atomic():

            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                phone_number=phone_number,
                order_type=order_type,
                total_amount=total_amount,
                delivery_address=delivery_address if order_type == "delivery" else None,
            )

            # Delivery logic
            if order_type == "delivery":
                order.expected_delivery = timezone.now().date() + timedelta(days=1)
                order.status = "pending"

            # Pickup logic
            elif order_type == "pickup":
                token_no = random.randint(1000, 9999)
                order.token_number = token_no
                order.status = "preparing"

            order.save()

            # Save order items + reduce stock
            for item in cart.items.all():

                if item.product:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        quantity=item.quantity,
                        price=item.product.price
                    )
                    item.product.stock -= item.quantity
                    item.product.save()

                elif item.combo:
                    OrderItem.objects.create(
                        order=order,
                        combo=item.combo,
                        quantity=item.quantity,
                        price=item.combo.get_discounted_price()
                    )
                    for c in item.combo.combo_items.all():
                        c.product.stock -= item.quantity * c.quantity
                        c.product.save()

            # Payment record
            Payment.objects.create(
                order=order,
                amount=total_amount,
                payment_method=payment_method,
                status="completed" if payment_method != "cod" else "pending"
            )

            cart.items.all().delete()

        return JsonResponse({
            'success': True,
            'order_id': str(order.id)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    context = {
        'order': order,
    }
    return render(request, 'wine/shop/order_confirmation.html', context)

def track_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Build tracking steps
    steps = []

    if order.order_type == "delivery":
        steps = [
            {"key": "pending", "label": "Order Received"},
            {"key": "confirmed", "label": "Order Confirmed"},
            {"key": "preparing", "label": "Order Being Packed"},
            {"key": "out_for_delivery", "label": "Out for Delivery"},
            {"key": "delivered", "label": "Delivered"}
        ]
    else:  # pickup
        steps = [
            {"key": "pending", "label": "Order Received"},
            {"key": "confirmed", "label": "Order Confirmed"},
            {"key": "preparing", "label": "Preparing Order"},
            {"key": "ready", "label": "Ready for Pickup"},
            {"key": "completed", "label": "Picked Up"}
        ]

    # Determine current step index
    current_step_index = 0
    for i, s in enumerate(steps):
        if s["key"] == order.status:
            current_step_index = i

    context = {
        "order": order,
        "steps": steps,
        "current_step_index": current_step_index,
    }

    return render(request, "wine/shop/track_order.html", context)


# Offer Management
@admin_required
def manage_offers(request):
    offers = Offer.objects.all().order_by('-created_at')
    
    if request.method == 'POST':
        offer_id = request.POST.get('offer_id')
        if offer_id:
            offer = get_object_or_404(Offer, id=offer_id)
        else:
            offer = Offer()

        offer.title = request.POST.get('title')
        offer.description = request.POST.get('description')
        offer.offer_type = request.POST.get('offer_type')
        offer.discount_percentage = request.POST.get('discount_percentage')
        offer.start_date = request.POST.get('start_date')
        offer.end_date = request.POST.get('end_date')
        offer.is_active = request.POST.get('is_active') == 'on'

        if 'image' in request.FILES:
            offer.image = request.FILES['image']

        try:
            offer.save()
            
            # Handle many-to-many relationships
            product_ids = request.POST.getlist('products')
            combo_ids = request.POST.getlist('combo_offers')
            
            offer.products.set(Product.objects.filter(id__in=product_ids))
            offer.combo_offers.set(ComboOffer.objects.filter(id__in=combo_ids))
            
            messages.success(request, 'Offer saved successfully!')
            return redirect(f"{reverse('manage_offers')}?section=offers")
        except Exception as e:
            messages.error(request, f'Error saving offer: {str(e)}')

    context = get_dashboard_context()
    context['offers'] = offers
    context['active_section'] = 'offers'
    return render(request, 'wine/admin_dashboard/dashboard.html', context)

@csrf_exempt
@admin_required
def delete_offer(request, offer_id):
    if request.method == "POST":
        try:
            offer = Offer.objects.get(id=offer_id)
            offer.delete()
            return JsonResponse({"success": True})
        except Offer.DoesNotExist:
            return JsonResponse({"error": "Offer not found"}, status=404)
    return JsonResponse({"error": "Invalid request"}, status=400)


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

def add_offer_to_cart(request, offer_id):
    try:
        offer = get_object_or_404(Offer, id=offer_id)
        
        # Check if offer is valid (active and within date range)
        now = timezone.now()
        if not (offer.is_active and offer.start_date <= now <= offer.end_date):
            messages.error(request, 'This offer is no longer available')
            return redirect('shop_home')
        
        # Check if offer has sufficient stock
        if not offer.has_sufficient_stock():
            messages.error(request, 'Sorry, this offer is out of stock')
            return redirect('shop_home')
        
        # Get or create cart (for both authenticated and anonymous users)
        if request.user.is_authenticated:
            cart, created = Cart.objects.get_or_create(user=request.user)
        else:
            # For anonymous users, use session-based cart
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key
            cart, created = Cart.objects.get_or_create(session_key=session_key, user=None)
        
        # Check if this offer is already in cart
        existing_offer_item = CartItem.objects.filter(cart=cart, offer=offer).first()
        
        if existing_offer_item:
            # If offer already in cart, increase quantity if possible
            if existing_offer_item.can_increase_quantity():
                existing_offer_item.quantity += 1
                existing_offer_item.save()
                messages.success(request, f'"{offer.title}" quantity increased!')
            else:
                messages.info(request, f'"{offer.title}" is already in your cart at maximum quantity')
        else:
            # Create cart item for the offer
            CartItem.objects.create(
                cart=cart,
                offer=offer,
                quantity=1
            )
            messages.success(request, f'"{offer.title}" added to cart!')
        
        return redirect('shop_home')
        
    except Exception as e:
        messages.error(request, 'An error occurred while adding the offer to cart')
        return redirect('shop_home')



import razorpay
from django.conf import settings
from django.http import JsonResponse

def create_razorpay_order(request):
    if request.method == "POST":
        data = json.loads(request.body)

        raw_amount = data["amount"]

        amount_float = round(float(raw_amount), 2)

        amount = int(amount_float * 100)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET_KEY))

        razorpay_order = client.order.create(dict(
            amount=amount,
            currency="INR",
            payment_capture=1
        ))

        return JsonResponse({
            "order_id": razorpay_order["id"],
            "amount": amount,
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID
        })


# ==================== KIOSK VIEWS ====================

def kiosk_view(request):
    """
    Kiosk view for in-shop ordering
    """
    # Get all available products
    products = Product.objects.filter(stock__gt=0, is_active=True).order_by('category', 'name')
    
    # Get current valid offers
    current_offers = Offer.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).prefetch_related('products', 'combo_offers')
    
    # Get cart for kiosk (anonymous session)
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    
    # Create or get kiosk cart
    cart, created = Cart.objects.get_or_create(
        session_key=session_key + "_kiosk",
        user=None
    )
    
    # Calculate cart totals
    cart_items = cart.items.all()
    cart_total = sum(item.get_total_price() for item in cart_items)
    cart_count = cart_items.count()
    
    context = {
        'products': products,
        'current_offers': current_offers,
        'product_categories': Product.CATEGORY_CHOICES,
        'cart_total': cart_total,
        'cart_count': cart_count,
    }
    
    return render(request, 'wine/shop/shopscreen.html', context)

def generate_token():
    """Generate a 4-digit token for kiosk orders"""
    return ''.join(random.choices(string.digits, k=4))

@csrf_exempt
def kiosk_process_order(request):
    """
    Process kiosk orders with online payment
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Get cart items from kiosk session
            session_key = request.session.session_key + "_kiosk"
            cart = get_object_or_404(Cart, session_key=session_key, user=None)
            cart_items = cart.items.all()
            
            if not cart_items.exists():
                return JsonResponse({
                    'success': False, 
                    'message': 'Cart is empty'
                })
            
            # Validate stock before processing
            for item in cart_items:
                if item.product:
                    if item.product.stock < item.quantity:
                        return JsonResponse({
                            'success': False,
                            'message': f'Insufficient stock for {item.product.name}'
                        })
            
            # Calculate totals
            subtotal = sum(item.get_total_price() for item in cart_items)
            tax = subtotal * Decimal('0.05')
            service_fee = Decimal('39.00')
            total = subtotal + tax + service_fee
            
            # Create order
            with transaction.atomic():
                # Generate token
                token = generate_token()
                
                # Create order for pickup (always pickup for kiosk)
                order = Order.objects.create(
                    user=None,  # Anonymous user for kiosk
                    phone_number="0000000000",  # Default phone for kiosk
                    order_type='pickup',
                    total_amount=total,
                    delivery_address=None,  # No delivery for kiosk
                    token_number=token,
                    status='preparing',
                )
                
                # Add items to order and update stock
                for item in cart_items:
                    if item.product:
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            quantity=item.quantity,
                            price=item.product.price
                        )
                        # Update stock
                        item.product.stock -= item.quantity
                        item.product.save()
                    
                    elif item.combo:
                        OrderItem.objects.create(
                            order=order,
                            combo=item.combo,
                            quantity=item.quantity,
                            price=item.combo.get_discounted_price()
                        )
                        # Update stock for combo items
                        for combo_item in item.combo.combo_items.all():
                            required_stock = item.quantity * combo_item.quantity
                            combo_item.product.stock -= required_stock
                            combo_item.product.save()
                    
                    elif item.offer:
                        # Handle offers
                        OrderItem.objects.create(
                            order=order,
                            product=None,
                            combo=None,
                            quantity=item.quantity,
                            price=item.offer.total_discounted_price
                        )
                
                # Create payment record
                Payment.objects.create(
                    order=order,
                    amount=total,
                    status='completed',
                    payment_method='online',
                    transaction_id=data.get('payment_id', 'kiosk_' + str(uuid.uuid4())[:8])
                )
                
                # Clear cart
                cart.items.all().delete()
            
            return JsonResponse({
                'success': True,
                'order_id': str(order.id),
                'token': token
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': str(e)
            })
    
    return JsonResponse({
        'success': False, 
        'message': 'Invalid request'
    })

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def kiosk_add_to_cart(request):
    """Kiosk-specific add to cart endpoint"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_type = data.get('type')  # 'product' or 'offer'
            item_id = data.get('id')
            
            if item_type == 'product':
                # Use your existing add_to_cart function
                product = get_object_or_404(Product, id=item_id)
                return add_to_cart_kiosk(request, product.id)
            elif item_type == 'offer':
                # Use your existing add_offer_to_cart function
                return add_offer_to_cart_kiosk(request, item_id)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request'
    })

def kiosk_get_cart(request):
    """Get kiosk cart data"""
    try:
        # Get kiosk cart (session + "_kiosk")
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key + "_kiosk"
        cart = Cart.objects.filter(session_key=session_key, user=None).first()
        
        if not cart:
            return JsonResponse({
                'success': True,
                'cart_items': [],
                'cart_count': 0,
                'cart_total': 0
            })
        
        cart_items = []
        for item in cart.items.all():
            cart_items.append({
                'id': str(item.id),
                'name': item.get_item_name(),
                'quantity': item.quantity,
                'price': float(item.get_price()),
                'total': float(item.get_total_price())
            })
        
        cart_total = sum(item.get_total_price() for item in cart.items.all())
        cart_count = cart.items.count()
        
        return JsonResponse({
            'success': True,
            'cart_items': cart_items,
            'cart_count': cart_count,
            'cart_total': float(cart_total)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

def add_to_cart_kiosk(request, product_id):
    """Wrapper for existing add_to_cart for kiosk"""
    try:
        product = get_object_or_404(Product, id=product_id)
        
        # Check stock
        if product.stock < 1:
            return JsonResponse({
                'success': False,
                'message': f'{product.name} is out of stock!'
            })
        
        # Get kiosk cart
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key + "_kiosk"
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            user=None
        )
        
        # Add to cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': 1}
        )
        
        if not created:
            if cart_item.quantity + 1 > product.stock:
                return JsonResponse({
                    'success': False,
                    'message': f'Only {product.stock} units available'
                })
            cart_item.quantity += 1
            cart_item.save()
        
        # Get updated cart count
        cart_count = cart.items.count()
        
        return JsonResponse({
            'success': True,
            'message': f'{product.name} added to cart!',
            'cart_count': cart_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

def add_offer_to_cart_kiosk(request, offer_id):
    """Wrapper for existing add_offer_to_cart for kiosk"""
    try:
        offer = get_object_or_404(Offer, id=offer_id)
        
        # Check if offer is valid
        if not offer.is_valid:
            return JsonResponse({
                'success': False,
                'message': 'This offer is no longer available'
            })
        
        # Check stock
        if not offer.has_sufficient_stock():
            return JsonResponse({
                'success': False,
                'message': 'This offer is out of stock'
            })
        
        # Get kiosk cart
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key + "_kiosk"
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            user=None
        )
        
        # Add to cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            offer=offer,
            defaults={'quantity': 1}
        )
        
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        
        # Get updated cart count
        cart_count = cart.items.count()
        
        return JsonResponse({
            'success': True,
            'message': f'{offer.title} added to cart!',
            'cart_count': cart_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
    


from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from wine.models import Order

@csrf_exempt  # For simple public access
def order_tracking(request):
    """Public order tracking page for customers"""
    order = None
    token = ""
    
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        if token:
            # Remove '#' if entered
            if token.startswith('#'):
                token = token[1:]
            try:
                order = Order.objects.get(token_number=token)
            except Order.DoesNotExist:
                order = None
    
    context = {
        'order': order,
        'token': token,
        'search_performed': request.method == 'POST',
    }
    
    return render(request, 'wine/order_tracking.html', context)


def order_tracking_detail(request, token):
    """Direct link for order tracking with token"""
    # Remove '#' if present
    if token.startswith('#'):
        token = token[1:]
    
    try:
        order = Order.objects.get(token_number=token)
    except Order.DoesNotExist:
        order = None
    
    context = {
        'order': order,
        'token': token,
    }
    
    return render(request, 'wine/order_tracking_detail.html', context)



from django.views.decorators.cache import cache_control
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse

@staff_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def tv_display(request):
    """TV display screen - show all active orders"""
    
    # Get ALL active orders (not completed/cancelled)
    active_orders = Order.objects.exclude(
        status__in=['completed', 'cancelled']
    ).prefetch_related('items__product', 'items__combo')
    
    # Sort: ready -> preparing -> pending, then by creation time
    status_priority = {'ready': 1, 'preparing': 2, 'pending': 3}
    ordered_orders = sorted(
        list(active_orders),
        key=lambda x: (status_priority.get(x.status, 99), x.created_at)
    )
    
    # Limit to 20 orders maximum for performance
    ordered_orders = ordered_orders[:20]
    
    # Count by status
    pending_count = sum(1 for o in ordered_orders if o.status == 'pending')
    preparing_count = sum(1 for o in ordered_orders if o.status == 'preparing')
    ready_count = sum(1 for o in ordered_orders if o.status == 'ready')
    total_active = len(ordered_orders)
    
    context = {
        'orders': ordered_orders,
        'single_mode': False,
        'now': timezone.now(),
        'total_active': total_active,
        'pending_count': pending_count,
        'preparing_count': preparing_count,
        'ready_count': ready_count,
    }
    
    if request.GET.get('ajax') == 'true':
        # Render just the orders grid portion
        from django.template.loader import render_to_string
        orders_html = render_to_string('wine/components/orders_grid.html', context)
        
        return HttpResponse(orders_html)
    
    return render(request, 'wine/tv_display.html', context)

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

@login_required
def staff_logout(request):
    logout(request)
    return redirect('staff_login')  


# In your views.py, add this function:
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Order
from datetime import datetime, timedelta

@login_required
def staff_reports(request):
    """Simple reports view for staff"""
    # Get date filters
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Get order counts
    total_orders = Order.objects.count()
    today_orders = Order.objects.filter(created_at__date=today).count()
    week_orders = Order.objects.filter(created_at__date__gte=week_ago).count()
    month_orders = Order.objects.filter(created_at__date__gte=month_ago).count()
    
    # Get orders by status
    status_counts = {}
    for status_code, status_name in Order.STATUS_CHOICES:
        status_counts[status_name] = Order.objects.filter(status=status_code).count()
    
    # Get recent orders
    recent_orders = Order.objects.all().order_by('-created_at')[:20]
    
    # Calculate total revenue
    total_revenue = Order.objects.filter(payment_status='completed').aggregate(
        total=models.Sum('total_amount')
    )['total'] or 0
    
    context = {
        'today': today,
        'total_orders': total_orders,
        'today_orders': today_orders,
        'week_orders': week_orders,
        'month_orders': month_orders,
        'status_counts': status_counts,
        'recent_orders': recent_orders,
        'total_revenue': total_revenue,
    }
    
    return render(request, 'staff/reports.html', context)


# @staff_required
# @cache_control(no_cache=True, must_revalidate=True, no_store=True)
# def tv_display_single(request, order_id=None):
#     """TV display showing single order in large format"""
#     if order_id:
#         order = get_object_or_404(Order, id=order_id)
#         orders = [order]
#     else:
#         # Get the oldest ready order, or oldest preparing order
#         order = Order.objects.filter(
#             status__in=['ready', 'preparing']
#         ).order_by(
#             'status',  # 'ready' comes before 'preparing' alphabetically
#             'created_at'
#         ).first()
        
#         if order:
#             orders = [order]
#         else:
#             orders = []
    
#     context = {
#         'orders': orders,
#         'single_mode': True,
#         'now': timezone.now(),
#     }
    
#     return render(request, 'wine/tv_display.html', context)