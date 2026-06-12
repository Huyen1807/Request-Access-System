# Access Request System (Backend)

Phần backend hỗ trợ hệ thống quản lý và phê duyệt yêu cầu truy cập (Access Request System), được phát triển bằng Django và Django REST Framework.

## Công nghệ sử dụng
- **Backend framework**: Django 5.2+
- **REST framework**: Django REST Framework (DRF)
- **Authentication**: JWT (JSON Web Token) via `djangorestframework-simplejwt`
- **Database**: SQLite (mặc định cho môi trường dev)

## Tính năng đã triển khai
1. **Xác thực qua Email & Password**: Đăng nhập bằng email để nhận JWT token (`access` & `refresh`).
2. **Phân quyền người dùng (Groups)**:
   - `sub-admin`: Có quyền tạo tài khoản và gán vào nhóm `requester` hoặc `owner`.
   - `requester`: Người gửi yêu cầu truy cập.
   - `owner`: Người sở hữu tài nguyên cần phê duyệt truy cập.

## Hướng dẫn cài đặt & chạy dự án

### 1. Chuẩn bị môi trường
```bash
# Clone project
git clone https://github.com/Huyen1807/Request-Access-System.git
cd Request-Access-System

# Tạo và kích hoạt virtual environment
python -m venv .venv
source .venv/bin/activate  # Trên Linux/macOS
# Hoặc
.venv\Scripts\activate     # Trên Windows

# Cài đặt thư viện cần thiết
pip install django djangorestframework djangorestframework-simplejwt
```

### 2. Khởi chạy cơ sở dữ liệu và Server
```bash
cd reqsys

# Chạy migrations để khởi tạo database
python manage.py migrate

# Tạo tài khoản Admin tối cao (Superuser)
python manage.py createsuperuser

# Khởi chạy Local Server
python manage.py runserver
```

## Các API Endpoints chính

### 1. Đăng nhập (JWT)
- **Lấy Token:** `POST /api/auth/login/`
  - Body: `{"email": "...", "password": "..."}`
- **Làm mới Token:** `POST /api/auth/token/refresh/`
  - Body: `{"refresh": "..."}`

### 2. Quản lý Tài khoản (Dành cho Sub-admin)
- **Tạo User mới:** `POST /api/auth/create-user/`
  - Header: `Authorization: Bearer <access_token_cua_sub_admin>`
  - Body:
    ```json
    {
        "email": "test@gmail.com",
        "password": "mat_khau_an_toan",
        "first_name": "Nguyen",
        "last_name": "An",
        "group_name": "requester"  // Chỉ nhận "requester" hoặc "owner"
    }
    ```
