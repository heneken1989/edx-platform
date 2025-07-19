from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from lms.djangoapps.payment.models import PaymentTransaction
from lms.djangoapps.payment.utils import has_active_subscription, get_user_subscription_info


class Command(BaseCommand):
    help = 'Check and manage all-access subscriptions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Check subscription for specific user'
        )
        parser.add_argument(
            '--list-all',
            action='store_true',
            help='List all active subscriptions'
        )
        parser.add_argument(
            '--expired',
            action='store_true',
            help='Show expired subscriptions'
        )
        parser.add_argument(
            '--renew',
            type=str,
            help='Renew subscription for specific user (username)'
        )

    def handle(self, *args, **options):
        if options['username']:
            self.check_user_subscription(options['username'])
        elif options['list_all']:
            self.list_all_subscriptions()
        elif options['expired']:
            self.list_expired_subscriptions()
        elif options['renew']:
            self.renew_subscription(options['renew'])
        else:
            self.stdout.write(self.style.ERROR('Please specify an action. Use --help for options.'))
            return

    def check_user_subscription(self, username):
        """Check subscription status for a specific user"""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        self.stdout.write(f'\n🔍 Checking subscription for user: {username}')
        self.stdout.write('=' * 50)

        # Check if user has active subscription
        has_subscription = has_active_subscription(user)
        subscription_info = get_user_subscription_info(user)

        if has_subscription and subscription_info:
            self.stdout.write(self.style.SUCCESS(f'✅ User has ACTIVE subscription'))
            self.stdout.write(f'📅 Expires: {subscription_info["expires_at"]}')
            self.stdout.write(f'⏰ Days remaining: {subscription_info["days_remaining"]}')
            self.stdout.write(f'💰 Amount paid: {subscription_info["amount"]} VND')
        else:
            self.stdout.write(self.style.WARNING('❌ User has NO active subscription'))

        # Show recent transactions
        transactions = PaymentTransaction.objects.filter(
            user=user,
            payment_type='all_access'
        ).order_by('-created_at')[:5]

        if transactions:
            self.stdout.write(f'\n📋 Recent transactions:')
            for txn in transactions:
                status_icon = '✅' if txn.payment_status == 'success' else '❌'
                self.stdout.write(f'{status_icon} {txn.txn_ref} - {txn.amount} VND - {txn.payment_status}')

    def list_all_subscriptions(self):
        """List all active subscriptions"""
        self.stdout.write('\n📊 All Active Subscriptions')
        self.stdout.write('=' * 50)

        active_transactions = PaymentTransaction.objects.filter(
            payment_type='all_access',
            payment_status='success',
            subscription_active=True
        ).select_related('user').order_by('-created_at')

        if not active_transactions:
            self.stdout.write(self.style.WARNING('No active subscriptions found'))
            return

        for txn in active_transactions:
            if txn.is_subscription_active():
                days_remaining = (txn.subscription_expires_at - timezone.now()).days
                self.stdout.write(f'👤 {txn.user.username}')
                self.stdout.write(f'   💰 Amount: {txn.amount} VND')
                self.stdout.write(f'   📅 Expires: {txn.subscription_expires_at}')
                self.stdout.write(f'   ⏰ Days remaining: {days_remaining}')
                self.stdout.write(f'   🆔 Transaction: {txn.txn_ref}')
                self.stdout.write('')

    def list_expired_subscriptions(self):
        """List expired subscriptions"""
        self.stdout.write('\n⏰ Expired Subscriptions')
        self.stdout.write('=' * 50)

        expired_transactions = PaymentTransaction.objects.filter(
            payment_type='all_access',
            payment_status='success',
            subscription_expires_at__lt=timezone.now()
        ).select_related('user').order_by('-subscription_expires_at')

        if not expired_transactions:
            self.stdout.write(self.style.SUCCESS('No expired subscriptions found'))
            return

        for txn in expired_transactions:
            days_expired = (timezone.now() - txn.subscription_expires_at).days
            self.stdout.write(f'👤 {txn.user.username}')
            self.stdout.write(f'   💰 Amount: {txn.amount} VND')
            self.stdout.write(f'   📅 Expired: {txn.subscription_expires_at}')
            self.stdout.write(f'   ⏰ Days expired: {days_expired}')
            self.stdout.write(f'   🆔 Transaction: {txn.txn_ref}')
            self.stdout.write('')

    def renew_subscription(self, username):
        """Renew subscription for a user"""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        self.stdout.write(f'\n🔄 Renewing subscription for user: {username}')
        self.stdout.write('=' * 50)

        # Find the most recent successful transaction
        latest_transaction = PaymentTransaction.objects.filter(
            user=user,
            payment_type='all_access',
            payment_status='success'
        ).order_by('-created_at').first()

        if not latest_transaction:
            self.stdout.write(self.style.ERROR('No previous subscription found for this user'))
            return

        # Renew the subscription
        latest_transaction.subscription_expires_at = timezone.now() + timezone.timedelta(days=365)
        latest_transaction.subscription_active = True
        latest_transaction.save()

        self.stdout.write(self.style.SUCCESS(f'✅ Subscription renewed for {username}'))
        self.stdout.write(f'📅 New expiration: {latest_transaction.subscription_expires_at}')
        self.stdout.write(f'💰 Original amount: {latest_transaction.amount} VND') 