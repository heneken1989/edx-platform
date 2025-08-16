from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PaymentTransaction(models.Model):
    """
    Model to store payment transaction information
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(decimal_places=2, max_digits=10)
    currency = models.CharField(max_length=3, default='VND')
    txn_ref = models.CharField(max_length=100, unique=True)
    payment_method = models.CharField(max_length=50, default='vnpay')
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled')
        ],
        default='pending'
    )
    payment_type = models.CharField(
        max_length=20,
        choices=[
            ('single_course', 'Single Course'),
            ('all_access', 'All Access Subscription')
        ],
        default='single_course'
    )
    course_id = models.CharField(max_length=100, blank=True, null=True)
    course_name = models.CharField(max_length=200, blank=True, null=True)
    enrollment_created = models.BooleanField(default=False)
    enrollment_date = models.DateTimeField(blank=True, null=True)
    subscription_active = models.BooleanField(default=False)
    subscription_expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} {self.currency} - {self.payment_status}"
        
    class Meta:
        db_table = 'payment_transaction'  # Match existing database table name
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions' 