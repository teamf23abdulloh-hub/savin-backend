from django.urls import path
from rest_framework.routers import DefaultRouter

from businesses.views import (
    AdminApplicationReviewView,
    AdminApplicationSetLocationView,
    AdminApplicationViewSet,
    AdminBridgeApplicationReviewView,
    AdminBusinessStatsView,
    AdminBusinessStopPartnershipView,
    AdminBusinessViewSet,
    ApplicationDetailView,
    ApplicationWizardStep1View,
    ApplicationWizardStepUpdateView,
    CashierLoginCheckView,
    CashierServiceListView,
    CategoryViewSet,
    MyApplicationsView,
    MyBusinessDashboardView,
    MyBusinessView,
    MyCashierDetailView,
    MyCashierListCreateView,
    MyServiceDetailView,
    MyServiceListCreateView,
    PanelLoginCheckView,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="categories")
router.register("admin/applications", AdminApplicationViewSet, basename="admin-applications")
router.register("admin/businesses", AdminBusinessViewSet, basename="admin-businesses")

urlpatterns = [
    # ---- Ariza qoldirish (wizard) ----
    path("applications/", MyApplicationsView.as_view(), name="my-applications"),
    path("applications/check-login/", PanelLoginCheckView.as_view(), name="application-check-login"),
    path("applications/step1/", ApplicationWizardStep1View.as_view(), name="application-step1"),
    # Admin panel backendidan keladigan tasdiqlash/rad etish natijasi (bridge)
    path("public/admin-bridge/applications/review/", AdminBridgeApplicationReviewView.as_view(), name="admin-bridge-application-review"),
    path("applications/<uuid:pk>/step/<int:step>/", ApplicationWizardStepUpdateView.as_view(), name="application-step"),
    path("applications/<uuid:pk>/", ApplicationDetailView.as_view(), name="application-detail"),

    # ---- Admin: ariza va biznes boshqaruvi ----
    path("admin/applications/<uuid:pk>/review/", AdminApplicationReviewView.as_view(), name="admin-application-review"),
    path("admin/applications/<uuid:pk>/set-location/", AdminApplicationSetLocationView.as_view(), name="admin-application-set-location"),
    path("admin/businesses/<uuid:pk>/stop-partnership/", AdminBusinessStopPartnershipView.as_view(), name="admin-business-stop"),
    path("admin/businesses/<uuid:pk>/stats/", AdminBusinessStatsView.as_view(), name="admin-business-stats"),

    # ---- Biznes egasi ----
    path("my-business/", MyBusinessView.as_view(), name="my-business"),
    path("my-business/dashboard/", MyBusinessDashboardView.as_view(), name="my-business-dashboard"),
    path("my-business/cashiers/check-login/", CashierLoginCheckView.as_view(), name="my-cashier-check-login"),
    path("my-business/cashiers/", MyCashierListCreateView.as_view(), name="my-cashiers"),
    path("my-business/cashiers/<uuid:pk>/", MyCashierDetailView.as_view(), name="my-cashier-detail"),

    # ---- Xizmatlar katalogi ----
    path("my-business/services/", MyServiceListCreateView.as_view(), name="my-services"),
    path("my-business/services/<uuid:pk>/", MyServiceDetailView.as_view(), name="my-service-detail"),
    path("cashier/services/", CashierServiceListView.as_view(), name="cashier-services"),
] + router.urls
