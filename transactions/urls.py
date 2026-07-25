from rest_framework.routers import DefaultRouter

from transactions.views import TransactionViewSet, DailyStatViewSet

router = DefaultRouter()
router.register("transactions", TransactionViewSet, basename="transactions")
router.register("daily-stats", DailyStatViewSet, basename="daily-stats")

urlpatterns = router.urls
