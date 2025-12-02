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


def get_user_section_access(user):
    """
    Get list of sections user has access to (from section_access payments)
    Supports:
    - Multiple sections: allowed_sections_json = ["読解", "文法"]
    - All except X: allowed_sections_json = ["*"] and excluded_sections_json = ["会話練習"]
    
    Args:
        user: Django User object
        
    Returns:
        dict: {
            'allowed_sections': list of section names, or ['*'] if all sections,
            'excluded_sections': list of excluded section names (if any)
        }
    """
    if not user or user.is_anonymous:
        return {'allowed_sections': [], 'excluded_sections': []}
    
    try:
        # Find all successful section_access transactions
        section_transactions = PaymentTransaction.objects.filter(
            user=user,
            payment_type='section_access',
            payment_status='success',
            subscription_active=True
        ).order_by('-created_at')
        
        # Collect all allowed and excluded sections
        allowed_sections = []
        excluded_sections = []
        has_all_sections = False  # Track if any transaction grants access to all sections
        
        for transaction in section_transactions:
            # Get allowed sections from new JSON field
            transaction_allowed = transaction.get_allowed_sections()
            transaction_excluded = transaction.get_excluded_sections()
            
            if transaction_allowed:
                if transaction_allowed == ['*']:
                    has_all_sections = True
                else:
                    # Add unique sections
                    for section in transaction_allowed:
                        if section not in allowed_sections:
                            allowed_sections.append(section)
            
            # Collect excluded sections
            if transaction_excluded:
                for section in transaction_excluded:
                    if section not in excluded_sections:
                        excluded_sections.append(section)
            
            # Fallback to section_name for backward compatibility
            if not transaction_allowed and transaction.section_name:
                if transaction.section_name not in allowed_sections:
                    allowed_sections.append(transaction.section_name)
        
        # If any transaction grants "all sections", return ['*']
        if has_all_sections:
            return {
                'allowed_sections': ['*'],
                'excluded_sections': excluded_sections
            }
        
        return {
            'allowed_sections': allowed_sections,
            'excluded_sections': excluded_sections
        }
            
    except Exception as e:
        print(f"Error getting section access: {str(e)}")
    
    return {'allowed_sections': [], 'excluded_sections': []}


def get_user_subscription_info(user):
    """
    Get detailed subscription information for a user
    Includes both all_access and section_access transactions
    Supports aggregation of multiple section_access packages
    
    Args:
        user: Django User object
        
    Returns:
        dict: Subscription information or None if no active subscription
        Note: allowed_sections is aggregated from ALL active section_access transactions
    """
    if not user or user.is_anonymous:
        return None
    
    try:
        # First, try to find the most recent successful all-access transaction
        latest_all_access = PaymentTransaction.objects.filter(
            user=user,
            payment_type='all_access',
            payment_status='success'
        ).order_by('-created_at').first()
        
        if latest_all_access and latest_all_access.is_subscription_active():
            return {
                'subscription_active': True,
                'payment_type': 'all_access',
                'expires_at': latest_all_access.subscription_expires_at,
                'days_remaining': (latest_all_access.subscription_expires_at - timezone.now()).days if latest_all_access.subscription_expires_at else None,
                'transaction_ref': latest_all_access.txn_ref,
                'amount_paid': latest_all_access.amount,
                'currency': latest_all_access.currency,
                'created_at': latest_all_access.created_at,
                'allowed_sections': ['*'],  # All sections for all_access
                'excluded_sections': [],
                'total_packages': 1  # Only 1 all_access package
            }
        
        # If no all_access, check for section_access transactions
        # Get ALL active section_access transactions (for aggregation)
        active_section_access = PaymentTransaction.objects.filter(
            user=user,
            payment_type='section_access',
            payment_status='success',
            subscription_active=True
        ).order_by('-created_at')
        
        # Filter to only active (not expired) transactions
        active_transactions = [
            txn for txn in active_section_access 
            if txn.is_subscription_active()
        ]
        
        if active_transactions:
            # Get aggregated section access info (from ALL active transactions)
            section_access_info = get_user_section_access(user)
            
            # Get latest transaction for display purposes
            latest_section_access = active_transactions[0]
            
            # Calculate earliest expiration (when access will be lost)
            earliest_expiration = min(
                (txn.subscription_expires_at for txn in active_transactions if txn.subscription_expires_at),
                default=None
            )
            
            # Calculate latest expiration (when all packages expire)
            latest_expiration = max(
                (txn.subscription_expires_at for txn in active_transactions if txn.subscription_expires_at),
                default=None
            )
            
            # Calculate days remaining based on earliest expiration
            days_remaining = None
            if earliest_expiration:
                days_remaining = (earliest_expiration - timezone.now()).days
            
            # Calculate total amount paid across all packages
            total_amount = sum(txn.amount for txn in active_transactions)
            
            # Get list of all package names/sections from transactions
            package_details = []
            for txn in active_transactions:
                txn_allowed = txn.get_allowed_sections()
                txn_excluded = txn.get_excluded_sections()
                package_info = {
                    'transaction_ref': txn.txn_ref,
                    'amount': float(txn.amount),
                    'created_at': txn.created_at.isoformat() if txn.created_at else None,
                    'expires_at': txn.subscription_expires_at.isoformat() if txn.subscription_expires_at else None,
                }
                if txn_allowed:
                    package_info['allowed_sections'] = txn_allowed
                if txn_excluded:
                    package_info['excluded_sections'] = txn_excluded
                if txn.section_name:
                    package_info['section_name'] = txn.section_name
                package_details.append(package_info)
            
            result = {
                'subscription_active': True,
                'payment_type': 'section_access',
                'expires_at': earliest_expiration.isoformat() if earliest_expiration else None,  # Earliest expiration
                'latest_expires_at': latest_expiration.isoformat() if latest_expiration else None,  # Latest expiration
                'days_remaining': days_remaining,
                'transaction_ref': latest_section_access.txn_ref,  # Latest transaction ref for display
                'amount_paid': latest_section_access.amount,  # Latest transaction amount
                'total_amount_paid': float(total_amount),  # Total across all packages
                'currency': latest_section_access.currency,
                'created_at': latest_section_access.created_at,
                'allowed_sections': section_access_info.get('allowed_sections', []),  # AGGREGATED from all packages
                'excluded_sections': section_access_info.get('excluded_sections', []),  # AGGREGATED from all packages
                'section_name': latest_section_access.section_name,  # For backward compatibility
                'total_packages': len(active_transactions),  # Number of active packages
            }
            
            # Only include packages list if there are multiple packages
            if len(active_transactions) > 1:
                result['packages'] = package_details  # List of all active packages
            
            return result
            
    except Exception as e:
        print(f"Error getting subscription info: {str(e)}")
        import traceback
        traceback.print_exc()
    
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