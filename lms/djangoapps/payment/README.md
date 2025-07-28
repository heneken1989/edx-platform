# Payment and Subscription System

Hệ thống thanh toán và đăng ký khóa học cho Open edX với hỗ trợ VNPay và All-Access Subscription.

## Tính năng

### 1. Thanh toán khóa học đơn lẻ
- Thanh toán cho một khóa học cụ thể
- Tích hợp VNPay payment gateway
- Tự động enroll user sau khi thanh toán thành công

### 2. All-Access Subscription
- Thanh toán một lần để truy cập tất cả khóa học
- Subscription có thời hạn (mặc định 1 năm)
- Tự động enroll user vào tất cả khóa học hiện có

## Cấu trúc Database

### PaymentTransaction Model
```python
class PaymentTransaction(models.Model):
    # Payment information
    txn_ref = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='VND')
    payment_method = models.CharField(max_length=50, default='vnpay')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    
    # Course information (for single course)
    course_id = models.CharField(max_length=100, blank=True, null=True)
    course_name = models.CharField(max_length=200, blank=True, null=True)
    
    # User information
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Subscription information (for all-access)
    subscription_active = models.BooleanField(default=False)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## API Endpoints

### 1. Tạo thanh toán
```
POST /api/payment/create/
```

**Request Body:**
```json
{
    "amount": 500000,
    "paymentType": "all_access",  // "single_course" hoặc "all_access"
    "courseId": "course-v1:edX+DemoX+Demo_Course",  // Chỉ cần cho single_course
    "courseName": "Demo Course",  // Chỉ cần cho single_course
    "useSimulator": false
}
```

**Response:**
```json
{
    "success": true,
    "paymentUrl": "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?...",
    "txnRef": "DEMO1234567890",
    "status": "pending",
    "paymentType": "all_access"
}
```

### 2. Kiểm tra subscription status
```
GET /api/payment/subscription/status/
```

**Response:**
```json
{
    "success": true,
    "has_subscription": true,
    "subscription_info": {
        "subscription_active": true,
        "expires_at": "2025-01-01T00:00:00Z",
        "days_remaining": 300,
        "transaction_ref": "DEMO1234567890",
        "amount_paid": 500000,
        "currency": "VND",
        "created_at": "2024-01-01T00:00:00Z"
    }
}
```

### 3. Kiểm tra quyền truy cập khóa học
```
GET /api/payment/course/{course_key}/access/
```

**Response:**
```json
{
    "success": true,
    "course_key": "course-v1:edX+DemoX+Demo_Course",
    "access_status": {
        "can_access": true,
        "access_type": "subscription",
        "subscription_info": {...}
    }
}
```

### 4. Lấy danh sách khóa học user có thể truy cập
```
GET /api/payment/courses/
```

**Response:**
```json
{
    "success": true,
    "has_all_access": true,
    "courses": [
        {
            "id": "course-v1:edX+DemoX+Demo_Course",
            "display_name": "Demo Course",
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-12-31T23:59:59Z"
        }
    ],
    "total_courses": 1
}
```

## Utility Functions

### 1. Kiểm tra subscription
```python
from lms.djangoapps.payment.utils import has_active_subscription

if has_active_subscription(user):
    # User có subscription active
    pass
```

### 2. Kiểm tra quyền truy cập khóa học
```python
from lms.djangoapps.payment.utils import can_access_course

if can_access_course(user, course_key):
    # User có thể truy cập khóa học
    pass
```

### 3. Lấy thông tin subscription
```python
from lms.djangoapps.payment.utils import get_user_subscription_info

subscription_info = get_user_subscription_info(user)
if subscription_info:
    print(f"Days remaining: {subscription_info['days_remaining']}")
