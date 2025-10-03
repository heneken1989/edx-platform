from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import json
import hashlib
import hmac
import urllib.parse
from datetime import datetime
import time
from .settings import get_vnpay_url, get_vnpay_credentials, VNPAY_CONFIG
from .models import PaymentTransaction
from django.utils import timezone
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie


def build_payment_url(path, **params):
    """
    Build a payment URL with the Learning MFE base URL and query parameters.
    
    Args:
        path (str): The path after the base URL (e.g., 'payment/success')
        **params: Query parameters to add to the URL
    
    Returns:
        str: Complete URL
    """
    # Remove trailing slash from base_url if exists
    base_url = "https://nihongodrill.com/learning"
    #base_url = "http://apps.local.openedx.io:2000"
    # Add path directly without /learning prefix
    url = f"{base_url}/{path}"
    
    if params:
        query_string = urllib.parse.urlencode(params)
        url = f"{url}?{query_string}"
    
    # Debug logging
    print(f"=== build_payment_url Debug ===")
    print(f"Base URL: {base_url}")
    print(f"Path: {path}")
    print(f"Params: {params}")
    print(f"Final URL: {url}")
    print(f"===============================")
    
    return url


@login_required
def payment_test(request):
    """
    Simple test endpoint to check if payment app is working
    """
    # Debug: Show learning base URL
    base_url = "http://apps.local.openedx.io:2000"
    print(f"Learning Base URL: {base_url}")
    
    return JsonResponse({
        'success': True,
        'message': 'Payment app is working!',
        'timestamp': datetime.now().isoformat(),
        'learning_base_url': base_url  # Add this to response
    })


