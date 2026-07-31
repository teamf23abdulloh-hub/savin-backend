"""Kategoriyalar bo'yicha standart xizmat turlari.

Biznes tasdiqlanganda uning kategoriyasiga mos xizmatlar avtomatik
yaratiladi — aks holda kassir QR skanerlagandan keyin 4-qadamda
"xizmat turi" tanlay olmay, tranzaksiyani yakunlay olmaydi.

Bu yozuvlar oddiy `Service` qatorlari — biznes egasi ularni o'z panelida
tahrirlashi, o'chirishi yoki yangisini qo'shishi mumkin.
Narxlar taxminiy boshlang'ich qiymat (so'mda) — egasi o'zi to'g'irlaydi.
"""

# Kalitlar kichik harfda solishtiriladi (kategoriya nomlari har xil yozilgan)
DEFAULT_SERVICES = {
    "barber": [
        ("Soch olish", 50000),
        ("Soqol olish", 30000),
        ("Soch + soqol", 70000),
        ("Bolalar sochi", 35000),
        ("Soch bo'yash", 90000),
    ],
    "sartaroshxona": [
        ("Soch olish", 50000),
        ("Soqol olish", 30000),
        ("Soch + soqol", 70000),
        ("Bolalar sochi", 35000),
    ],
    "salon": [
        ("Soch turmagi", 80000),
        ("Manikyur", 60000),
        ("Pedikyur", 80000),
        ("Kosmetologiya", 150000),
        ("Kipriklar", 120000),
        ("Qosh dizayni", 50000),
    ],
    "go'zallik va salomatlik": [
        ("Kosmetologiya", 150000),
        ("Massaj", 120000),
        ("Manikyur", 60000),
        ("Soch parvarishi", 90000),
    ],
    "restoran": [
        ("Asosiy taom", 45000),
        ("Birinchi taom", 25000),
        ("Salat", 20000),
        ("Ichimlik", 12000),
        ("Shirinlik", 22000),
        ("Biznes-lanch", 40000),
    ],
    "restoran va kafe": [
        ("Asosiy taom", 45000),
        ("Salat", 20000),
        ("Ichimlik", 12000),
        ("Shirinlik", 22000),
    ],
    "kafe": [
        ("Kofe", 20000),
        ("Choy", 12000),
        ("Fastfud", 30000),
        ("Shirinlik", 22000),
        ("Salat", 20000),
    ],
    "fitness": [
        ("Bir martalik tashrif", 30000),
        ("Oylik abonement", 300000),
        ("Shaxsiy mashg'ulot", 100000),
        ("Guruh mashg'uloti", 50000),
    ],
    "sport va fitnes": [
        ("Bir martalik tashrif", 30000),
        ("Oylik abonement", 300000),
        ("Shaxsiy mashg'ulot", 100000),
    ],
    "supermarket": [
        ("Oziq-ovqat xaridi", 100000),
        ("Maishiy tovarlar", 80000),
        ("Ichimliklar", 30000),
    ],
    "tibbiyot": [
        ("Shifokor qabuli", 100000),
        ("Tahlil topshirish", 80000),
        ("UZI tekshiruvi", 120000),
        ("Stomatolog qabuli", 150000),
    ],
    "kiyim": [
        ("Ustki kiyim", 300000),
        ("Ko'ylak", 150000),
        ("Shim", 180000),
        ("Poyabzal", 250000),
        ("Aksessuar", 60000),
    ],
    "ta'lim": [
        ("Bir oylik kurs", 400000),
        ("Individual dars", 100000),
        ("Sinov darsi", 0),
    ],
    "taxi": [
        ("Shahar ichida", 25000),
        ("Shahardan tashqari", 80000),
    ],
    "avto": [
        ("Moy almashtirish", 150000),
        ("Yuvish", 40000),
        ("Diagnostika", 100000),
        ("Shina almashtirish", 60000),
    ],
}

# Kategoriya topilmasa ishlatiladigan umumiy ro'yxat
FALLBACK_SERVICES = [
    ("Asosiy xizmat", 50000),
    ("Qo'shimcha xizmat", 30000),
]


def services_for_category(category_name):
    """Kategoriya nomiga mos (nom, narx) ro'yxatini qaytaradi."""
    key = (category_name or "").strip().lower()
    if key in DEFAULT_SERVICES:
        return DEFAULT_SERVICES[key]
    # Qisman moslik: "Restoran va kafe" -> "restoran"
    for known, items in DEFAULT_SERVICES.items():
        if known in key or key in known:
            return items
    return FALLBACK_SERVICES


def create_default_services(business):
    """Biznes uchun standart xizmatlarni yaratadi (bor bo'lsa tegmaydi)."""
    from businesses.models import Service

    if Service.objects.filter(business=business).exists():
        return 0

    category = business.category.name if business.category_id else ""
    items = services_for_category(category)
    Service.objects.bulk_create(
        [
            Service(business=business, name=name, price=price, is_active=True)
            for name, price in items
        ]
    )
    return len(items)
