"""
Example configuration for the payment app Learning MFE URL.

This file shows how to configure the Learning MFE URL in different environments.
Copy the relevant settings to your Django settings files.
"""

# =============================================================================
# DEVELOPMENT ENVIRONMENT
# =============================================================================

# For local development, you can use:
LEARNING_MICROFRONTEND_URL = 'http://localhost:2000'

# Or if you're using MFE_CONFIG:
MFE_CONFIG = {
    'LEARNING_BASE_URL': 'http://localhost:2000',
    # ... other MFE config ...
}

# =============================================================================
# STAGING ENVIRONMENT
# =============================================================================

# For staging environment:
LEARNING_MICROFRONTEND_URL = 'https://learning-staging.yourdomain.com'

# Or with MFE_CONFIG:
MFE_CONFIG = {
    'LEARNING_BASE_URL': 'https://learning-staging.yourdomain.com',
    # ... other MFE config ...
}

# =============================================================================
# PRODUCTION ENVIRONMENT
# =============================================================================

# For production environment:
LEARNING_MICROFRONTEND_URL = 'https://learning.yourdomain.com'

# Or with MFE_CONFIG:
MFE_CONFIG = {
    'LEARNING_BASE_URL': 'https://learning.yourdomain.com',
    # ... other MFE config ...
}

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

# You can also set these via environment variables:
# export LEARNING_MICROFRONTEND_URL="https://learning.yourdomain.com"

# =============================================================================
# TUTOR CONFIGURATION
# =============================================================================

# If you're using Tutor, you can configure this in your tutor config:
# 
# # config.yml
# MFE_CONFIG:
#   LEARNING_BASE_URL: "{{ "https" if ENABLE_HTTPS else "http" }}://{{ MFE_HOST }}/learning"
#
# # Or in the MFE-specific settings:
# {% if get_mfe("learning") %}
# LEARNING_MICROFRONTEND_URL = "{{ "https" if ENABLE_HTTPS else "http" }}://{{ MFE_HOST }}/learning"
# MFE_CONFIG["LEARNING_BASE_URL"] = "{{ "https" if ENABLE_HTTPS else "http" }}://{{ MFE_HOST }}/learning"
# {% endif %}

# =============================================================================
# COMPLETE EXAMPLE
# =============================================================================

# Here's a complete example of how your settings might look:

"""
# In your Django settings file (e.g., lms/envs/common.py)

# Learning MFE Configuration
LEARNING_MICROFRONTEND_URL = 'http://localhost:2000'  # Development

# MFE Configuration (alternative approach)
MFE_CONFIG = {
    'BASE_URL': 'http://localhost:2000',
    'LEARNING_BASE_URL': 'http://localhost:2000',
    'LMS_BASE_URL': 'http://localhost:8000',
    'STUDIO_BASE_URL': 'http://localhost:8001',
    # ... other MFE settings ...
}

# Payment-specific settings (optional)
PAYMENT_SETTINGS = {
    'LEARNING_MFE_URL': LEARNING_MICROFRONTEND_URL,
    'SUCCESS_REDIRECT_PATH': '/learning/payment/success',
    'CANCEL_REDIRECT_PATH': '/learning/payment/cancel',
}
""" 