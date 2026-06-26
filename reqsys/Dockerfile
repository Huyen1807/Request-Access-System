FROM python:3.12-slim

WORKDIR /app

# Copy toàn bộ project
COPY . .

# Cài pip
RUN pip install --no-cache-dir -r reqsys/requirements.txt

# Change to reqsys directory (nơi có manage.py)
WORKDIR /app/reqsys

# Collect static files
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Cấp quyền
RUN chmod +x build.sh

# Run từ reqsys directory
CMD ["/bin/sh", "-c", "./build.sh && python manage.py migrate && gunicorn reqsys.wsgi:application --bind 0.0.0.0:8000 --workers 2"]