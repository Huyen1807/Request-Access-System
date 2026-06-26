FROM python:3.12-slim

WORKDIR /app

# Copy toàn bộ project trước (bao gồm folder reqsys)
COPY . .

# Cài pip (requirements.txt đã có trong /app sau COPY . .)
RUN pip install --no-cache-dir -r requirements.txt

# Collect static files
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Cấp quyền execute
RUN chmod +x build.sh

# Run
CMD ["/bin/sh", "-c", "./build.sh && gunicorn reqsys.wsgi:application --bind 0.0.0.0:8000 --workers 2"]