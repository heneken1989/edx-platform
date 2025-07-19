from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PaymentTransaction(models.Model):
    """
    Model to store payment transaction information
    """
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('single_course', 'Single Course'),
        ('all_access', 'All Access Subscription'),
    ]
    
    # Payment information
    txn_ref = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='VND')
    payment_method = models.CharField(max_length=50, default='vnpay')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='single_course')
    
    # Course information (for single course payment)
    course_id = models.CharField(max_length=100, blank=True, null=True)
    course_name = models.CharField(max_length=200, blank=True, null=True)
    
    # User information
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Enrollment status
    enrollment_created = models.BooleanField(default=False)
    enrollment_date = models.DateTimeField(null=True, blank=True)
    
    # Subscription information (for all-access)
    subscription_active = models.BooleanField(default=False)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_transaction'
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'
    
    def __str__(self):
        if self.payment_type == 'all_access':
            return f"{self.txn_ref} - All Access Subscription - {self.payment_status}"
        else:
            return f"{self.txn_ref} - {self.course_name} - {self.payment_status}"
    
    def mark_as_success(self):
        """Mark transaction as successful and create enrollment"""
        self.payment_status = 'success'
        self.save()
        
        if self.payment_type == 'all_access':
            self.create_all_access_subscription()
        else:
            self.create_enrollment()
    
    def create_enrollment(self):
        """Create course enrollment for the user (single course)"""
        if not self.enrollment_created and self.course_id:
            try:
                from common.djangoapps.student.models import CourseEnrollment
                from opaque_keys.edx.keys import CourseKey
                
                # Create course enrollment
                course_key = CourseKey.from_string(self.course_id)
                enrollment, created = CourseEnrollment.enroll(
                    user=self.user,
                    course_key=course_key,
                    mode='verified'  # or 'honor' based on your needs
                )
                
                if created:
                    self.enrollment_created = True
                    self.enrollment_date = timezone.now()
                    self.save()
                    print(f"Enrollment created for user {self.user.username} in course {self.course_id}")
                else:
                    print(f"Enrollment already exists for user {self.user.username} in course {self.course_id}")
                    
            except Exception as e:
                print(f"Error creating enrollment: {str(e)}")
                # Don't raise exception to avoid breaking payment flow
    
    def create_all_access_subscription(self):
        """Create all-access subscription for the user"""
        if not self.subscription_active:
            try:
                from common.djangoapps.student.models import CourseEnrollment
                from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
                from opaque_keys.edx.keys import CourseKey
                
                print(f"Starting all-access subscription creation for user {self.user.username}")
                
                # Set subscription as active
                self.subscription_active = True
                # Set expiration to 1 year from now (you can adjust this)
                self.subscription_expires_at = timezone.now() + timezone.timedelta(days=365)
                self.save()
                
                print(f"Subscription activated for user {self.user.username}, expires at {self.subscription_expires_at}")
                
                # Get all available courses (including future courses for subscription)
                all_courses = CourseOverview.objects.filter(
                    start__lte=timezone.now() + timezone.timedelta(days=30),  # Include courses starting within 30 days
                    end__gte=timezone.now(),    # Course hasn't ended
                ).order_by('start')
                
                print(f"Found {all_courses.count()} courses to enroll user in")
                
                enrolled_count = 0
                already_enrolled_count = 0
                error_count = 0
                
                for course_overview in all_courses:
                    try:
                        # Check if user is already enrolled
                        existing_enrollment = CourseEnrollment.get_enrollment(
                            self.user, 
                            course_overview.id
                        )
                        
                        if not existing_enrollment or not existing_enrollment.is_active:
                            # Enroll user in the course
                            enrollment, created = CourseEnrollment.enroll(
                                user=self.user,
                                course_key=course_overview.id,
                                mode='verified'  # Give verified access to all courses
                            )
                            
                            if created:
                                enrolled_count += 1
                                print(f"✅ Enrolled user {self.user.username} in course {course_overview.display_name} ({course_overview.id})")
                            else:
                                print(f"⚠️ Enrollment already exists for user {self.user.username} in course {course_overview.display_name}")
                                already_enrolled_count += 1
                        else:
                            print(f"ℹ️ User {self.user.username} already enrolled in course {course_overview.display_name}")
                            already_enrolled_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        print(f"❌ Error enrolling user in course {course_overview.id}: {str(e)}")
                        continue
                
                print(f"🎉 All-access subscription completed for user {self.user.username}")
                print(f"📊 Summary: {enrolled_count} new enrollments, {already_enrolled_count} already enrolled, {error_count} errors")
                
                # Update transaction with enrollment info
                self.enrollment_created = True
                self.enrollment_date = timezone.now()
                self.save()
                
                return {
                    'success': True,
                    'enrolled_count': enrolled_count,
                    'already_enrolled_count': already_enrolled_count,
                    'error_count': error_count,
                    'total_courses': all_courses.count()
                }
                
            except Exception as e:
                print(f"❌ Error creating all-access subscription: {str(e)}")
                import traceback
                traceback.print_exc()
                # Don't raise exception to avoid breaking payment flow
                return {
                    'success': False,
                    'error': str(e)
                }
        else:
            print(f"ℹ️ Subscription already active for user {self.user.username}")
            return {
                'success': True,
                'message': 'Subscription already active'
            }
    
    def is_subscription_active(self):
        """Check if user's all-access subscription is still active"""
        if not self.subscription_active:
            return False
        
        if self.subscription_expires_at and self.subscription_expires_at < timezone.now():
            # Subscription has expired
            self.subscription_active = False
            self.save()
            return False
        
        return True 