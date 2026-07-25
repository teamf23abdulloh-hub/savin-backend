"""Admin operatorlari uchun autentifikatsiya backendi.

`AdminUser` endi AUTH_USER_MODEL emas, shuning uchun standart `ModelBackend` uni
topa olmaydi. `authenticate(request, username=..., password=...)` chaqirilganda
avval `ModelBackend` `users.User`ni (email bo'yicha) qidiradi, topmasa shu
backend `AdminUser`ni login (username) bo'yicha qidiradi.
"""

from django.contrib.auth.backends import BaseBackend

from .models import AdminUser


class AdminUserBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            user = AdminUser.objects.get(username=username)
        except AdminUser.DoesNotExist:
            # Mavjud bo'lmagan login uchun ham parolni hisoblaymiz — javob
            # vaqti bo'yicha loginlarni topib bo'lmasligi uchun.
            AdminUser().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        return getattr(user, "is_active", True)

    def get_user(self, user_id):
        try:
            return AdminUser.objects.get(pk=user_id)
        except AdminUser.DoesNotExist:
            return None
