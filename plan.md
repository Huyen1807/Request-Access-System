Chuyển từ Group-based sang Role-based permission (requester/sub-admin/owner)
Context
Hiện tại hệ thống dùng 3 Django Group riêng biệt (requester, owner, sub-admin) để phân quyền — một user chỉ thuộc 1 group. Yêu cầu mới: mọi user đều là requester, và có thể đồng thời có thêm role sub-admin và/hoặc owner (không loại trừ nhau). Sub-admin còn được scope hẹp hơn: chỉ quản lý (CRUD) các Domain được gán cho mình, không phải tất cả Domain như hiện tại; Application cũng theo scope domain đó.

User đã xác nhận:

Department (PNL) CRUD: chỉ superuser (request.user.is_superuser) được tạo/sửa/xóa. Sub-admin (và mọi user khác) chỉ được xem danh sách PNL (read-only), không CRUD.
Domain mới tạo: không tự gán người tạo làm quản lý — domain "trống" cho đến khi có người gán.
Hành động "gán domain cho sub-admin khác": bất kỳ sub-admin nào cũng làm được (không cần đang là người quản lý domain đó).
Dữ liệu cũ (db.sqlite3 hiện tại): xóa hết, không cần data-migration phức tạp để backfill từ Group → field mới. Sẽ tạo lại DB sạch sau khi đổi schema.
Vì project dùng django.contrib.auth.User mặc định (không có custom user model — đổi AUTH_USER_MODEL giữa chừng là việc cực rủi ro, không cần thiết), cách thêm field is_subadmin/is_owner là tạo model UserProfile (OneToOne tới User) trong app accounts, tự động tạo qua signal post_save.

Thay đổi model
accounts/models.py — thêm:

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', primary_key=True)
    is_subadmin = models.BooleanField(default=False)
    is_owner = models.BooleanField(default=False)
Signal post_save trên User (đặt trong accounts/signals.py, kết nối trong accounts/apps.py.ready()) tự tạo UserProfile cho mọi user mới. Nếu user.is_superuser, tự set is_subadmin=True luôn — để superuser tạo qua build.sh/createsuperuser bootstrap được hệ thống (giải quyết vấn đề "chưa có ai để tạo sub-admin đầu tiên" sau khi xóa data cũ).

applications/models.py — Domain — thêm:

managers = models.ManyToManyField(User, related_name='managed_domains', blank=True, verbose_name="Sub-admin quản lý")
applications/models.py / access_requests/models.py — cập nhật limit_choices_to:

Application.owner, OwnerBatch.owner → {'profile__is_owner': True}
AccessRequest.reviewed_by → {'profile__is_subadmin': True}
AccessRequest.requester → bỏ limit_choices_to (mọi user đều hợp lệ)
Permissions (accounts/permissions.py)
IsSubAdmin: request.user.profile.is_subadmin
IsOwner: request.user.profile.is_owner
IsRequester: chỉ còn is_authenticated (mọi user đều là requester) — giữ class để không phải sửa access_requests/views.py
IsNotRequester: bỏ hẳn việc dùng class này cho change_password — vì giờ mọi user (kể cả chỉ có role requester) đều được tự đổi mật khẩu của mình. UserViewSet.get_permissions() cho action change_password chỉ cần IsAuthenticated (xóa override dùng IsNotRequester). Class IsNotRequester không còn nơi nào dùng → xóa khỏi accounts/permissions.py.
Thêm IsDomainManager (object-level): obj.managers.filter(pk=request.user.pk).exists() — dùng cho update/destroy Domain và Application (qua domain của Application)
Thêm IsSuperUser: request.user.is_superuser — dùng cho write methods của DepartmentViewSet
accounts/serializers.py
CustomTokenObtainPairSerializer: bỏ logic lấy groups, trả về data['roles'] = list luôn có 'requester', cộng thêm 'sub-admin'/'owner' nếu profile tương ứng True.
UserCreateSerializer: bỏ group_name ChoiceField. Thêm is_subadmin, is_owner (BooleanField, required=False, default False, write-only). create(): tạo user như cũ (profile tự tạo qua signal), set 2 cờ lên user.profile, save. Email thông báo role liệt kê role nào được gán.
UserSerializer: bỏ get_groups; thêm is_subadmin, is_owner (đọc từ obj.profile).
UserUpdateSerializer: bỏ group_name; thêm is_subadmin, is_owner (BooleanField required=False, độc lập, không loại trừ nhau). update(): nếu field có trong validated_data thì set lên profile và save.
accounts/views.py (UserViewSet)
get_queryset(): bỏ filter groups__name__in=[...] → trả tất cả user (select_related('profile')) để sub-admin thấy được toàn bộ user khi gán role/gán domain.
owners() action: filter profile__is_owner=True, is_active=True.
Thêm action subadmins (giống owners) filter profile__is_subadmin=True, is_active=True — cần để frontend chọn sub-admin khi gán domain.
get_permissions(): bỏ override riêng cho change_password (không cần IsNotRequester nữa) — action này chỉ cần IsAuthenticated, mọi user tự đổi mật khẩu của chính mình.
applications/ — Domain & Application scope
applications/serializers.py

