#!/usr/bin/env bash
# Script này được Render tự động chạy sau khi build xong Docker image

set -o errexit  # Dừng ngay nếu có lỗi

# Chạy database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

echo "Build completed successfully!"
