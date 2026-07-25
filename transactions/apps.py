from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    name = 'transactions'

    def ready(self):
        # ✅ FIX: signals.py mavjud edi, lekin hech qayerda import qilinmagani
        # uchun @receiver(post_save, ...) handler umuman ishga tushmasdi —
        # tranzaksiya yaratilganda DailyTransactionStat avtomatik yangilanmayotgan edi.
        import transactions.signals  # noqa: F401
