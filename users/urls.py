from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from users.views import (
    AdminMembershipUpdateView,
    AdminUserBlockView,
    AdminUserViewSet,
    ChangePasswordView,
    LoginView,
    MeView,
    RegisterView,
    SuperAdminAdminAccountViewSet,
)

router = DefaultRouter()
router.register("admin/users", AdminUserViewSet, basename="admin-users")
router.register("superadmin/admins", SuperAdminAdminAccountViewSet, basename="superadmin-admins")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("me/", MeView.as_view(), name="me"),

    path("admin/users/<uuid:pk>/block/", AdminUserBlockView.as_view(), name="admin-user-block"),
    path("admin/users/<uuid:pk>/membership/", AdminMembershipUpdateView.as_view(), name="admin-user-membership"),
] + router.urls
