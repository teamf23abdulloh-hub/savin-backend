"""Admin panel view'lari uchun asosiy sinflar.

Admin paneli alohida backend bo'lganda uning DRF sozlamalari ham alohida edi:
har bir view standart holda `IsAuthenticated` + `StandardPagination` olardi.
Birlashtirilgandan keyin esa standart sozlamalar butun platformaga umumiy —
ya'ni mijozning JWT tokeni ham `IsAuthenticated`dan o'tib ketardi va sahifalash
ham boshqa (PAGE_SIZE=20) bo'lardi.

Shuning uchun `core/views.py` va `accounts/views.py` `rest_framework` o'rniga
shu moduldan `APIView` / `generics` import qiladi — natijada o'sha fayllardagi
barcha view'lar avtomatik ravishda admin-panelga xos sozlamani oladi:

    permission_classes = [IsAdminOperator]   # faqat AdminUser
    pagination_class   = StandardPagination  # page_size=10, `page_size` param
    filter_backends    = []                  # global filtrlar aralashmasin

View'ning o'zida bu atributlar aniq yozilgan bo'lsa (masalan public
endpointlardagi `permission_classes = [AllowAny]`) — o'sha ustun turadi.
"""

from rest_framework import generics as _generics
from rest_framework.views import APIView as _APIView

from accounts.permissions import IsAdminOperator

from .pagination import StandardPagination


class _AdminScoped:
    permission_classes = [IsAdminOperator]
    pagination_class = StandardPagination
    filter_backends = []


class APIView(_AdminScoped, _APIView):
    pass


class generics:
    """`rest_framework.generics` ning admin-panelga moslangan varianti."""

    class GenericAPIView(_AdminScoped, _generics.GenericAPIView):
        pass

    class ListAPIView(_AdminScoped, _generics.ListAPIView):
        pass

    class CreateAPIView(_AdminScoped, _generics.CreateAPIView):
        pass

    class ListCreateAPIView(_AdminScoped, _generics.ListCreateAPIView):
        pass

    class RetrieveAPIView(_AdminScoped, _generics.RetrieveAPIView):
        pass

    class UpdateAPIView(_AdminScoped, _generics.UpdateAPIView):
        pass

    class DestroyAPIView(_AdminScoped, _generics.DestroyAPIView):
        pass

    class RetrieveUpdateAPIView(_AdminScoped, _generics.RetrieveUpdateAPIView):
        pass

    class RetrieveDestroyAPIView(_AdminScoped, _generics.RetrieveDestroyAPIView):
        pass

    class RetrieveUpdateDestroyAPIView(_AdminScoped, _generics.RetrieveUpdateDestroyAPIView):
        pass
