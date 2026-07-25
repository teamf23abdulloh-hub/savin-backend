from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("admins/", views.AdminListCreateView.as_view(), name="auth-admins-list-create"),
    path("admins/<int:pk>/", views.AdminDetailView.as_view(), name="auth-admins-detail"),
    path("change-password/", views.ChangePasswordView.as_view(), name="auth-change-password"),
    path(
        "notification-prefs/",
        views.NotificationPreferenceView.as_view(),
        name="auth-notification-prefs",
    ),
    path("settings/", views.AccountSettingsView.as_view(), name="auth-account-settings"),
]
