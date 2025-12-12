from decimal import Decimal
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model


# -------------------- CUSTOM USER --------------------
class CustomUser(AbstractUser):
    USER_TYPES = (
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('customer', 'Customer'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='customer')
    
    full_name = models.CharField(max_length=200, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    raw_password = models.CharField(max_length=128, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.user_type = 'admin'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.user_type})"


User = get_user_model()


# -------------------- PRODUCT --------------------
class Product(models.Model):
    CATEGORY_CHOICES = (
        ('whisky', 'Whisky'),
        ('vodka', 'Vodka'),
        ('beer', 'Beer'),
        ('wine', 'Wine'),
        ('rum', 'Rum'),
        ('gin', 'Gin'),
        ('tequila', 'Tequila'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def is_in_stock(self):
        return self.stock > 0
    
    def get_stock_status(self):
        if self.stock == 0:
            return 'out_of_stock'
        elif self.stock < 10:
            return 'low_stock'
        else:
            return 'in_stock'

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


# -------------------- COMBO OFFERS --------------------
class ComboOffer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField()
    products = models.ManyToManyField(Product, through='ComboItem')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    image = models.ImageField(upload_to='combos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    def get_discounted_price(self):
        total_price = sum(item.product.price * item.quantity for item in self.combo_items.all())
        discount_decimal = self.discount_percentage / Decimal('100')
        return total_price * (Decimal('1') - discount_decimal)
    
    def __str__(self):
        return self.name


class ComboItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    combo = models.ForeignKey(ComboOffer, on_delete=models.CASCADE, related_name='combo_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)


# -------------------- CART --------------------
class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# -------------------- OFFER --------------------
class Offer(models.Model):
    OFFER_TYPES = (
        ('today', "Today's Offer"),
        ('combo', 'Combo Offer'),
        ('discount', 'Discount Offer'),
        ('special', 'Special Day Offer'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPES)
    products = models.ManyToManyField(Product, blank=True)
    combo_offers = models.ManyToManyField(ComboOffer, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='offers/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} ({self.get_offer_type_display()})"
    
    def is_valid(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date

    @property
    def total_original_price(self):
        total = Decimal('0')
        for product in self.products.all():
            total += product.price
        for combo in self.combo_offers.all():
            total += combo.get_discounted_price()
        return total
    
    @property
    def total_discounted_price(self):
        if self.discount_percentage:
            discount_amount = (self.total_original_price * self.discount_percentage) / Decimal('100')
            return self.total_original_price - discount_amount
        return self.total_original_price

    def has_sufficient_stock(self):
        for product in self.products.all():
            if product.stock < 1:
                return False
        for combo in self.combo_offers.all():
            for combo_item in combo.combo_items.all():
                if combo_item.product.stock < combo_item.quantity:
                    return False
        return True


# -------------------- CART ITEMS --------------------
class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    combo = models.ForeignKey(ComboOffer, on_delete=models.CASCADE, null=True, blank=True)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    
    def get_total_price(self):
        if self.product:
            return self.product.price * Decimal(str(self.quantity))
        elif self.combo:
            return self.combo.get_discounted_price() * Decimal(str(self.quantity))
        elif self.offer:
            return self.offer.total_discounted_price * Decimal(str(self.quantity))
        return Decimal('0')
    
    def can_increase_quantity(self):
        if self.product:
            return self.quantity < self.product.stock
        
        elif self.combo:
            for combo_item in self.combo.combo_items.all():
                required_stock = (self.quantity + 1) * combo_item.quantity
                if combo_item.product.stock < required_stock:
                    return False
            return True
        
        elif self.offer:
            return self.offer.has_sufficient_stock()

        return False
    
    def get_item_name(self):
        if self.product:
            return self.product.name
        elif self.combo:
            return self.combo.name
        elif self.offer:
            return self.offer.title
        return "Unknown Item"


# -------------------- ORDER --------------------
class Order(models.Model):
    ORDER_TYPES = (
        ('delivery', 'Home Delivery'),
        ('pickup', 'Pickup from Store'),
    )

    ORDER_STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready for Pickup'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    # Add these as class attributes
    STATUS_CHOICES = ORDER_STATUS
    ORDER_TYPE_CHOICES = ORDER_TYPES
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='orders')
    phone_number = models.CharField(max_length=15)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, default='delivery')
    delivery_address = models.TextField(blank=True, null=True)
    token_number = models.CharField(max_length=10, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=15, choices=ORDER_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.id}"
    
    # In your models.py Order class
    def get_status_timeline(self):
        timeline = []
        
        # Define all possible steps
        steps = [
            {
                'name': 'Order Placed',
                'description': 'Your order has been received',
                'status': 'pending',
                'time': self.created_at if self.status != 'cancelled' else None
            },
            {
                'name': 'Order Confirmed',
                'description': 'We\'ve confirmed your order',
                'status': 'confirmed',
                'time': None
            },
            {
                'name': 'Processing',
                'description': 'Preparing your items',
                'status': 'processing',
                'time': None
            }
        ]
        
        # Add delivery/pickup specific steps
        if self.order_type == 'delivery':
            steps.extend([
                {
                    'name': 'Out for Delivery',
                    'description': 'Your order is on the way',
                    'status': 'out_for_delivery',
                    'time': None
                },
                {
                    'name': 'Delivered',
                    'description': 'Order delivered successfully',
                    'status': 'delivered',
                    'time': None
                }
            ])
        else:  # pickup
            steps.extend([
                {
                    'name': 'Ready for Pickup',
                    'description': 'Your order is ready',
                    'status': 'ready',
                    'time': None
                },
                {
                    'name': 'Picked Up',
                    'description': 'Order collected successfully',
                    'status': 'completed',
                    'time': None
                }
            ])
        
        # Determine completed and current steps
        status_order = ['pending', 'confirmed', 'processing', 'out_for_delivery', 'ready', 'delivered', 'completed']
        
        try:
            current_index = status_order.index(self.status)
        except ValueError:
            current_index = 0
        
        for i, step in enumerate(steps):
            step_copy = step.copy()
            step_copy['completed'] = i < current_index
            step_copy['current'] = i == current_index
            timeline.append(step_copy)
        
        return timeline


# -------------------- ORDER ITEMS --------------------
class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    combo = models.ForeignKey(ComboOffer, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    
    def get_total_price(self):
        return self.price * Decimal(str(self.quantity))
    
    # ADD THIS METHOD
    def get_item_name(self):
        """Get the name of the item"""
        if self.product:
            return f"{self.product.name}"
        elif self.combo:
            return f"{self.combo.name} (Combo)"
        else:
            # Check if there's an offer or other type
            return f"Item #{self.id}"

# -------------------- PAYMENT --------------------
class Payment(models.Model):
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    PAYMENT_METHODS = (
        ('upi', 'UPI'),
        ('card', 'Card'),
        ('cash', 'Cash'),
        ('online', 'Online Payment'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS, default='online')
    transaction_id = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.transaction_id} - {self.status}"
