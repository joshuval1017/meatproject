from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator

# Create your models here.

class DeliveryProfile(models.Model):
    VEHICLE_TYPES = [
        ('BIKE', 'Motorcycle/Scooter'),
        ('BICYCLE', 'Bicycle'),
        ('CAR', 'Car'),
        ('VAN', 'Van'),
    ]

    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('BUSY', 'Busy'),
        ('BREAK', 'On Break'),
        ('OFFLINE', 'Not Available'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delivery_profile')
    vehicle_type = models.CharField(max_length=10, choices=VEHICLE_TYPES, default='BIKE')
    vehicle_number = models.CharField(max_length=15, default='')
    license_number = models.CharField(max_length=20, default='')
    current_location = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OFFLINE')
    is_verified = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_deliveries = models.IntegerField(default=0)
    successful_deliveries = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_status_change = models.DateTimeField(auto_now=True)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    phone = models.CharField(max_length=15, default='')
    license_image = models.ImageField(upload_to='delivery_documents/licenses/', null=True, blank=True)

    # Profile management fields
    profile_picture = models.ImageField(upload_to='delivery_profiles/', null=True, blank=True)
    address = models.TextField(blank=True, default='')
    id_proof = models.ImageField(upload_to='delivery_documents/id_proofs/', null=True, blank=True)
    vehicle_registration = models.ImageField(upload_to='delivery_documents/vehicle_registrations/', null=True, blank=True)
    id_verified = models.BooleanField(default=False)
    vehicle_verified = models.BooleanField(default=False)
    emergency_contact = models.CharField(max_length=15, blank=True)
    bank_account = models.CharField(max_length=20, blank=True)
    ifsc_code = models.CharField(max_length=11, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)

    @property
    def is_available(self):
        return self.status == 'AVAILABLE'

    def __str__(self):
        return f"{self.user.get_full_name()}'s Delivery Profile"

    class Meta:
        verbose_name = 'Delivery Profile'
        verbose_name_plural = 'Delivery Profiles'
