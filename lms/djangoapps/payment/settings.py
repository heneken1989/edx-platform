"""
VNPay Payment Settings
"""

import os
from pathlib import Path
from django.conf import settings

# Load environment variables from .env file if it exists
env_file = Path(__file__).parent.parent.parent.parent / '.env.vnpay'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# VNPay Configuration 
VNPAY_CONFIG = {
    # Sandbox URLs (for testing)
    'SANDBOX_URL': 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html',
    
    # Production URLs (for live payments)
    'PRODUCTION_URL': 'https://pay.vnpay.vn/vpcpay.html',
    
    # VNPay Credentials - Replace with your actual credentials
    'TMN_CODE': os.environ.get('VNPAY_TMN_CODE', 'DEMO'),
    'HASH_SECRET': os.environ.get('VNPAY_HASH_SECRET', 'DEMO_SECRET'),
    
    # Environment setting
    'USE_SANDBOX': os.environ.get('VNPAY_USE_SANDBOX', 'True').lower() == 'true',
}

# Get credentials
def get_vnpay_credentials():
    """Get VNPay credentials"""
    return {
        'tmn_code': VNPAY_CONFIG['TMN_CODE'],
        'hash_secret': VNPAY_CONFIG['HASH_SECRET'],
    }

# Learning MFE Configuration
def get_learning_base_url():
    """
    Get the Learning MFE base URL (hardcoded for now)
    """
    return "http://apps.local.openedx.io:2000"

# Get the appropriate URL based on environment
def get_vnpay_url():
    """Get VNPay URL based on environment setting"""
    if VNPAY_CONFIG['USE_SANDBOX']:
        return VNPAY_CONFIG['SANDBOX_URL']
    return VNPAY_CONFIG['PRODUCTION_URL'] 