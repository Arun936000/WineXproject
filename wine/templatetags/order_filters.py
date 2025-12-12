# wine/templatetags/order_filters.py
from django import template

register = template.Library()

@register.filter
def filter_status(queryset, status):
    """Filter orders by status"""
    if hasattr(queryset, 'filter'):
        return queryset.filter(status=status)
    return [order for order in queryset if order.status == status]