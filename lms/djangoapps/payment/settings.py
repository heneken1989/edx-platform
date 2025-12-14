"""
Payment Gateway Settings (VNPay & PayOS)
"""

import os
from pathlib import Path
from django.conf import settings

# Load environment variables from .env file if it exists
# Load from .env.payment (if exists, contains both), otherwise load from .env.vnpay and .env.payos separately
base_path = Path(__file__).parent.parent.parent.parent
env_payment_file = base_path / '.env.payment'
env_vnpay_file = base_path / '.env.vnpay'
env_payos_file = base_path / '.env.payos'

# If .env.payment exists, load it (contains both VNPay and PayOS)
if env_payment_file.exists():
    print(f"Loading env vars from: {env_payment_file}")
    with open(env_payment_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                try:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
                except ValueError:
                    continue
    print(f"Finished loading from: {env_payment_file}")
else:
    # Otherwise, load from separate files
    for env_file in [env_vnpay_file, env_payos_file]:
        if env_file.exists():
            print(f"Loading env vars from: {env_file}")
            with open(env_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        try:
                            key, value = line.strip().split('=', 1)
                            os.environ[key] = value
                        except ValueError:
                            continue
            print(f"Finished loading from: {env_file}")

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

# PayOS Configuration
PAYOS_CONFIG = {
    # Sandbox URLs (for testing) - PayOS uses same URL for sandbox and production
    'SANDBOX_API_URL': 'https://api-merchant.payos.vn',
    
    # Production URLs (for live payments)
    'PRODUCTION_API_URL': 'https://api-merchant.payos.vn',
    
    # PayOS Credentials - Replace with your actual credentials
    'CLIENT_ID': os.environ.get('PAYOS_CLIENT_ID', 'DEMO'),
    'API_KEY': os.environ.get('PAYOS_API_KEY', 'DEMO_KEY'),
    'CHECKSUM_KEY': os.environ.get('PAYOS_CHECKSUM_KEY', 'DEMO_CHECKSUM'),
    
    # Environment setting
    'USE_SANDBOX': os.environ.get('PAYOS_USE_SANDBOX', 'True').lower() == 'true',
}

# Get PayOS credentials
def get_payos_credentials():
    """Get PayOS credentials"""
    credentials = {
        'client_id': PAYOS_CONFIG['CLIENT_ID'],
        'api_key': PAYOS_CONFIG['API_KEY'],
        'checksum_key': PAYOS_CONFIG['CHECKSUM_KEY'],
    }
    # Debug: Log credentials status (without exposing full values)
    print(f"=== PayOS Credentials Debug ===")
    print(f"CLIENT_ID from env: {os.environ.get('PAYOS_CLIENT_ID', 'NOT SET')}")
    print(f"CLIENT_ID in config: {PAYOS_CONFIG['CLIENT_ID'][:10] if PAYOS_CONFIG['CLIENT_ID'] != 'DEMO' else 'DEMO'}...")
    print(f"API_KEY from env: {os.environ.get('PAYOS_API_KEY', 'NOT SET')[:10] if os.environ.get('PAYOS_API_KEY') else 'NOT SET'}...")
    print(f"API_KEY in config: {PAYOS_CONFIG['API_KEY'][:10] if PAYOS_CONFIG['API_KEY'] != 'DEMO_KEY' else 'DEMO_KEY'}...")
    print(f"USE_SANDBOX: {PAYOS_CONFIG['USE_SANDBOX']}")
    print(f"==============================")
    return credentials

# Get PayOS API URL based on environment
def get_payos_api_url():
    """Get PayOS API URL based on environment setting"""
    if PAYOS_CONFIG['USE_SANDBOX']:
        return PAYOS_CONFIG['SANDBOX_API_URL']
    return PAYOS_CONFIG['PRODUCTION_API_URL'] 