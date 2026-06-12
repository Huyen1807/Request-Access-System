FROM python:3.12-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Cài đặt dependencies trước (tận dụng Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code vào container
COPY . .

# Thu thập static files (CSS/JS của Django Admin)
RUN python manage.py collectstatic --noinput

# Expose port 8000 ra ngoài container
EXPOSE 8000

# Cấp quyền thực thi cho build.sh và chạy nó trước khi khởi động Gunicorn
RUN chmod +x build.sh

CMD ["/bin/sh", "-c", "./build.sh && gunicorn reqsys.wsgi:application --bind 0.0.0.0:8000 --workers 2"]