DomainSerializer: thêm field đọc managers (id, email, first_name, last_name — tái dùng ApplicationOwnerSerializer-style nested serializer).
Thêm DomainAssignSubAdminSerializer (giống ApplicationAssignOwnerSerializer): validate subadmin_id → user phải có profile.is_subadmin=True.
ApplicationAssignOwnerSerializer.validate_owner_id: đổi check sang user.profile.is_owner.
ApplicationSerializer.validate(): thêm check khi tạo mới — domain được chọn phải nằm trong request.user.managed_domains (lấy qua self.context['request']), nếu không raise lỗi "Bạn không quản lý domain này."
applications/views.py

DepartmentViewSet: get_permissions() đổi — SAFE methods (GET) → IsAuthenticated (mọi user, gồm sub-admin, đều xem được danh sách PNL); write methods (POST/PUT/PATCH/DELETE) → IsAuthenticated, IsSuperUser.
DomainViewSet:
get_permissions(): SAFE methods → IsAuthenticated; create → IsAuthenticated, IsSubAdmin; update/partial_update/destroy → IsAuthenticated, IsSubAdmin, IsDomainManager (object-level check tự áp dụng qua get_object() → check_object_permissions).
Thêm action assign-subadmin (POST, detail=True): bất kỳ sub-admin nào gọi được (permission chỉ cần IsSubAdmin, không cần IsDomainManager) — body {"subadmin_id": ...}, thêm vào domain.managers.
Thêm action remove-subadmin tương tự — bỏ khỏi domain.managers.
get_queryset(): giữ ?department_id=, thêm ?mine=true để filter managers=request.user (tiện cho UI "domain của tôi").
ApplicationViewSet:
get_permissions(): SAFE → IsAuthenticated; create → IsAuthenticated, IsSubAdmin (validate domain ở serializer); update/partial_update/destroy/assign_owner/remove_owner → IsAuthenticated, IsSubAdmin, IsDomainManager (object permission check trên application.domain — IsDomainManager.has_object_permission cần nhận obj là Application, lấy obj.domain để check thay vì check trực tiếp obj.managers; viết một biến thể IsApplicationDomainManager hoặc cho IsDomainManager.has_object_permission tự dò field managers qua getattr(obj, 'domain', obj).managers).
access_requests/ — chỉ 1 chỗ cần đổi
access_requests/views.py, hàm _notify_subadmin_reminder:

sub_admins = User.objects.filter(groups__name='sub-admin', is_active=True)
→

sub_admins = User.objects.filter(profile__is_subadmin=True, is_active=True)
Không cần đổi gì khác trong app này — toàn bộ permission_classes đều tham chiếu qua accounts.permissions, logic được cập nhật tập trung ở đó.

Migrations & reset dữ liệu
accounts: migration tạo UserProfile.
applications: migration thêm Domain.managers (M2M) + đổi limit_choices_to trên Application.owner (no-op DB, chỉ đổi metadata).
access_requests: migration đổi limit_choices_to trên requester, reviewed_by, OwnerBatch.owner (no-op DB).
Theo xác nhận của user: xóa reqsys/db.sqlite3 sau khi code xong, chạy lại python manage.py migrate để tạo DB sạch theo schema mới — sẽ xác nhận lại với user trước khi thực hiện xóa file (hành động phá hủy dữ liệu).
Sau khi có DB sạch: tạo superuser qua manage.py createsuperuser (hoặc qua build.sh/env vars) — nhờ signal, superuser này tự có is_subadmin=True để bắt đầu tạo các user/sub-admin khác qua API.
Verification
python manage.py makemigrations && python manage.py migrate chạy sạch, không lỗi.
python manage.py check.
Test thủ công qua python manage.py shell hoặc Swagger UI (/api/docs/swagger/):
Tạo superuser → login → thấy roles chứa sub-admin.
Sub-admin tạo user mới với is_owner=True → login user đó → roles chứa owner.
Sub-admin A tạo Domain → Sub-admin B (chưa được gán) thử PATCH domain đó → 403.
Sub-admin A gọi assign-subadmin gán B vào domain → B PATCH domain → thành công.
Tạo Application trong domain mà sub-admin hiện tại không quản lý → 400 từ serializer validation.
Gán owner cho Application bằng user không có is_owner=True → lỗi validate.
Existing test trong access_requests/tests.py (nếu có) vẫn pass — chạy python manage.py test.
Add Comment