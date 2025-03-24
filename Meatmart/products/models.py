from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='category_images/', blank=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name

class Product(models.Model):
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_quantity = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    stock_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.0)]
    )
    image = models.ImageField(upload_to='product_images/')
    is_available = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

    def update_stock(self, new_quantity, change_type, reason, user):
        previous_quantity = self.stock_quantity
        self.stock_quantity = new_quantity
        self.save()

        # Create stock history entry
        StockHistory.objects.create(
            product=self,
            previous_quantity=previous_quantity,
            new_quantity=new_quantity,
            change_type=change_type,
            change_reason=reason,
            changed_by=user
        )

        # Check for low stock alert
        if hasattr(self, 'stock_alert') and self.stock_alert.is_active:
            if new_quantity <= self.stock_alert.threshold_quantity:
                self.notify_low_stock()

    def notify_low_stock(self):
        from django.utils import timezone
        from django.core.mail import send_mail
        from django.conf import settings

        alert = self.stock_alert
        # Only send notification if last notification was sent more than 24 hours ago
        if not alert.last_notification_sent or \
           (timezone.now() - alert.last_notification_sent).days >= 1:
            
            subject = f'Low Stock Alert: {self.name}'
            message = f'''
            Low stock alert for {self.name}
            Current stock: {self.stock_quantity}kg
            Threshold: {alert.threshold_quantity}kg
            Please restock soon.
            '''
            
            # Send email to seller
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.seller.email],
                fail_silently=True,
            )

            # Update last notification time
            alert.last_notification_sent = timezone.now()
            alert.save()

    def check_stock_availability(self, requested_quantity):
        return self.stock_quantity >= requested_quantity and self.is_available

class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('product', 'user')
    
    def __str__(self):
        return f"{self.user.email}'s review on {self.product.name}"

class Promotion(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.product.name} - {self.discount_percentage}% off"

class StockHistory(models.Model):
    STOCK_CHANGE_TYPES = [
        ('ADDITION', 'Stock Added'),
        ('REDUCTION', 'Stock Reduced'),
        ('ADJUSTMENT', 'Stock Adjusted'),
        ('SALE', 'Stock Sold'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_history')
    previous_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    new_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    change_type = models.CharField(max_length=20, choices=STOCK_CHANGE_TYPES)
    change_reason = models.TextField()
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Stock Histories'

    def __str__(self):
        return f"{self.product.name} - {self.change_type} at {self.created_at}"

class StockAlert(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='stock_alert')
    threshold_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    last_notification_sent = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Alert for {self.product.name} at {self.threshold_quantity}kg"
