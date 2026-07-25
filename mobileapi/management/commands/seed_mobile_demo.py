from django.core.management.base import BaseCommand
from django.utils.text import slugify

from businesses.models import Application, Business, BusinessType, Region
from users.models import User

# QO'QON bo'ylab demo bizneslar — mobil ilova xaritasi/katalogi uchun.
# Qo'qon markazi ~ 40.528, 70.942. (nom, kategoriya, chegirma%, mahalla, lat, lng)
DEMO = [
    ("Fresh Cut Barber", "Barber", 35, "Qo'qon markaz", 40.5290, 70.9420),
    ("Korzinka Qo'qon", "Supermarket", 10, "Istiqlol", 40.5312, 70.9451),
    ("Milano Restoran", "Restoran", 15, "Qo'qon markaz", 40.5266, 70.9438),
    ("Glow Beauty Salon", "Salon", 30, "Do'stlik", 40.5341, 70.9392),
    ("Power Gym", "Fitness", 20, "Furqat", 40.5231, 70.9481),
    ("Shifo Klinika", "Tibbiyot", 20, "Turon", 40.5352, 70.9502),
    ("Zara Style", "Kiyim", 18, "Markaz", 40.5281, 70.9411),
    ("FitZone", "Fitness", 25, "Amir Temur", 40.5252, 70.9522),
    ("Evos Qo'qon", "Restoran", 15, "Istiqlol", 40.5301, 70.9432),
    ("Choco Cafe", "Kafe", 10, "Markaz", 40.5276, 70.9456),
    ("MediPlus", "Tibbiyot", 12, "Furqat", 40.5221, 70.9401),
    ("Makro Qo'qon", "Supermarket", 8, "Turon", 40.5361, 70.9471),
    ("Denim House", "Kiyim", 15, "Do'stlik", 40.5331, 70.9521),
    ("Beauty Lab", "Salon", 30, "Markaz", 40.5286, 70.9445),
]

CATEGORIES = ["Restoran", "Kafe", "Barber", "Salon", "Fitness", "Supermarket", "Tibbiyot", "Kiyim"]


class Command(BaseCommand):
    help = "Mobil ilova uchun demo kategoriya va bizneslarni yaratadi."

    def handle(self, *args, **options):
        from businesses.models import Category

        # 1) Kategoriyalar (slug to'qnashuvidan himoyalangan — bazada boshqa
        #    nomli kategoriyalar bo'lishi mumkin)
        def _unique_slug(base):
            slug = slugify(base) or "cat"
            candidate = slug
            n = 1
            while Category.objects.filter(slug=candidate).exists():
                candidate = f"{slug}-{n}"
                n += 1
            return candidate

        cat_map = {}
        for name in CATEGORIES:
            cat = Category.objects.filter(name=name).first()
            if cat is None:
                cat = Category.objects.create(
                    name=name, slug=_unique_slug(name), is_active=True
                )
            cat_map[name] = cat
        self.stdout.write(self.style.SUCCESS(f"Kategoriyalar: {len(cat_map)} ta"))

        # 2) Demo biznes egasi
        owner, created = User.objects.get_or_create(
            username="demo_owner",
            defaults={
                "email": "demo_owner@savin.local",
                "role": User.Role.BUSINESS_OWNER,
                "phone_number": "+998900000000",
            },
        )
        if created:
            owner.set_password("demo12345")
            owner.save()

        # 3) Eski demo bizneslarni (va arizalarni) tozalaymiz — Qo'qon
        #    bizneslari bilan toza almashtirish uchun.
        old = Business.objects.filter(owner=owner)
        old_apps = Application.objects.filter(applicant=owner)
        removed = old.count()
        old.delete()
        old_apps.delete()
        self.stdout.write(self.style.WARNING(f"Eski demo bizneslar o'chirildi: {removed} ta"))

        # 4) Bizneslar (+ chegirma uchun Application) — Qo'qon
        made = 0
        for i, (name, cat_name, discount, district, lat, lng) in enumerate(DEMO):
            category = cat_map.get(cat_name)
            if category is None:
                category, _ = Category.objects.get_or_create(
                    name=cat_name, defaults={"slug": slugify(cat_name), "is_active": True}
                )

            if Business.objects.filter(name=name, owner=owner).exists():
                continue

            phone = f"+99890{1000000 + i:07d}"
            app = Application.objects.create(
                applicant=owner,
                business_name=name,
                category=category,
                business_type=BusinessType.YATT,
                responsible_full_name="Demo Owner",
                phone_number=phone,
                region=Region.FERGANA,
                city_district=district,
                full_address=f"{district}, Qo'qon",
                discount_percent=discount,
                status=Application.Status.APPROVED,
                latitude=lat,
                longitude=lng,
            )
            Business.objects.create(
                owner=owner,
                application=app,
                name=name,
                category=category,
                business_type=BusinessType.YATT,
                phone_number=phone,
                region=Region.FERGANA,
                city_district=district,
                full_address=f"{district}, Qo'qon",
                latitude=lat,
                longitude=lng,
                is_active=True,
            )
            made += 1

        self.stdout.write(self.style.SUCCESS(f"Bizneslar yaratildi: {made} ta"))
        self.stdout.write(self.style.SUCCESS("Demo seed tugadi."))