```

## Management Commands

### Enroll user vào tất cả khóa học
```bash
python manage.py lms enroll_user_all_courses username --mode verified --force
```

**Options:**
- `username`: Tên user cần enroll
- `--mode`: Mode enrollment (default: verified)
- `--force`: Force re-enrollment nếu đã enrolled

## Cấu hình VNPay

Tạo file `.env.vnpay` trong thư mục gốc:

```env
VNPAY_TMN_CODE=your_tmn_code
VNPAY_HASH_SECRET=your_hash_secret
VNPAY_USE_SANDBOX=True
```

## Workflow

### 1. Single Course Payment
1. User chọn khóa học
2. Gọi API `/api/payment/create/` với `paymentType: "single_course"`
3. Redirect user đến VNPay
4. Sau khi thanh toán thành công, user được enroll vào khóa học đó

### 2. All-Access Subscription
1. User chọn gói All-Access
2. Gọi API `/api/payment/create/` với `paymentType: "all_access"`
3. Redirect user đến VNPay
4. Sau khi thanh toán thành công, user được enroll vào tất cả khóa học

### 3. Kiểm tra quyền truy cập
1. Khi user truy cập khóa học, kiểm tra subscription status
2. Nếu có subscription active → cho phép truy cập
3. Nếu không có subscription → kiểm tra enrollment riêng lẻ

## Lưu ý

- Subscription mặc định có thời hạn 1 năm
- User có subscription sẽ được enroll vào tất cả khóa học hiện có
- Hệ thống tự động kiểm tra và cập nhật trạng thái subscription
- Có thể mở rộng để hỗ trợ nhiều payment gateway khác 

# Payment App Configuration

## Learning MFE URL Configuration

The payment app now dynamically retrieves the Learning MFE base URL from Django settings instead of hardcoding it. This makes the app more flexible and easier to configure across different environments.

### Configuration Options

The app will look for the Learning MFE URL in the following order:

1. **LEARNING_MICROFRONTEND_URL** setting (recommended)
2. **MFE_CONFIG['LEARNING_BASE_URL']** setting
3. **Fallback URL** for development

### Setting up the Learning MFE URL

#### Option 1: Using LEARNING_MICROFRONTEND_URL (Recommended)

Add this to your Django settings file (e.g., `lms/envs/common.py`):

```python
# Learning MFE URL
LEARNING_MICROFRONTEND_URL = 'http://localhost:2000'  # Development
# LEARNING_MICROFRONTEND_URL = 'https://learning.yourdomain.com'  # Production
```

#### Option 2: Using MFE_CONFIG

Add this to your Django settings file:

```python
MFE_CONFIG = {
    # ... other config ...
    'LEARNING_BASE_URL': 'http://localhost:2000',  # Development
    # 'LEARNING_BASE_URL': 'https://learning.yourdomain.com',  # Production
}
```

#### Option 3: Environment Variables

You can also set the URL via environment variables:

```bash
export LEARNING_MICROFRONTEND_URL="http://localhost:2000"
```

### Usage in Code

The payment app provides utility functions to build URLs:

```python
from lms.djangoapps.payment.settings import get_learning_base_url
from lms.djangoapps.payment.views import build_payment_url

# Get the base URL
base_url = get_learning_base_url()

# Build a payment URL with parameters
success_url = build_payment_url('payment/success', 
                               txnRef='12345', 
                               amount=100000, 
                               subscription='true')
```

### Benefits

- **Environment Flexibility**: Easy to switch between development, staging, and production
- **No Hardcoding**: URLs are configured centrally in Django settings
- **Fallback Support**: Multiple configuration options with sensible defaults
- **Clean Code**: Utility functions make URL building more readable

### Migration from Hardcoded URLs

If you were previously using hardcoded URLs like:
```python
# Old way (not recommended)
success_url = "http://apps.local.openedx.io:2000/learning/payment/success"
```

You can now use:
```python
# New way (recommended)
success_url = build_payment_url('payment/success', txnRef=txn_ref)
```

This makes your code more maintainable and environment-agnostic. 