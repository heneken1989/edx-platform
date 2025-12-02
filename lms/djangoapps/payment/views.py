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
import requests
from .settings import (
    get_vnpay_url, get_vnpay_credentials, VNPAY_CONFIG,
    get_payos_api_url, get_payos_credentials, PAYOS_CONFIG
)
from .models import PaymentTransaction
from django.utils import timezone
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie


def build_payment_url(path, **params):
    """
    Build a payment URL with the Learning MFE base URL and query parameters.
    
    Args:
        path (str): The path after the base URL (e.g., 'payment/success' or 'learning/payment/success')
        **params: Query parameters to add to the URL
    
    Returns:
        str: Complete URL
    """
    # Remove trailing slash from base_url if exists
    base_url = "https://nihongodrill.com"
    #base_url = "http://apps.local.openedx.io:2000"
    # Ensure path starts with /learning
    if not path.startswith('learning/'):
        path = f"learning/{path}"
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
        payment_type = data.get('paymentType', 'all_access')  # 'all_access' or 'section_access'
        course_id = data.get('courseId', 'ALL_COURSES')
        course_name = data.get('courseName', 'Gói All Access - Truy cập tất cả khóa học')
        section_name = data.get('sectionName')  # For section_access payment (backward compatibility)
        allowed_sections = data.get('allowedSections')  # List of section names (e.g., ["読解", "文法"])
        excluded_sections = data.get('excludedSections')  # List of excluded section names (e.g., ["会話練習"])
        expires_at_str = data.get('expiresAt')  # ISO string of expiration date
        duration_months = data.get('durationMonths', '1')  # Duration in months for reference
        
        # Format amount: multiply by 100 (VNPay expects amount in smallest currency unit)
        vnp_amount = amount * 100
        
        # Format date: YYYYMMDDHHmmss
        create_date = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Generate unique transaction reference
        txn_ref = f'DEMO{int(time.time())}'
        
        # Set order info based on payment type
        if payment_type == 'section_access':
            if excluded_sections:
                order_info = f'All sections except {", ".join(excluded_sections)}'
            elif allowed_sections:
                if allowed_sections == ['*']:
                    order_info = 'All sections access'
                else:
                    order_info = f'Sections: {", ".join(allowed_sections)}'
            elif section_name:
                order_info = f'Thanh toan Section {section_name}'
            else:
                order_info = 'Section access'
        else:
            order_info = 'Thanh toan goi All Access - Truy cap tat ca khoa hoc'
        
        # Save payment transaction to database
        try:
            # Prepare JSON fields for allowed/excluded sections
            # Note: json is already imported at the top of the file
            allowed_sections_json = None
            excluded_sections_json = None
            
            if payment_type == 'section_access':
                if allowed_sections:
                    # If allowed_sections is ['*'], it means all sections
                    allowed_sections_json = json.dumps(allowed_sections)
                elif section_name:
                    # Backward compatibility: use section_name if allowed_sections not provided
                    allowed_sections_json = json.dumps([section_name])
                
                if excluded_sections:
                    excluded_sections_json = json.dumps(excluded_sections)
            
            print(f"Creating transaction with data:")
            print(f"- txn_ref: {txn_ref}")
            print(f"- amount: {amount}")
            print(f"- user: {request.user.username}")
            print(f"- payment_type: {payment_type}")
            if section_name:
                print(f"- section_name: {section_name}")
            if allowed_sections:
                print(f"- allowed_sections: {allowed_sections}")
            if excluded_sections:
                print(f"- excluded_sections: {excluded_sections}")
            if expires_at_str:
                print(f"- expires_at: {expires_at_str}")
                print(f"- duration_months: {duration_months}")
            
            # Parse expires_at if provided
            subscription_expires_at = None
            if expires_at_str:
                try:
                    from django.utils.dateparse import parse_datetime
                    subscription_expires_at = parse_datetime(expires_at_str)
                    if subscription_expires_at:
                        # Ensure timezone awareness
                        if timezone.is_naive(subscription_expires_at):
                            subscription_expires_at = timezone.make_aware(subscription_expires_at)
                        print(f"✅ Parsed expires_at: {subscription_expires_at}")
                except Exception as e:
                    print(f"⚠️ Failed to parse expires_at '{expires_at_str}': {str(e)}")
                    # Fallback: calculate from duration_months
                    if duration_months:
                        try:
                            months = int(duration_months)
                            subscription_expires_at = timezone.now() + timezone.timedelta(days=months * 30)
                            print(f"✅ Calculated expires_at from duration ({months} months): {subscription_expires_at}")
                        except:
                            pass
            
            # If still no expires_at, use default (1 year)
            if not subscription_expires_at:
                subscription_expires_at = timezone.now() + timezone.timedelta(days=365)
                print(f"⚠️ Using default expires_at (365 days): {subscription_expires_at}")
            
            transaction = PaymentTransaction.objects.create(
                txn_ref=txn_ref,
                amount=amount,
                currency='VND',
                payment_method='vnpay',
                payment_type=payment_type,
                course_id=None if payment_type == 'all_access' else course_id,
                course_name=course_name,
                section_name=section_name,  # Store section name for section_access (backward compatibility)
                allowed_sections_json=allowed_sections_json,  # JSON array of allowed sections
                excluded_sections_json=excluded_sections_json,  # JSON array of excluded sections
                user=request.user,
                payment_status='pending',
                enrollment_created=False,
                subscription_active=False,
                subscription_expires_at=subscription_expires_at  # Set expiration date
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
        
        # Get payment method from request
        payment_method = data.get('paymentMethod', 'vnpay')
        
        # Only continue if transaction was saved successfully
        try:
            # Update transaction with payment method
            transaction.payment_method = payment_method
            transaction.save()
            
            if payment_method == 'payos':
                # Handle PayOS payment
                try:
                    payos_api_url = get_payos_api_url()
                    payos_credentials = get_payos_credentials()
                    
                    # Validate PayOS credentials
                    if not payos_credentials['client_id'] or payos_credentials['client_id'] == 'DEMO':
                        raise Exception("PayOS Client ID not configured. Please set PAYOS_CLIENT_ID in environment variables.")
                    if not payos_credentials['api_key'] or payos_credentials['api_key'] == 'DEMO_KEY':
                        raise Exception("PayOS API Key not configured. Please set PAYOS_API_KEY in environment variables.")
                    
                    # PayOS payment link creation
                    
                    # Prepare PayOS payment data
                    order_code = int(time.time())  # Unique order code
                    cancel_url = data.get('cancelUrl', f"{request.build_absolute_uri('/')}learning/payment/cancel")
                    # PayOS returnUrl should point to backend callback, which will redirect to success page
                    return_url = data.get('returnUrl', f"{request.build_absolute_uri('/')}api/payment/callback/")
                    amount_int = int(amount)
                    
                    # PayOS requires description to be max 25 characters
                    payos_description = order_info[:25] if len(order_info) > 25 else order_info
                    
                    # Create signature data (sorted alphabetically as per PayOS docs)
                    # Format: amount=$amount&cancelUrl=$cancelUrl&description=$description&orderCode=$orderCode&returnUrl=$returnUrl
                    signature_data = f"amount={amount_int}&cancelUrl={cancel_url}&description={payos_description}&orderCode={order_code}&returnUrl={return_url}"
                    
                    # Generate HMAC_SHA256 signature
                    checksum_key = payos_credentials['checksum_key']
                    signature = hmac.new(
                        checksum_key.encode('utf-8'),
                        signature_data.encode('utf-8'),
                        hashlib.sha256
                    ).hexdigest()
                    
                    payos_data = {
                        "orderCode": order_code,
                        "amount": amount_int,  # Amount in VND (PayOS uses VND directly, not multiplied)
                        "description": payos_description,  # Max 25 characters for PayOS
                        "cancelUrl": cancel_url,
                        "returnUrl": return_url,
                        "items": [
                            {
                                "name": course_name,
                                "quantity": 1,
                                "price": amount_int
                            }
                        ],
                        "signature": signature  # Required by PayOS API
                    }
                    
                    # Create payment link via PayOS API
                    headers = {
                        'Content-Type': 'application/json',
                        'x-client-id': str(payos_credentials['client_id']),
                        'x-api-key': str(payos_credentials['api_key'])
                    }
                    
                    # PayOS API endpoint - try /v2/payment-requests first, fallback to /payment-requests
                    api_endpoint = f"{payos_api_url}/v2/payment-requests"
                    
                    print(f"=== PayOS Debug Info ===")
                    print(f"API URL: {api_endpoint}")
                    print(f"Client ID: {payos_credentials['client_id']}")
                    print(f"API Key: {payos_credentials['api_key'][:10]}...")  # Only show first 10 chars for security
                    print(f"Order Code: {order_code}")
                    print(f"Amount: {amount_int}")
                    print(f"Description (original): {order_info}")
                    print(f"Description (PayOS, max 25 chars): {payos_description}")
                    print(f"Signature Data: {signature_data}")
                    print(f"Signature: {signature}")
                    print(f"Request Data: {json.dumps(payos_data, ensure_ascii=False)}")
                    print(f"=========================")
                    
                    payos_response = requests.post(
                        api_endpoint,
                        json=payos_data,
                        headers=headers,
                        timeout=30
                    )
                    
                    print(f"PayOS API Response Status: {payos_response.status_code}")
                    print(f"PayOS API Response: {payos_response.text}")
                    
                    if payos_response.status_code == 200:
                        payos_result = payos_response.json()
                        print(f"PayOS Response JSON: {json.dumps(payos_result, ensure_ascii=False)}")
                        
                        # PayOS response structure: {"code": "00", "desc": "success", "data": {"checkoutUrl": "..."}}
                        if payos_result.get('code') == '00' or payos_result.get('code') == 0:
                            payment_url = payos_result.get('data', {}).get('checkoutUrl')
                            
                            if payment_url:
                                # Update transaction with PayOS order code
                                transaction.txn_ref = f"PAYOS_{order_code}"
                                transaction.save()
                                
                                payment_data = {
                                    'success': True,
                                    'paymentUrl': payment_url,
                                    'txnRef': transaction.txn_ref,
                                    'status': 'pending',
                                    'paymentType': 'all_access',
                                    'paymentMethod': 'payos'
                                }
                                
                                print(f"✅ PayOS payment URL created: {payment_url}")
                                return JsonResponse(payment_data)
                            else:
                                raise Exception(f"PayOS did not return checkout URL. Response: {payos_result}")
                        else:
                            error_desc = payos_result.get('desc', 'Unknown error')
                            raise Exception(f"PayOS API returned error: {error_desc}")
                    else:
                        error_msg = payos_response.text
                        print(f"❌ PayOS API error: {payos_response.status_code} - {error_msg}")
                        try:
                            error_json = payos_response.json()
                            error_desc = error_json.get('desc', error_json.get('message', error_msg))
                            raise Exception(f"PayOS API error ({payos_response.status_code}): {error_desc}")
                        except:
                            raise Exception(f"PayOS API error ({payos_response.status_code}): {error_msg}")
                            
                except requests.exceptions.RequestException as e:
                    print(f"❌ PayOS Request Exception: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise Exception(f"PayOS network error: {str(e)}")
                except Exception as e:
                    print(f"❌ PayOS Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise
            
            else:
                # Handle VNPay payment (default)
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
                    'paymentType': 'all_access',
                    'paymentMethod': 'vnpay'
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


def handle_payos_callback(request, payos_data=None):
    """
    Handle PayOS callback after payment
    PayOS returns: code=00&id=xxx&cancel=false&status=PAID&orderCode=xxx
    """
    print(f"PayOS callback received - Method: {request.method}")
    print(f"GET params: {dict(request.GET)}")
    if payos_data:
        print(f"POST data: {payos_data}")
    
    try:
        # PayOS can send callback via webhook (POST) or redirect (GET)
        # Check for orderCode in different formats
        order_code = None
        status = None
        code = None
        
        # First check GET parameters (redirect format)
        if request.GET.get('orderCode'):
            # GET redirect format from PayOS
            order_code = request.GET.get('orderCode')
            status = request.GET.get('status', '').upper()  # 'PAID', 'CANCELLED', 'PENDING'
            code = request.GET.get('code')  # '00' = success
            cancel = request.GET.get('cancel', 'false').lower() == 'true'
            
            print(f"PayOS GET callback - orderCode: {order_code}, status: {status}, code: {code}, cancel: {cancel}")
            
            # Determine payment status from PayOS response
            # PayOS format: code=00 (success), status=PAID, cancel=false
            if cancel:
                status = 'CANCELLED'
            elif code == '00' and status == 'PAID':
                status = 'PAID'  # Payment successful
            elif code != '00':
                status = 'FAILED'
            # If status is already set (PAID, CANCELLED, etc), keep it
        
        # Check POST data (webhook format)
        elif payos_data:
            if 'data' in payos_data:
                # Webhook format
                data = payos_data.get('data', {})
                order_code = data.get('orderCode')
                status = data.get('status')  # 'PAID', 'CANCELLED', 'PENDING'
            elif 'orderCode' in payos_data:
                # Direct format
                order_code = payos_data.get('orderCode')
                status = payos_data.get('status')
        
        if not order_code:
            print("PayOS callback: No orderCode found")
            error_url = build_payment_url('learning/payment/cancel', error='invalid_callback')
            return redirect(error_url)
        
        print(f"PayOS Transaction: orderCode={order_code}, status={status}")
        
        # Find transaction by order code (stored in txn_ref as PAYOS_{orderCode})
        try:
            transaction = PaymentTransaction.objects.get(txn_ref=f"PAYOS_{order_code}")
        except PaymentTransaction.DoesNotExist:
            # Try to find by order code directly
            try:
                transaction = PaymentTransaction.objects.filter(
                    payment_method='payos',
                    txn_ref__contains=str(order_code)
                ).first()
            except:
                transaction = None
        
        if not transaction:
            print(f"PayOS transaction not found for orderCode: {order_code}")
            error_url = build_payment_url('learning/payment/cancel', orderCode=order_code, error='transaction_not_found')
            return redirect(error_url)
        
        # Verify payment success (status = 'PAID' or code = '00')
        if status == 'PAID' or (code == '00' and status == 'PAID'):
            # Mark transaction as successful and create enrollment/subscription
            if transaction.payment_status != 'success':
                # Update transaction status
                transaction.payment_status = 'success'
                # Don't override payment_type if it's already set (e.g., section_access)
                # Only set to 'all_access' if it's not already set
                if not transaction.payment_type:
                    transaction.payment_type = 'all_access'
                
                # Get all available courses and enroll user
                from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
                from common.djangoapps.student.models import CourseEnrollment
                from common.djangoapps.course_modes.models import CourseMode
                from django.db.models import Q
                
                enrolled_count = 0
                now = timezone.now()
                
                # Get all available courses
                available_courses = CourseOverview.objects.filter(
                    Q(enrollment_start__lte=now, enrollment_end__gt=now) |
                    Q(enrollment_start__isnull=True, enrollment_end__isnull=True)
                ).exclude(
                    id__in=CourseEnrollment.objects.filter(
                        user=transaction.user,
                        is_active=True
                    ).values_list('course_id', flat=True)
                )
                
                # Apply enrollment configuration (if exists)
                try:
                    from .enrollment_config import should_enroll_course
                    # Filter courses based on configuration
                    courses_to_enroll = [
                        course for course in available_courses
                        if should_enroll_course(course.id, course)
                    ]
                    print(f"Enrollment config applied: {len(courses_to_enroll)}/{available_courses.count()} courses selected")
                except ImportError:
                    # If config doesn't exist, enroll all courses (default behavior)
                    courses_to_enroll = available_courses
                    print("No enrollment config found, enrolling in all available courses")
                
                # Enroll in each selected course
                for course in courses_to_enroll:
                    try:
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
                transaction.enrollment_created = enrolled_count > 0
                transaction.enrollment_date = timezone.now() if enrolled_count > 0 else None
                transaction.subscription_active = True
                # Only set expires_at if not already set (preserve the value from create_payment)
                if not transaction.subscription_expires_at:
                    transaction.subscription_expires_at = timezone.now() + timezone.timedelta(days=365)
                    print(f"⚠️ PayOS callback: Set default expires_at (365 days): {transaction.subscription_expires_at}")
                else:
                    print(f"✅ PayOS callback: Using existing expires_at: {transaction.subscription_expires_at}")
                # Keep payment_type and section_name as set during creation
                transaction.save()
                
                print(f"PayOS payment successful for user {transaction.user.username}")
                print(f"Payment type: {transaction.payment_type}")
                print(f"Section name: {transaction.section_name}")
                if transaction.payment_type == 'section_access' and transaction.section_name:
                    print(f"✅ Section access granted: {transaction.section_name}")
                print(f"Enrolled in {enrolled_count} courses")
                
                # Build success URL
                success_params = {
                    'txnRef': transaction.txn_ref,
                    'amount': transaction.amount,
                    'subscription': 'true',
                    'enrolledCount': enrolled_count,
                    'totalCourses': len(courses_to_enroll) if 'courses_to_enroll' in locals() else available_courses.count()
                }
                success_url = build_payment_url('learning/payment/success', **success_params)
                return redirect(success_url)
            else:
                # Already processed, redirect to success
                success_url = build_payment_url('learning/payment/success', txnRef=transaction.txn_ref)
                return redirect(success_url)
        else:
            # Payment failed or cancelled
            transaction.payment_status = 'failed' if status == 'CANCELLED' else 'pending'
            transaction.save()
            print(f"PayOS payment failed/cancelled for transaction {transaction.txn_ref}")
            
            cancel_url = build_payment_url('learning/payment/cancel', txnRef=transaction.txn_ref, error='payment_failed')
            return redirect(cancel_url)
            
    except Exception as e:
        print(f"Error processing PayOS callback: {str(e)}")
        import traceback
        traceback.print_exc()
        error_url = build_payment_url('learning/payment/cancel', error=str(e))
        return redirect(error_url)


@csrf_exempt
def vnpay_callback(request):
    """
    Handle VNPay callback after payment
    """
    print(f"Payment callback received: {request.method}")
    print(f"GET params: {request.GET}")
    print(f"POST params: {request.POST}")
    
    # Check if this is a PayOS callback
    # PayOS GET format: code=00&id=xxx&cancel=false&status=PAID&orderCode=xxx
    if request.GET.get('orderCode') and (request.GET.get('code') or request.GET.get('status')):
        # This is PayOS callback via GET redirect
        return handle_payos_callback(request, None)
    
    # Check if this is a PayOS webhook (POST with JSON)
    if request.method == 'POST':
        try:
            # Note: json is already imported at the top of the file
            payos_data = json.loads(request.body) if request.body else {}
            
            # Check if it's PayOS webhook format
            if 'data' in payos_data or 'code' in payos_data:
                return handle_payos_callback(request, payos_data)
        except:
            pass
    
    # Otherwise, handle as VNPay callback
    try:
        # Get VNPay response parameters
        txn_ref = request.GET.get('vnp_TxnRef')
        response_code = request.GET.get('vnp_ResponseCode')
        amount = request.GET.get('vnp_Amount')
        secure_hash = request.GET.get('vnp_SecureHash')
        
        print(f"VNPay Transaction: {txn_ref}, Response Code: {response_code}")
        
        # Verify payment success (Response Code 00 = Success)
        if response_code == '00':
            # Find the transaction
            try:
                transaction = PaymentTransaction.objects.get(txn_ref=txn_ref)
                
                # Mark transaction as successful and create enrollment/subscription
                if transaction.payment_status != 'success':
                    # Update transaction status
                    transaction.payment_status = 'success'
                    # Don't override payment_type if it's already set (e.g., section_access)
                    # Only set to 'all_access' if it's not already set
                    if not transaction.payment_type:
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
                    
                    # Apply enrollment configuration (if exists)
                    try:
                        from .enrollment_config import should_enroll_course
                        # Filter courses based on configuration
                        courses_to_enroll = [
                            course for course in available_courses
                            if should_enroll_course(course.id, course)
                        ]
                        print(f"Enrollment config applied: {len(courses_to_enroll)}/{available_courses.count()} courses selected")
                    except ImportError:
                        # If config doesn't exist, enroll all courses (default behavior)
                        courses_to_enroll = available_courses
                        print("No enrollment config found, enrolling in all available courses")
                    
                    # Enroll in each selected course
                    for course in courses_to_enroll:
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
                    transaction.enrollment_created = enrolled_count > 0
                    transaction.enrollment_date = timezone.now() if enrolled_count > 0 else None
                    transaction.subscription_active = True
                    # Only set expires_at if not already set (preserve the value from create_payment)
                    if not transaction.subscription_expires_at:
                        transaction.subscription_expires_at = timezone.now() + timezone.timedelta(days=365)
                        print(f"⚠️ VNPay callback: Set default expires_at (365 days): {transaction.subscription_expires_at}")
                    else:
                        print(f"✅ VNPay callback: Using existing expires_at: {transaction.subscription_expires_at}")
                    # Keep payment_type and section_name as set during creation
                    transaction.save()
                    
                    print(f"Payment successful for user {transaction.user.username}")
                    print(f"Payment type: {transaction.payment_type}")
                    print(f"Section name: {transaction.section_name}")
                    if transaction.payment_type == 'section_access' and transaction.section_name:
                        print(f"✅ Section access granted: {transaction.section_name}")
                    print(f"Enrolled in {enrolled_count} courses")
                    
                    # Build success URL with enrollment information
                    success_params = {
                        'txnRef': txn_ref,
                        'amount': transaction.amount,
                        'subscription': 'true',
                        'enrolledCount': enrolled_count,
                        'totalCourses': len(courses_to_enroll) if 'courses_to_enroll' in locals() else available_courses.count()
                    }
                    success_url = build_payment_url('learning/payment/success', **success_params)
                    return redirect(success_url)
                    
            except PaymentTransaction.DoesNotExist:
                print(f"Transaction {txn_ref} not found")
                error_url = build_payment_url('learning/payment/cancel', txnRef=txn_ref, error='transaction_not_found')
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
        error_url = build_payment_url('learning/payment/cancel', error=str(e))
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


@login_required
def get_user_access_info_api(request):
    """
    API endpoint to get user's access_info
    Returns access_type ('free', 'subscribed', or 'section_access') and unit_limit
    
    Response:
    {
        'success': True,
        'access_info': {
            'access_type': 'free' | 'subscribed' | 'section_access',
            'unit_limit': 20 | null,
            'allowed_sections': ['読解', ...],  # List of section names user has access to
            'updated_at': 'ISO timestamp'
        }
    }
    """
    try:
        from .utils import has_active_subscription, get_user_section_access
        
        # Check if user has active subscription
        has_subscription = has_active_subscription(request.user)
        
        # Get section access (returns dict with 'allowed_sections' and 'excluded_sections')
        section_access = get_user_section_access(request.user)
        allowed_sections = section_access.get('allowed_sections', [])
        excluded_sections = section_access.get('excluded_sections', [])
        
        if has_subscription:
            access_info = {
                'access_type': 'subscribed',
                'unit_limit': None,  # Unlimited for subscribed users
                'allowed_sections': [],  # All sections for subscribed users
                'excluded_sections': [],
                'updated_at': timezone.now().isoformat(),
            }
        elif allowed_sections:
            access_info = {
                'access_type': 'section_access',
                'unit_limit': None,  # Unlimited units for purchased sections
                'allowed_sections': allowed_sections,  # List of section names, or ['*'] if all sections
                'excluded_sections': excluded_sections,  # List of excluded section names (if any)
                'updated_at': timezone.now().isoformat(),
            }
        else:
            access_info = {
                'access_type': 'free',
                'unit_limit': 20,  # Free users can only see first 20 units per sequence
                'allowed_sections': [],
                'excluded_sections': [],
                'updated_at': timezone.now().isoformat(),
            }
        
        return JsonResponse({
            'success': True,
            'access_info': access_info
        })
    except Exception as e:
        print(f"Error getting access_info: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return default free access on error
        return JsonResponse({
            'success': False,
            'error': str(e),
            'access_info': {
                'access_type': 'free',
                'unit_limit': 20,
                'allowed_sections': [],
                'updated_at': timezone.now().isoformat(),
            }
        }, status=500)


@csrf_exempt
@login_required
def toggle_subscription_status(request):
    """
    API endpoint to deactivate or reactivate subscription for testing
    Only works for staff users or the user themselves
    
    POST /api/payment/toggle-subscription/
    Body: {
        "action": "deactivate" | "reactivate",
        "username": "optional_username"  # Only for staff users
    }
    """
    try:
        # Note: json is already imported at the top of the file
        data = json.loads(request.body) if request.body else {}
        action = data.get('action', 'deactivate')  # 'deactivate' or 'reactivate'
        target_username = data.get('username')
        
        # Determine target user
        if target_username:
            # Staff users can toggle any user's subscription
            if not request.user.is_staff:
                return JsonResponse({
                    'success': False,
                    'error': 'Only staff users can toggle other users\' subscriptions'
                }, status=403)
            
            try:
                from django.contrib.auth.models import User
                target_user = User.objects.get(username=target_username)
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'User "{target_username}" not found'
                }, status=404)
        else:
            # User can only toggle their own subscription
            target_user = request.user
        
        # Find the most recent successful all-access transaction
        latest_transaction = PaymentTransaction.objects.filter(
            user=target_user,
            payment_type='all_access',
            payment_status='success'
        ).order_by('-created_at').first()
        
        if not latest_transaction:
            return JsonResponse({
                'success': False,
                'error': f'No subscription transaction found for user "{target_user.username}"'
            }, status=404)
        
        # Toggle subscription status
        if action == 'deactivate':
            # Deactivate ALL active subscriptions (both all_access and section_access)
            all_active_transactions = PaymentTransaction.objects.filter(
                user=target_user,
                payment_status='success',
                subscription_active=True
            )
            
            deactivated_count = 0
            deactivated_transactions = []
            
            for transaction in all_active_transactions:
                transaction.subscription_active = False
                transaction.save()
                deactivated_count += 1
                deactivated_transactions.append({
                    'txn_ref': transaction.txn_ref,
                    'payment_type': transaction.payment_type,
                    'section_name': transaction.section_name if transaction.payment_type == 'section_access' else None
                })
            
            print(f"🔍 [toggle_subscription] Deactivated {deactivated_count} transactions for user {target_user.username}")
            
            return JsonResponse({
                'success': True,
                'message': f'All subscriptions deactivated for user "{target_user.username}" ({deactivated_count} transactions)',
                'user': target_user.username,
                'action': 'deactivated',
                'transaction_ref': latest_transaction.txn_ref,
                'deactivated_count': deactivated_count,
                'deactivated_transactions': deactivated_transactions,
                'subscription_active': False,
                'access_info': {
                    'access_type': 'free',
                    'unit_limit': 20
                }
            })
        elif action == 'reactivate':
            latest_transaction.subscription_active = True
            if not latest_transaction.subscription_expires_at:
                # Set expiration to 1 year from now if not set
                latest_transaction.subscription_expires_at = timezone.now() + timezone.timedelta(days=365)
            latest_transaction.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Subscription reactivated for user "{target_user.username}"',
                'user': target_user.username,
                'action': 'reactivated',
                'transaction_ref': latest_transaction.txn_ref,
                'subscription_active': True,
                'subscription_expires_at': latest_transaction.subscription_expires_at.isoformat(),
                'access_info': {
                    'access_type': 'subscribed',
                    'unit_limit': None
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Invalid action: "{action}". Use "deactivate" or "reactivate"'
            }, status=400)
            
    except Exception as e:
        print(f"Error toggling subscription status: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@login_required
def activate_section_access(request):
    """
    API endpoint to activate section access for testing
    Creates a test transaction with section_access payment type
    
    POST /api/payment/activate-section-access/
    Body: {
        "section_name": "読解"  # Optional, defaults to "読解"
    }
    """
    try:
        import uuid
        # Note: json is already imported at the top of the file
        data = json.loads(request.body) if request.body else {}
        section_name = data.get('section_name', '読解')  # Default to "読解"
        
        # Create a unique transaction reference using UUID to ensure uniqueness
        # Format: SECTION_ACCESS_{uuid}_{username}
        # Use full UUID (32 chars) + username to ensure absolute uniqueness
        unique_id = str(uuid.uuid4()).replace('-', '')
        txn_ref = f'SECTION_ACCESS_{unique_id}_{request.user.username}'
        
        # Ensure txn_ref is not empty and is unique
        if not txn_ref or len(txn_ref.strip()) == 0:
            return JsonResponse({
                'success': False,
                'error': 'Failed to generate transaction reference'
            }, status=500)
        
        # Double-check uniqueness (should never happen with UUID, but just in case)
        max_retries = 10
        retry_count = 0
        while PaymentTransaction.objects.filter(txn_ref=txn_ref).exists() and retry_count < max_retries:
            unique_id = str(uuid.uuid4()).replace('-', '')
            txn_ref = f'SECTION_ACCESS_{unique_id}_{request.user.username}'
            retry_count += 1
            print(f"⚠️ [activate_section_access] txn_ref collision detected, retry {retry_count}: {txn_ref}")
        
        if retry_count >= max_retries:
            return JsonResponse({
                'success': False,
                'error': 'Failed to generate unique transaction reference after multiple attempts'
            }, status=500)
        
        print(f"🔍 [activate_section_access] Generated txn_ref: {txn_ref}")
        
        # Check if user already has this section access
        existing_transaction = PaymentTransaction.objects.filter(
            user=request.user,
            payment_type='section_access',
            section_name=section_name,
            payment_status='success',
            subscription_active=True
        ).order_by('-created_at').first()
        
        if existing_transaction and existing_transaction.is_subscription_active():
            return JsonResponse({
                'success': True,
                'message': f'Section "{section_name}" access already active',
                'user': request.user.username,
                'section_name': section_name,
                'transaction_ref': existing_transaction.txn_ref,
                'access_info': {
                    'access_type': 'section_access',
                    'allowed_sections': [section_name],
                    'unit_limit': None
                }
            })
        
        # Create new transaction
        try:
            transaction = PaymentTransaction.objects.create(
                user=request.user,
                amount=0,  # Free for testing
                currency='VND',
                txn_ref=txn_ref,  # Explicitly set txn_ref
                payment_method='test',
                payment_type='section_access',
                section_name=section_name,
                course_id=None,
                course_name=f'Section Access: {section_name}',
                payment_status='success',
                subscription_active=True,
                subscription_expires_at=timezone.now() + timezone.timedelta(days=365),
                enrollment_created=False,
            )
        except Exception as create_error:
            error_str = str(create_error)
            print(f"❌ [activate_section_access] Error creating transaction: {error_str}")
            print(f"❌ [activate_section_access] Attempted txn_ref: {txn_ref}")
            
            # If creation fails due to duplicate txn_ref, try one more time with new UUID
            if 'Duplicate entry' in error_str or 'txn_ref' in error_str or 'duplicate' in error_str.lower():
                print(f"⚠️ [activate_section_access] Duplicate txn_ref detected, regenerating...")
                # Use full UUID this time
                unique_id = str(uuid.uuid4()).replace('-', '')
                txn_ref = f'SECTION_ACCESS_{unique_id}_{request.user.username}'
                print(f"🔄 [activate_section_access] New txn_ref: {txn_ref}")
                
                try:
                    transaction = PaymentTransaction.objects.create(
                        user=request.user,
                        amount=0,
                        currency='VND',
                        txn_ref=txn_ref,
                        payment_method='test',
                        payment_type='section_access',
                        section_name=section_name,
                        course_id=None,
                        course_name=f'Section Access: {section_name}',
                        payment_status='success',
                        subscription_active=True,
                        subscription_expires_at=timezone.now() + timezone.timedelta(days=365),
                        enrollment_created=False,
                    )
                    print(f"✅ [activate_section_access] Transaction created successfully with new txn_ref")
                except Exception as retry_error:
                    print(f"❌ [activate_section_access] Retry also failed: {str(retry_error)}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Failed to create transaction: {str(retry_error)}'
                    }, status=500)
            else:
                raise  # Re-raise if it's a different error
        
        # Enroll user in ALL courses (for section access, enroll in all courses)
        from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
        from common.djangoapps.student.models import CourseEnrollment
        from common.djangoapps.course_modes.models import CourseMode
        from django.db.models import Q
        
        enrolled_count = 0
        now = timezone.now()
        
        # Get ALL available courses (no filtering for section access)
        # For section access, we want to enroll in all courses so user can access the section in any course
        all_courses = CourseOverview.objects.all()
        
        # Exclude courses user is already enrolled in
        already_enrolled = CourseEnrollment.objects.filter(
            user=request.user,
            is_active=True
        ).values_list('course_id', flat=True)
        
        courses_to_enroll = all_courses.exclude(id__in=already_enrolled)
        
        print(f"🔍 [activate_section_access] Enrolling user {request.user.username} in {courses_to_enroll.count()} courses for section '{section_name}'")
        
        # Enroll in each course (enroll in ALL courses for section access)
        for course in courses_to_enroll:
            try:
                # Skip courses that are not currently open for enrollment (optional check)
                # But for section access, we still try to enroll even if enrollment period has passed
                enrollment = CourseEnrollment.enroll(
                    user=request.user,
                    course_key=course.id,
                    mode=CourseMode.VERIFIED,
                    check_access=False  # Set to False to allow enrollment even if enrollment period has passed
                )
                if enrollment:
                    enrolled_count += 1
                    print(f"✅ Enrolled in course {course.id}")
            except Exception as e:
                # Try with check_access=True if check_access=False fails
                try:
                    enrollment = CourseEnrollment.enroll(
                        user=request.user,
                        course_key=course.id,
                        mode=CourseMode.VERIFIED,
                        check_access=True
                    )
                    if enrollment:
                        enrolled_count += 1
                        print(f"✅ Enrolled in course {course.id} (with check_access)")
                except Exception as e2:
                    print(f"❌ Failed to enroll in course {course.id}: {str(e2)}")
                    continue
        
        transaction.enrollment_created = enrolled_count > 0
        transaction.enrollment_date = timezone.now() if enrolled_count > 0 else None
        transaction.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Section "{section_name}" access activated',
            'user': request.user.username,
            'section_name': section_name,
            'transaction_ref': transaction.txn_ref,
            'enrolled_courses': enrolled_count,
            'access_info': {
                'access_type': 'section_access',
                'allowed_sections': [section_name],
                'unit_limit': None
            }
        })
        
    except Exception as e:
        print(f"Error activating section access: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)