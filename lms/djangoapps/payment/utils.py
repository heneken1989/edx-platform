"""
Utility functions for payment and subscription management
"""

from django.contrib.auth.models import User
from django.utils import timezone
from .models import PaymentTransaction


def has_active_subscription(user):
    """
    Check if user has an active all-access subscription
    
    Args:
        user: Django User object
        
    Returns:
        bool: True if user has active subscription, False otherwise
    """
    if not user or user.is_anonymous:
        return False
    
    try:
        # Find the most recent successful all-access transaction
        latest_transaction = PaymentTransaction.objects.filter(
            user=user,
            payment_type='all_access',
            payment_status='success'
        ).order_by('-created_at').first()
        
        if latest_transaction and latest_transaction.is_subscription_active():
            return True
            
    except Exception as e:
        print(f"Error checking subscription status: {str(e)}")
    
    return False


def get_user_subscription_info(user):
    """
    Get detailed subscription information for a user
    
    Args:
        user: Django User object
        
    Returns:
        dict: Subscription information or None if no active subscription
    """
    if not user or user.is_anonymous:
        return None
    
    try:
        # Find the most recent successful all-access transaction
        latest_transaction = PaymentTransaction.objects.filter(
            user=user,
            payment_type='all_access',
            payment_status='success'
        ).order_by('-created_at').first()
        
        if latest_transaction and latest_transaction.is_subscription_active():
            return {
                'subscription_active': True,
                'expires_at': latest_transaction.subscription_expires_at,
                'days_remaining': (latest_transaction.subscription_expires_at - timezone.now()).days,
                'transaction_ref': latest_transaction.txn_ref,
                'amount_paid': latest_transaction.amount,
                'currency': latest_transaction.currency,
                'created_at': latest_transaction.created_at
            }
            
    except Exception as e:
        print(f"Error getting subscription info: {str(e)}")
    
    return None


def can_access_course(user, course_key):
    """
    Check if user can access a specific course
    
    Args:
        user: Django User object
        course_key: Course key string
        
    Returns:
        bool: True if user can access the course, False otherwise
    """
    if not user or user.is_anonymous:
        return False
    
    # Check if user has active subscription
    if has_active_subscription(user):
        return True
    
    # Check if user is enrolled in this specific course
    try:
        from common.djangoapps.student.models import CourseEnrollment
        enrollment = CourseEnrollment.get_enrollment(user, course_key)
        return enrollment and enrollment.is_active
    except Exception:
        return False


def get_user_course_access_status(user, course_key):
    """
    Get detailed access status for a user and course
    
    Args:
        user: Django User object
        course_key: Course key string
        
    Returns:
        dict: Access status information
    """
    if not user or user.is_anonymous:
        return {
            'can_access': False,
            'reason': 'not_authenticated'
        }
    
    # Check subscription first
    subscription_info = get_user_subscription_info(user)
    if subscription_info:
        return {
            'can_access': True,
            'access_type': 'subscription',
            'subscription_info': subscription_info
        }
    
    # Check individual enrollment
    try:
        from common.djangoapps.student.models import CourseEnrollment
        enrollment = CourseEnrollment.get_enrollment(user, course_key)
        
        if enrollment and enrollment.is_active:
            return {
                'can_access': True,
                'access_type': 'enrollment',
                'enrollment_mode': enrollment.mode,
                'enrollment_date': enrollment.created
            }
        else:
            return {
                'can_access': False,
                'reason': 'not_enrolled'
            }
            
    except Exception as e:
        return {
            'can_access': False,
            'reason': 'error',
            'error': str(e)
        } 