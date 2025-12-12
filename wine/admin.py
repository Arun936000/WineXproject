from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Product, CartItem, Offer

admin.site.register(Product)
admin.site.register(CartItem)
admin.site.register(Offer)


class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display = ('username', 'email', 'full_name', 'user_type', 'is_staff')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'email')}),
        ('User Type', {'fields': ('user_type',)}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'full_name', 'user_type',
                'password1', 'password2', 'is_staff', 'is_active'
            ),
        }),
    )

    search_fields = ('username', 'email', 'full_name')
    ordering = ('username',)



admin.site.register(CustomUser, CustomUserAdmin)
