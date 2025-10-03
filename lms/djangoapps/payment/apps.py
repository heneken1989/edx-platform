from django.apps import AppConfig


class PaymentConfig(AppConfig):
    name = 'lms.djangoapps.payment'
    verbose_name = 'Payment'
    
    def ready(self):
        """
        Import signal handlers when the app is ready
        """
        try:
            import lms.djangoapps.payment.signals  # noqa F401
            print("Payment app signals imported successfully")
        except ImportError as e:
            print(f"Failed to import payment signals: {e}")
            pass 