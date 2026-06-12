#!/usr/bin/env bash
# Script này được Render tự động chạy sau khi build xong Docker image

set -o errexit  # Dừng ngay nếu có lỗi

# Chạy database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Tự động tạo superuser nếu khai báo biến môi trường
echo "Checking and creating superuser if needed..."
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reqsys.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if username and password:
    if not User.objects.filter(username=username).exists():
        print(f'Creating superuser {username}...')
        User.objects.create_superuser(username=username, email=email, password=password)
        print('Superuser created successfully!')
    else:
        print('Superuser already exists.')
else:
    print('DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD not set. Skipping.')
"

echo "Build completed successfully!"