@csrf_exempt
@require_http_methods(["POST"])
def create_payment(request):
    """
    Create a VNPay payment URL with proper formatting
    """
    print(f"Payment API called with method: {request.method}")
    print(f"Request headers: {request.headers}")
    print(f"Request body: {request.body}")
    
    try:
        data = json.loads(request.body)
        amount = data.get('amount', 0)
        payment_type = data.get('paymentType', 'all_access')  # Default to all_access
        course_id = data.get('courseId', 'ALL_COURSES')
        course_name = data.get('courseName', 'Gói All Access - Truy cập tất cả khóa học')
        
        # Format amount: multiply by 100 (VNPay expects amount in smallest currency unit)
        vnp_amount = amount * 100
        
        # Format date: YYYYMMDDHHmmss
        create_date = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Generate unique transaction reference
        txn_ref = f'DEMO{int(time.time())}'
        
        # Set order info for all access payment
        order_info = 'Thanh toan goi All Access - Truy cap tat ca khoa hoc'
        
        # Save payment transaction to database
        try:
            print(f"Creating transaction with data:")
            print(f"- txn_ref: {txn_ref}")
            print(f"- amount: {amount}")
            print(f"- user: {request.user.username}")
            print(f"- payment_type: all_access")
            
            transaction = PaymentTransaction.objects.create(
                txn_ref=txn_ref,
                amount=amount,
                currency='VND',
                payment_method='vnpay',
                payment_type='all_access',  # Always all_access
                course_id=None,  # No specific course for all access
                course_name='Gói All Access - Truy cập tất cả khóa học',
                user=request.user,
                payment_status='pending',  # Use existing payment_status field
                enrollment_created=False,  # Use existing enrollment_created field
                subscription_active=False  # Use existing subscription_active field
            )
            print(f"✅ Payment transaction saved: {txn_ref}")
        except Exception as e:
            print(f"❌ Error saving transaction: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': f'Failed to create payment transaction: {str(e)}'
            }, status=500)
        
        # Only continue if transaction was saved successfully
        try:
            # Get VNPay credentials
            vnpay_url = get_vnpay_url()
            credentials = get_vnpay_credentials()
            tmn_code = credentials['tmn_code']
            hash_secret = credentials['hash_secret']
            
            # Create VNPay parameters
            vnp_params = {
                'vnp_Amount': str(vnp_amount),
                'vnp_Command': 'pay',
                'vnp_CreateDate': create_date,
                'vnp_CurrCode': 'VND',
                'vnp_IpAddr': request.META.get('REMOTE_ADDR', '127.0.0.1'),
                'vnp_Locale': 'vn',
                'vnp_OrderInfo': order_info,
                'vnp_OrderType': 'other',
                'vnp_ReturnUrl': request.build_absolute_uri('/payment/callback/'),
                'vnp_TmnCode': tmn_code,
                'vnp_TxnRef': txn_ref,
                'vnp_Version': '2.1.0'
            }
            
            # Sort parameters alphabetically (VNPay requirement)
            sorted_params = dict(sorted(vnp_params.items()))
            
            # Create query string
            query_string = '&'.join([f'{k}={urllib.parse.quote_plus(str(v))}' for k, v in sorted_params.items()])
            
            # Create hash signature
            hmac_obj = hmac.new(
                hash_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha512
            )
            secure_hash = hmac_obj.hexdigest()
            query_string += f'&vnp_SecureHash={secure_hash}'
            
            # Create payment URL
            payment_url = f'{vnpay_url}?{query_string}'
            
            # Debug logging
            print(f"VNPay Debug Info:")
            print(f"Amount: {amount} -> {vnp_amount}")
            print(f"Create Date: {create_date}")
            print(f"Txn Ref: {txn_ref}")
            print(f"Payment Type: {payment_type}")
            print(f"Order Info: {order_info}")
            print(f"Query String: {query_string}")
            print(f"Payment URL: {payment_url}")
            
            payment_data = {
                'success': True,
                'paymentUrl': payment_url,
                'txnRef': txn_ref,
                'status': 'pending',
                'paymentType': 'all_access'
            }
            
            print(f"Returning payment data: {payment_data}")
            return JsonResponse(payment_data)
            
        except Exception as e:
            print(f"Error creating VNPay parameters or URL: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': f'Failed to create payment URL: {str(e)}'
            }, status=500)
            
    except Exception as e:
        print(f"Payment creation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@csrf_exempt
def vnpay_callback(request):
    """
    Handle VNPay callback after payment
    """
    print(f"VNPay callback received: {request.GET}")
    
    try:
        # Get VNPay response parameters
        txn_ref = request.GET.get('vnp_TxnRef')
        response_code = request.GET.get('vnp_ResponseCode')
        amount = request.GET.get('vnp_Amount')
        secure_hash = request.GET.get('vnp_SecureHash')
        
        print(f"Transaction: {txn_ref}, Response Code: {response_code}")
        
        # Verify payment success (Response Code 00 = Success)
        if response_code == '00':
            # Find the transaction
            try:
                transaction = PaymentTransaction.objects.get(txn_ref=txn_ref)
                
                # Mark transaction as successful and create enrollment/subscription
                if transaction.payment_status != 'success':
                    # Update transaction status
                    transaction.payment_status = 'success'
                    transaction.payment_type = 'all_access'
                    
                    # Get all available courses
                    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
                    from common.djangoapps.student.models import CourseEnrollment
                    from common.djangoapps.course_modes.models import CourseMode
                    from django.db.models import Q
                    
                    enrolled_count = 0
                    now = timezone.now()
                    
                    # Get all available courses
                    available_courses = CourseOverview.objects.filter(
                        Q(enrollment_start__lte=now, enrollment_end__gt=now) |  # Within enrollment period
                        Q(enrollment_start__isnull=True, enrollment_end__isnull=True)  # No enrollment period set
                    ).exclude(
                        # Exclude courses user is already enrolled in
                        id__in=CourseEnrollment.objects.filter(
                            user=transaction.user,
                            is_active=True
                        ).values_list('course_id', flat=True)
                    )
                    
                    # Enroll in each available course
                    for course in available_courses:
                        try:
                            # Enroll with verified mode
                            enrollment = CourseEnrollment.enroll(
                                user=transaction.user,
                                course_key=course.id,
                                mode=CourseMode.VERIFIED,
                                check_access=True
                            )
                            if enrollment:
                                enrolled_count += 1
                                print(f"✅ Successfully enrolled {transaction.user.username} in course {course.id}")
                        except Exception as e:
                            print(f"❌ Failed to enroll in course {course.id}: {str(e)}")
                            continue
                    
                    # Update transaction with enrollment info
                    transaction.enrollment_created = enrolled_count > 0  # Use existing enrollment_created field
                    transaction.enrollment_date = timezone.now() if enrolled_count > 0 else None  # Use existing enrollment_date field
                    transaction.subscription_active = True  # Use existing subscription_active field
                    transaction.subscription_expires_at = timezone.now() + timezone.timedelta(days=365)  # Use existing subscription_expires_at field
                    transaction.save()
                    
                    print(f"All-access subscription activated for user {transaction.user.username}")
                    print(f"Enrolled in {enrolled_count} courses")
                    
                    # Build success URL with enrollment information
                    success_params = {
                        'txnRef': txn_ref,
                        'amount': transaction.amount,
                        'subscription': 'true',
                        'enrolledCount': enrolled_count,
                        'totalCourses': available_courses.count()
                    }
                    success_url = build_payment_url('payment/success', **success_params)
                    return redirect(success_url)
                    
            except PaymentTransaction.DoesNotExist:
                print(f"Transaction {txn_ref} not found")
                error_url = build_payment_url('payment/cancel', txnRef=txn_ref, error='transaction_not_found')
                return redirect(error_url)
        else:
            # Payment failed
            try:
                transaction = PaymentTransaction.objects.get(txn_ref=txn_ref)
                transaction.payment_status = 'failed'
                transaction.save()
                print(f"Payment failed for transaction {txn_ref}")
            except PaymentTransaction.DoesNotExist:
                pass
            
            # Redirect to cancel page
            cancel_url = build_payment_url('payment/cancel', txnRef=txn_ref, error='payment_failed')
            return redirect(cancel_url)
            
    except Exception as e:
        print(f"Error processing VNPay callback: {str(e)}")
        # Redirect to error page
        error_url = build_payment_url('payment/cancel', error=str(e))
        return redirect(error_url)


@login_required
def check_subscription_status(request):
    """
    API endpoint to check user's subscription status
    """
    from .utils import get_user_subscription_info
    
    subscription_info = get_user_subscription_info(request.user)
    
    return JsonResponse({
        'success': True,
        'has_subscription': subscription_info is not None,
        'subscription_info': subscription_info
    })


@login_required
def check_course_access(request, course_key):
    """
    API endpoint to check if user can access a specific course
    """
    from .utils import get_user_course_access_status
    
    access_status = get_user_course_access_status(request.user, course_key)
    
    return JsonResponse({
        'success': True,
        'course_key': course_key,
        'access_status': access_status
    })


@login_required
def check_enrollment_status(request):
    """
    API endpoint to check user's enrollment status after payment
    """
    from .utils import has_active_subscription, get_user_subscription_info
    from common.djangoapps.student.models import CourseEnrollment
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
    
    # Get user's subscription status
    has_subscription = has_active_subscription(request.user)
    subscription_info = get_user_subscription_info(request.user)
    
    # Get user's enrollments
    enrollments = CourseEnrollment.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('course')
    
    # Get all available courses
    all_courses = CourseOverview.objects.filter(
        start__lte=timezone.now(),
        end__gte=timezone.now(),
    )
    
    # Get recent transactions
    recent_transactions = PaymentTransaction.objects.filter(
        user=request.user,
        payment_type='all_access'
    ).order_by('-created_at')[:5]
    
    transactions_data = []
    for txn in recent_transactions:
        transactions_data.append({
            'txn_ref': txn.txn_ref,
            'amount': float(txn.amount),
            'payment_status': txn.payment_status,
            'created_at': txn.created_at.isoformat(),
            'subscription_active': txn.subscription_active,
            'subscription_expires_at': txn.subscription_expires_at.isoformat() if txn.subscription_expires_at else None
        })
    
    # Get enrollment data
    enrollment_data = []
    for enrollment in enrollments:
        enrollment_data.append({
            'course_id': str(enrollment.course.id),
            'course_name': enrollment.course.display_name,
            'mode': enrollment.mode,
            'created': enrollment.created.isoformat(),
            'is_active': enrollment.is_active
        })
    
    return JsonResponse({
        'success': True,
        'user': {
            'username': request.user.username,
            'email': request.user.email,
            'user_id': request.user.id
        },
        'subscription': {
            'has_subscription': has_subscription,
            'subscription_info': subscription_info
        },
        'enrollments': {
            'total_enrolled': enrollments.count(),
            'total_available': all_courses.count(),
            'enrollment_list': enrollment_data
        },
        'transactions': {
            'total_transactions': recent_transactions.count(),
            'transaction_list': transactions_data
        },
        'status': {
            'has_subscription': has_subscription,
            'has_enrollments': enrollments.count() > 0,
            'can_access_all_courses': has_subscription,
            'enrollment_successful': has_subscription or enrollments.count() > 0
        }
    })


@ensure_csrf_cookie
def get_csrf_token(request):
    """
    API endpoint to get CSRF token for frontend
    """
    try:
        token = get_token(request)
        return JsonResponse({
            'csrf_token': token,
            'success': True
        })
    except Exception as e:
        print(f"Error getting CSRF token: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
def test_auto_enroll_hh(request):
    """
    Test endpoint để auto enroll user hh
    """
    try:
        from lms.djangoapps.payment.signals import auto_enroll_user_in_all_courses
        from django.contrib.auth.models import User
        
        # Lấy user hh
        try:
            user = User.objects.get(username='hh')
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User hh not found'
            }, status=404)
        
        print(f"=== TEST AUTO ENROLL FOR USER HH ===")
        print(f"User: {user.username} (ID: {user.id})")
        
        # Test auto enrollment function
        result = auto_enroll_user_in_all_courses(user)
        
        if result:
            print(f"=== AUTO ENROLL COMPLETE ===")
            print(f"Result: {result}")
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully enrolled user hh in {result["enrolled_count"]} courses',
                'enrolled_count': result['enrolled_count'],
                'total_available_courses': result['total_courses'],
                'user': user.username
            })
        else:
            print(f"=== AUTO ENROLL FAILED ===")
            
            return JsonResponse({
                'success': False,
                'error': 'Auto enrollment failed'
            }, status=500)

    except Exception as e:
        print(f"=== AUTO ENROLL ERROR ===")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
