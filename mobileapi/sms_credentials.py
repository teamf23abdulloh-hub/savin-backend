"""SMS kredensiallari — VAQTINCHALIK, oddiy fayl.

Nima uchun shu yerda
--------------------
Eskiz hisobi hali "test" rolida va tasdiqlangan shablon yo'q (tiket kutilmoqda).
Shu davrda loyiha hech qanday muhit sozlamasisiz, hamma joyda (lokal, Railway)
bir xil ishlashi kerak. Shuning uchun qiymatlar `.env` emas, shu oddiy faylda.

DIQQAT — bu fayl `.env` dan farq qiladi
---------------------------------------
`.env` git'ga tushmaydi, bu fayl esa TUSHADI. Ya'ni bu yerdagi parol repoga
kirish huquqi bo'lgan hammaga ko'rinadi. Tiket hal bo'lgach:

    1) qiymatlarni `.env` ga (yoki Railway -> Variables ga) ko'chiring;
    2) shu fayldagi qatorlarni bo'shatib qo'ying ("" qilib);
    3) Eskiz kabinetidan yashirin kalitni YANGILANG.

Ustuvorlik: **muhit o'zgaruvchisi > shu fayl**. Shuning uchun `.env` ga
ko'chirganingizda bu yerdagi qiymatlar o'z-o'zidan e'tibordan qoladi — kodni
o'zgartirish shart emas.
"""

# --- Eskiz.uz (my.eskiz.uz -> SMS -> Sozlamalar -> SMS shlyuz) --------------
ESKIZ_EMAIL = "azizbeknosirov774@gmail.com"
ESKIZ_PASSWORD = "elNzcSlcmLeHKPGMCtaThLoZwfkL9gogHK8iGmH9"

# Jo'natuvchi. O'z nomingiz (nick) tasdiqlangach shu yerga yoziladi.
ESKIZ_SENDER = "4546"

# OTP matni. Eskiz FAQAT moderatsiyadan o'tgan shablonni yuboradi va matn
# tasdiqlangan variantga AYNAN mos kelishi kerak ({code} — kod o'rni).
SMS_OTP_TEMPLATE = "Savin: tasdiqlash kodingiz {code}. Hech kimga aytmang."

# Bo'sh = haqiqiy rejim: har bir raqamga SMS yuborishga URINIB ko'riladi.
# Eskiz shablonni tasdiqlagan zahoti SMS o'zi ketaveradi — bu yerda hech
# narsani o'zgartirish kerak emas.
SMS_DEV_MODE = ""

# --- VAQTINCHALIK ZAXIRA YO'L (1): haqiqiy SMS kelsin -----------------------
# Eskiz o'z matnimizni rad etsa, uning STANDART test matnini yuboradi
# ("Bu Eskiz dan test"). Foydalanuvchi kodni emas, shu matnni oladi — lekin
# SMS jismonan keladi va kanal ishlayotgani ko'rinadi.
#
# Bu barcha SMS turlariga tegishli: ilovaga kirish kodi, biznes arizasi
# tasdiqlangani, kassir qo'shilgani.
#
# Eskiz shabloni tasdiqlangach shu qatorni "" qilib qo'ying — o'shanda
# foydalanuvchi haqiqiy matnni oladi.
ESKIZ_TEST_TEXT_FALLBACK = "True"

# --- VAQTINCHALIK ZAXIRA YO'L (2): oqim uzilmasin ---------------------------
# Eskiz SMSni rad etsa (hozirgi holat: "test" roli, shablon tasdiqlanmagan),
# tasdiqlash kodi API javobida qaytariladi va ilova uni o'zi to'ldiradi.
# Natija: ro'yxatdan o'tish BARCHA raqamlar uchun xatosiz ishlaydi.
#
# XAVF: kod javobda ochiq kelgani uchun istalgan odam istalgan telefon
# raqami nomidan tizimga kira oladi. Bu — faqat tiket kutilayotgan davr uchun.
# Eskiz shablonni tasdiqlagach shu qatorni "" qilib qo'ying.
SMS_ALLOW_OTP_IN_RESPONSE = "True"
