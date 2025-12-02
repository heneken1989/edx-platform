from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


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
            ('all_access', 'All Access Subscription'),
            ('section_access', 'Section Access')  # Access to specific section
        ],
        default='single_course'
    )
    course_id = models.CharField(max_length=100, blank=True, null=True)
    course_name = models.CharField(max_length=200, blank=True, null=True)
    section_name = models.CharField(max_length=200, blank=True, null=True)  # Section display name (e.g., "読解") - DEPRECATED: use allowed_sections_json
    allowed_sections_json = models.TextField(blank=True, null=True)  # JSON array of section names user has access to (e.g., ["読解", "文法"])
    excluded_sections_json = models.TextField(blank=True, null=True)  # JSON array of section names to exclude (e.g., ["会話練習"]) - used with "all except X" logic
    enrollment_created = models.BooleanField(default=False)
    enrollment_date = models.DateTimeField(blank=True, null=True)
    subscription_active = models.BooleanField(default=False)
    subscription_expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def is_subscription_active(self):
        """
        Check if this transaction represents an active subscription
        
        Returns:
            bool: True if subscription is active (not expired), False otherwise
        """
        if not self.subscription_active:
            return False
        
        if not self.subscription_expires_at:
            # If no expiration date, consider it active if subscription_active is True
            return True
        
        # Check if subscription has not expired
        return timezone.now() < self.subscription_expires_at
    
    def get_allowed_sections(self):
        """
        Get list of allowed sections from allowed_sections_json
        
        Returns:
            list: List of section names, or ["*"] if all sections are allowed
        """
        if self.allowed_sections_json:
            try:
                return json.loads(self.allowed_sections_json)
            except (json.JSONDecodeError, TypeError):
                return []
        # Fallback to section_name for backward compatibility
        if self.section_name:
            return [self.section_name]
        return []
    
    def get_excluded_sections(self):
        """
        Get list of excluded sections from excluded_sections_json
        
        Returns:
            list: List of section names to exclude
        """
        if self.excluded_sections_json:
            try:
                return json.loads(self.excluded_sections_json)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} {self.currency} - {self.payment_status}"
        
    class Meta:
        db_table = 'payment_transaction'  # Match existing database table name
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions' 