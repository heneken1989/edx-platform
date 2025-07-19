from django.urls import path
from . import views

app_name = 'payment'

urlpatterns = [
    path('test/', views.payment_test, name='payment_test'),
    path('create/', views.create_payment, name='create_payment_api'),
    path('callback/', views.vnpay_callback, name='vnpay_callback'),
    path('subscription/status/', views.check_subscription_status, name='check_subscription_status'),
    path('subscription/details/', views.get_subscription_details, name='get_subscription_details'),
    path('enrollment/status/', views.check_enrollment_status, name='check_enrollment_status'),
    path('course/<str:course_key>/access/', views.check_course_access, name='check_course_access'),
    path('courses/', views.get_all_courses_for_user, name='get_all_courses_for_user'),
] 