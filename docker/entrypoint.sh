#!/bin/bash
set -e

# Set default values
SERVICE_VARIANT=${SERVICE_VARIANT:-lms}
SERVICE_PORT=${SERVICE_PORT:-8000}

# Export environment variables
export SERVICE_VARIANT
export SERVICE_PORT

# Run the command
exec "$@"
