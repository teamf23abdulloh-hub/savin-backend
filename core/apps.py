from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Mobil ilovada ro'yxatdan o'tgan mijoz admin panelning
        # "Foydalanuvchilar" ro'yxatida ko'rinishi uchun signallar
        from . import signals  # noqa: F401
