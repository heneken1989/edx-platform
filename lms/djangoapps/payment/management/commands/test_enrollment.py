from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from lms.djangoapps.payment.models import PaymentTransaction
from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


class Command(BaseCommand):
    help = 'Test enrollment functionality for all-access subscription'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            required=True,
            help='Username to test enrollment for'
        )
        parser.add_argument(
            '--create-test-transaction',
            action='store_true',
            help='Create a test payment transaction'
        )
        parser.add_argument(
            '--enroll-all',
            action='store_true',
            help='Enroll user in all available courses'
        )

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        self.stdout.write(f'\n🧪 Testing enrollment for user: {username}')
        self.stdout.write('=' * 50)

        if options['create_test_transaction']:
            self.create_test_transaction(user)
        
        if options['enroll_all']:
            self.enroll_user_in_all_courses(user)
        
        self.show_enrollment_status(user)

    def create_test_transaction(self, user):
        """Create a test payment transaction"""
        self.stdout.write('\n💰 Creating test payment transaction...')
        
        # Generate unique transaction reference
        import time
        txn_ref = f'TEST{int(time.time())}'
        
        # Create test transaction
        transaction = PaymentTransaction.objects.create(
            txn_ref=txn_ref,
            amount=1000000,  # 1,000,000 VND
            currency='VND',
            payment_method='vnpay',
            payment_status='success',
            payment_type='all_access',
            course_id=None,
            course_name='Gói All Access - Truy cập tất cả khóa học',
            user=user,
            subscription_active=True,
            subscription_expires_at=timezone.now() + timezone.timedelta(days=365)
        )
        
        self.stdout.write(self.style.SUCCESS(f'✅ Test transaction created: {txn_ref}'))
        self.stdout.write(f'   Amount: {transaction.amount} VND')
        self.stdout.write(f'   Expires: {transaction.subscription_expires_at}')
        
        return transaction

    def enroll_user_in_all_courses(self, user):
        """Enroll user in all available courses"""
        self.stdout.write('\n📚 Enrolling user in all available courses...')
        
        # Get all available courses
        all_courses = CourseOverview.objects.filter(
            start__lte=timezone.now() + timezone.timedelta(days=30),
            end__gte=timezone.now(),
        ).order_by('start')
        
        self.stdout.write(f'Found {all_courses.count()} courses to enroll in')
        
        enrolled_count = 0
        already_enrolled_count = 0
        error_count = 0
        
        for course_overview in all_courses:
            try:
                # Check if user is already enrolled
                existing_enrollment = CourseEnrollment.get_enrollment(
                    user, 
                    course_overview.id
                )
                
                if not existing_enrollment or not existing_enrollment.is_active:
                    # Enroll user in the course
                    enrollment, created = CourseEnrollment.enroll(
                        user=user,
                        course_key=course_overview.id,
                        mode='verified'
                    )
                    
                    if created:
                        enrolled_count += 1
                        self.stdout.write(f'✅ Enrolled in: {course_overview.display_name}')
                    else:
                        self.stdout.write(f'⚠️ Already enrolled in: {course_overview.display_name}')
                        already_enrolled_count += 1
                else:
                    self.stdout.write(f'ℹ️ Already enrolled in: {course_overview.display_name}')
                    already_enrolled_count += 1
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f'❌ Error enrolling in {course_overview.id}: {str(e)}'))
                continue
        
        self.stdout.write(f'\n📊 Enrollment Summary:')
        self.stdout.write(f'   ✅ New enrollments: {enrolled_count}')
        self.stdout.write(f'   ℹ️ Already enrolled: {already_enrolled_count}')
        self.stdout.write(f'   ❌ Errors: {error_count}')

    def show_enrollment_status(self, user):
        """Show current enrollment status"""
        self.stdout.write('\n📋 Current Enrollment Status:')
        self.stdout.write('=' * 50)
        
        # Check subscription status
        from lms.djangoapps.payment.utils import has_active_subscription
        has_subscription = has_active_subscription(user)
        
        if has_subscription:
            self.stdout.write(self.style.SUCCESS('✅ User has active all-access subscription'))
        else:
            self.stdout.write(self.style.WARNING('❌ User has no active subscription'))
        
        # Show individual enrollments
        enrollments = CourseEnrollment.objects.filter(
            user=user,
            is_active=True
        ).select_related('course')
        
        self.stdout.write(f'\n📚 Individual Course Enrollments ({enrollments.count()}):')
        
        for enrollment in enrollments:
            self.stdout.write(f'   📖 {enrollment.course.display_name}')
            self.stdout.write(f'      Mode: {enrollment.mode}')
            self.stdout.write(f'      Created: {enrollment.created}')
            self.stdout.write('')
        
        # Show recent transactions
        transactions = PaymentTransaction.objects.filter(
            user=user,
            payment_type='all_access'
        ).order_by('-created_at')[:3]
        
        if transactions:
            self.stdout.write('💰 Recent All-Access Transactions:')
            for txn in transactions:
                status_icon = '✅' if txn.payment_status == 'success' else '❌'
                self.stdout.write(f'   {status_icon} {txn.txn_ref} - {txn.amount} VND - {txn.payment_status}')
                if txn.subscription_active:
                    days_remaining = (txn.subscription_expires_at - timezone.now()).days
                    self.stdout.write(f'      Expires: {txn.subscription_expires_at} ({days_remaining} days remaining)')
                self.stdout.write('') 