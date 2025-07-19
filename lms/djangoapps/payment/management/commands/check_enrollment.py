from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from lms.djangoapps.payment.models import PaymentTransaction
from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from lms.djangoapps.payment.utils import has_active_subscription, get_user_subscription_info


class Command(BaseCommand):
    help = 'Check if user enrollment was successful after payment'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username to check enrollment for'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed enrollment information'
        )

    def handle(self, *args, **options):
        username = options['username']
        detailed = options['detailed']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        self.stdout.write(f'\n🔍 ENROLLMENT CHECK FOR USER: {username}')
        self.stdout.write('=' * 60)
        self.stdout.write(f'👤 User: {user.username}')
        self.stdout.write(f'📧 Email: {user.email}')
        self.stdout.write(f'🆔 User ID: {user.id}')
        self.stdout.write('=' * 60)

        # Check subscription status
        self.check_subscription_status(user)
        
        # Check payment transactions
        self.check_payment_transactions(user)
        
        # Check course enrollments
        self.check_course_enrollments(user, detailed)
        
        # Show summary
        self.show_summary(user)

    def check_subscription_status(self, user):
        """Check user's subscription status"""
        self.stdout.write('\n1️⃣ SUBSCRIPTION STATUS')
        self.stdout.write('-' * 40)
        
        has_subscription = has_active_subscription(user)
        subscription_info = get_user_subscription_info(user)
        
        if has_subscription:
            self.stdout.write(self.style.SUCCESS('✅ User has ACTIVE all-access subscription'))
            if subscription_info:
                self.stdout.write(f'📅 Expires: {subscription_info["expires_at"]}')
                self.stdout.write(f'⏰ Days remaining: {subscription_info["days_remaining"]}')
                self.stdout.write(f'💰 Amount paid: {subscription_info["amount"]} VND')
        else:
            self.stdout.write(self.style.WARNING('❌ User has NO active subscription'))

    def check_payment_transactions(self, user):
        """Check user's payment transactions"""
        self.stdout.write('\n2️⃣ PAYMENT TRANSACTIONS')
        self.stdout.write('-' * 40)
        
        transactions = PaymentTransaction.objects.filter(
            user=user,
            payment_type='all_access'
        ).order_by('-created_at')
        
        if transactions.exists():
            self.stdout.write(f'💰 Found {transactions.count()} all-access transactions:')
            for txn in transactions:
                status_icon = "✅" if txn.payment_status == 'success' else "❌"
                self.stdout.write(f'   {status_icon} {txn.txn_ref}')
                self.stdout.write(f'      Amount: {txn.amount} VND')
                self.stdout.write(f'      Status: {txn.payment_status}')
                self.stdout.write(f'      Created: {txn.created_at}')
                if txn.subscription_active:
                    days_remaining = (txn.subscription_expires_at - timezone.now()).days
                    self.stdout.write(f'      Expires: {txn.subscription_expires_at} ({days_remaining} days)')
                self.stdout.write('')
        else:
            self.stdout.write('❌ No all-access transactions found')

    def check_course_enrollments(self, user, detailed=False):
        """Check user's course enrollments"""
        self.stdout.write('\n3️⃣ COURSE ENROLLMENTS')
        self.stdout.write('-' * 40)
        
        enrollments = CourseEnrollment.objects.filter(
            user=user,
            is_active=True
        ).select_related('course')
        
        if enrollments.exists():
            self.stdout.write(f'📚 User is enrolled in {enrollments.count()} courses:')
            if detailed:
                for enrollment in enrollments:
                    self.stdout.write(f'   📖 {enrollment.course.display_name}')
                    self.stdout.write(f'      Mode: {enrollment.mode}')
                    self.stdout.write(f'      Created: {enrollment.created}')
                    self.stdout.write('')
            else:
                self.stdout.write(f'   📊 Total enrollments: {enrollments.count()}')
        else:
            self.stdout.write('❌ User is not enrolled in any courses')
        
        # Check available courses
        all_courses = CourseOverview.objects.filter(
            start__lte=timezone.now(),
            end__gte=timezone.now(),
        )
        
        self.stdout.write(f'\n📖 Available courses: {all_courses.count()}')
        self.stdout.write(f'📚 User enrolled: {enrollments.count()}')
        
        # Check if user has subscription
        has_subscription = has_active_subscription(user)
        if has_subscription:
            self.stdout.write('✅ User has all-access - should be able to access all courses')
        else:
            self.stdout.write('❌ User needs individual enrollment for each course')

    def show_summary(self, user):
        """Show final summary"""
        self.stdout.write('\n6️⃣ FINAL SUMMARY')
        self.stdout.write('-' * 40)
        
        has_subscription = has_active_subscription(user)
        transactions = PaymentTransaction.objects.filter(
            user=user,
            payment_type='all_access'
        ).count()
        enrollments = CourseEnrollment.objects.filter(
            user=user,
            is_active=True
        ).count()
        all_courses = CourseOverview.objects.filter(
            start__lte=timezone.now(),
            end__gte=timezone.now(),
        ).count()
        
        self.stdout.write(f'🎓 Subscription: {"✅ Active" if has_subscription else "❌ Inactive"}')
        self.stdout.write(f'💰 Transactions: {transactions}')
        self.stdout.write(f'📚 Enrollments: {enrollments}')
        self.stdout.write(f'📖 Available courses: {all_courses}')
        
        if has_subscription and enrollments.count() > 0:
            self.stdout.write(self.style.SUCCESS('🎉 SUCCESS: User has subscription and is enrolled in courses!'))
        elif has_subscription and enrollments.count() == 0:
            self.stdout.write(self.style.WARNING('⚠️ WARNING: User has subscription but no enrollments'))
        elif not has_subscription and enrollments.count() > 0:
            self.stdout.write('ℹ️ INFO: User has individual course enrollments')
        else:
            self.stdout.write(self.style.ERROR('❌ ISSUE: User has no subscription and no enrollments')) 