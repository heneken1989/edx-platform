from django.urls import path
from . import views

app_name = 'payment'

urlpatterns = [
    path('test/', views.payment_test, name='payment_test'),
    path('csrf-token/', views.get_csrf_token, name='get_csrf_token'),
    path('create/', views.create_payment, name='create_payment_api'),
    path('callback/', views.vnpay_callback, name='vnpay_callback'),
    path('subscription/status/', views.check_subscription_status, name='check_subscription_status'),
    path('enrollment/status/', views.check_enrollment_status, name='check_enrollment_status'),
    path('course/<str:course_key>/access/', views.check_course_access, name='check_course_access'),
    path('auto-enroll-all/', views.auto_enroll_all_courses, name='auto_enroll_all_courses'),
    path('test-auto-enroll-hh/', views.test_auto_enroll_hh, name='test_auto_enroll_hh'),
] 