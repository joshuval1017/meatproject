#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Set Python path and environment variables
export PYTHONPATH=/opt/render/project/src
export DJANGO_SETTINGS_MODULE=meatmart.settings

# Debug: Print current directory and list files
echo "Current directory before cd:"
pwd
ls -la

# Move to the Django project directory where manage.py is located
cd Meatmart

# Debug: Print current directory and list files after cd
echo "Current directory after cd:"
pwd
ls -la

# Collect static files
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate
