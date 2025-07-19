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