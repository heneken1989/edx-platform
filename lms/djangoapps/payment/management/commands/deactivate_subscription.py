"""
Management command to deactivate subscription for a user
Usage: python manage.py lms deactivate_subscription <username>
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from lms.djangoapps.payment.models import PaymentTransaction


class Command(BaseCommand):
    help = 'Deactivate subscription for a user (for testing purposes)'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username of the user to deactivate subscription'
        )
        parser.add_argument(
            '--reactivate',
            action='store_true',
            help='Reactivate subscription instead of deactivating'
        )

    def handle(self, *args, **options):
        username = options['username']
        reactivate = options.get('reactivate', False)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        # Find the most recent successful all-access transaction
        latest_transaction = PaymentTransaction.objects.filter(
            user=user,
            payment_type='all_access',
            payment_status='success'
        ).order_by('-created_at').first()

        if not latest_transaction:
            self.stdout.write(
                self.style.WARNING(f'⚠️  No subscription transaction found for user "{username}"')
            )
            return

        if reactivate:
            # Reactivate subscription
            latest_transaction.subscription_active = True
            if not latest_transaction.subscription_expires_at:
                # Set expiration to 1 year from now if not set
                latest_transaction.subscription_expires_at = timezone.now() + timezone.timedelta(days=365)
            latest_transaction.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Subscription reactivated for user "{username}"\n'
                    f'   Transaction: {latest_transaction.txn_ref}\n'
                    f'   Expires at: {latest_transaction.subscription_expires_at}'
                )
            )
        else:
            # Deactivate subscription
            latest_transaction.subscription_active = False
            latest_transaction.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Subscription deactivated for user "{username}"\n'
                    f'   Transaction: {latest_transaction.txn_ref}\n'
                    f'   User will now have free access (20 units limit)'
                )
            )

