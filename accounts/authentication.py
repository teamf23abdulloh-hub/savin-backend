"""Admin paneli uchun token autentifikatsiyasi.

DRF'ning `TokenAuthentication`i faqat `model` atributini almashtirishni talab
qiladi — qolgan mantiq (header'ni o'qish, `Authorization: Token <key>` formati,
`is_active` tekshiruvi) o'zgarishsiz qoladi.
"""

from rest_framework.authentication import TokenAuthentication

from .models import AdminToken


class AdminTokenAuthentication(TokenAuthentication):
    model = AdminToken
