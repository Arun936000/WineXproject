from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),
    
    # Authentication URLs
    path('auth/admin-login/', views.admin_login, name='admin_login'),
    path('auth/staff-login/', views.staff_login, name='staff_login'),
    path('auth/login/', views.customer_login, name='customer_login'),
    path('auth/signup/', views.customer_signup, name='customer_signup'),
    path('auth/logout/', views.user_logout, name='user_logout'),
    path('staff-logout/', views.staff_logout, name='staff_logout'),
    
    # Admin Dashboard URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/products/', views.manage_products, name='manage_products'),
    path('admin-dashboard/staff/', views.manage_staff, name='manage_staff'),
    path('admin-dashboard/sales-report/', views.sales_report, name='sales_report'),
    path("delete_product/<uuid:product_id>/", views.delete_product, name="delete_product"),
    path('admin-dashboard/offers/', views.manage_offers, name='manage_offers'),
    path("delete_offer/<uuid:offer_id>/", views.delete_offer, name="delete_offer"),

    
    # Staff Dashboard URLs
    path('staff-dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff-dashboard/orders/', views.manage_orders, name='manage_orders'),
    path('staff-dashboard/orders/<uuid:order_id>/', views.order_detail, name='order_detail'),
    path('staff/orders/', views.manage_orders, name='manage_orders'),
    path('staff/orders/<uuid:order_id>/', views.order_detail, name='order_detail'),
    path('staff/orders/quick-update/', views.quick_status_update, name='quick_status_update'),
    path('staff/orders/<uuid:order_id>/print/', views.print_receipt, name='print_receipt'),
    path('staff/products/', views.view_products, name='view_products'),
    path('staff/customers/', views.manage_customers, name='manage_customers'),
    path('staff/customers/<uuid:customer_id>/orders/', views.customer_orders, name='customer_orders'),

    path('api/dashboard/stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/orders/', views.api_orders, name='api_orders'),
    path('api/orders/recent/', views.api_recent_orders, name='api_recent_orders'),
    path('api/orders/<uuid:order_id>/', views.api_order_detail, name='api_order_detail'),
     path('api/orders/<uuid:order_id>/receipt/', views.api_order_receipt, name='api_order_receipt'),
    # path('api/orders/<uuid:order_id>/status/', views.api_update_order_status, name='api_update_order_status'),
    path('api/orders/<uuid:order_id>/update-status/', views.api_update_order_status, name='update_order_status'),
    path('api/orders/create-manual/', views.api_create_manual_order, name='api_create_manual_order'),

    path('api/products/', views.api_products, name='api_products'),
    path('api/products/all/', views.api_all_products, name='api_all_products'),
    
    # Offers and Combos API URLs
    path('api/offers/', views.api_offers, name='api_offers'),
    path('api/combos/', views.api_combos, name='api_combos'),
    
    # Customers API
    path('api/customers/', views.api_customers, name='api_customers'),
    
    # Reports API
    path('api/reports/today/', views.api_reports_today, name='api_reports_today'),
    
    # Add this missing URL:
    path('staff/reports/', views.staff_reports, name='staff_reports'),
    
    # Customer urls
    path('customer/customer_dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('customer/orders/<uuid:order_id>/', views.customer_order_detail, name='customer_order_detail'),
    path('api/customer/orders/<uuid:order_id>/', views.api_customer_order_detail, name='api_customer_order_detail'),

    # Shop URLs
    path('shop/', views.shop_home, name='shop_home'),
    # path('shop/product/<uuid:product_id>/', views.product_detail, name='product_detail'),
    path('add-offer-to-cart/<uuid:offer_id>/', views.add_offer_to_cart, name='add_offer_to_cart'),
    path('shop/combo/<uuid:combo_id>/', views.combo_detail, name='combo_detail'),
    
    # Cart URLs 
    path('shop/cart/', views.view_cart, name='view_cart'),
    path('shop/cart/add/<uuid:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('shop/cart/increase/<uuid:item_id>/', views.increase_quantity, name='increase_quantity'),
    path('shop/cart/decrease/<uuid:item_id>/', views.decrease_quantity, name='decrease_quantity'),
    path('shop/cart/remove/<uuid:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('order-confirmation/<uuid:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('track-order/<uuid:order_id>/', views.track_order, name='track_order'),

    
    # Checkout URLs
    path('shop/checkout/', views.checkout, name='checkout'),
    path('shop/checkout/process/', views.process_order, name='process_order'),
    # path('shop/order-confirmation/<uuid:order_id>/', views.order_confirmation, name='order_confirmation'),

    path("create_razorpay_order/", views.create_razorpay_order, name="create_razorpay_order"),

    path('kiosk/', views.kiosk_view, name='kiosk_view'),
    path('kiosk-add-to-cart/', views.kiosk_add_to_cart, name='kiosk_add_to_cart'),
    path('kiosk-get-cart/', views.kiosk_get_cart, name='kiosk_get_cart'),
    path('kiosk-process-order/', views.kiosk_process_order, name='kiosk_process_order'),


    path('track-order/', views.order_tracking, name='order_tracking'),
    path('track-order/<str:token>/', views.order_tracking_detail, name='order_tracking_detail'),


    path('staff/tv-display/', views.tv_display, name='tv_display'),
    # path('staff/tv-display/single/', views.tv_display_single, name='tv_display_single'),
    # path('staff/tv-display/single/<uuid:order_id>/', views.tv_display_single, name='tv_display_single_order'),
]