def auto_enroll_all_courses(request):
    """
    API endpoint to auto enroll user in all available courses
    This uses the shared auto enrollment function
    """
    try:
        from lms.djangoapps.payment.signals import auto_enroll_user_in_all_courses
        
        # Check for JWT authentication
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            # JWT authentication
            jwt_token = auth_header.split(' ')[1]
            try:
                from openedx.core.djangoapps.oauth_dispatch.jwt import create_jwt_for_user
                from openedx.core.djangoapps.user_authn.utils import get_user_from_jwt
                user = get_user_from_jwt(jwt_token)
                print(f"=== AUTO ENROLL START (JWT) ===")
                print(f"User: {user.username} (ID: {user.id})")
            except Exception as e:
                print(f"JWT authentication failed: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JWT token'
                }, status=401)
        else:
            # Session authentication
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required'
                }, status=401)
            user = request.user
            print(f"=== AUTO ENROLL START (Session) ===")
            print(f"User: {user.username} (ID: {user.id})")
        
        print(f"Request method: {request.method}")
        print(f"Request headers: {dict(request.headers)}")

        # Use the shared auto enrollment function
        result = auto_enroll_user_in_all_courses(user)
        
        if result:
            print(f"=== AUTO ENROLL COMPLETE ===")
            print(f"User: {user.username}")
            print(f"Result: {result}")

            return JsonResponse({
                'success': True,
                'message': f'Successfully enrolled in {result["enrolled_count"]} courses',
                'enrolled_count': result['enrolled_count'],
                'total_available_courses': result['total_courses'],
                'user': user.username
            })
        else:
            print(f"=== AUTO ENROLL FAILED ===")
            print(f"User: {user.username}")
            
            return JsonResponse({
                'success': False,
                'error': 'Auto enrollment failed'
            }, status=500)

    except Exception as e:
        print(f"=== AUTO ENROLL ERROR ===")
        print(f"Error in auto_enroll_all_courses: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)