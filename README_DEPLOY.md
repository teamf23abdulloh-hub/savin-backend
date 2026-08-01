# Savin backend — Railway deploy va ma'lumot boshqaruvi

## 1. Eng muhimi: ma'lumot endi deployda o'chmaydi

Ilgari `startCommand` ichida `python manage.py run_seed` turardi. U `SEED`
env-o'zgaruvchisiga qarab bazani **flush** qilib qayta to'ldirardi. `SEED`
Railway'da bir marta qo'yilgach o'zgarmas bo'lib qolgani uchun **har bir
deployda barcha yangi ma'lumotlar o'chib ketardi**.

Hozir:

- `run_seed` `startCommand`dan **olib tashlandi** (`Procfile`, `railway.json`);
- `run_seed` buyrug'ining o'zi **zararsiz no-op**ga aylantirildi — Railway
  panelidagi eski startCommand hali uni chaqirsa ham, hech narsa o'chmaydi;
- `DATABASE_URL` qo'yilmagan bo'lsa, production deploy endi **darhol
  to'xtaydi** (ilgari jimgina vaqtinchalik SQLite'ga tushib, har deployda
  hamma narsani yo'qotardi).

Deploy paytida faqat quyidagilar bajariladi (hech biri ma'lumot o'chirmaydi):

```
migrate  ->  collectstatic  ->  sync_members --apply  ->  gunicorn
```

---

## 2. Postgres ulash (majburiy)

Ma'lumot saqlanishi uchun Postgres **shart**. Railway disklari vaqtinchalik.

1. Railway loyihasida: **New → Database → Add PostgreSQL**
2. Backend servis → **Variables** → yangi o'zgaruvchi:

   ```
   DATABASE_URL = ${{Postgres.DATABASE_URL}}
   ```

3. **Redeploy**.

Ulanmagan bo'lsa, deploy logida to'liq yo'l-yo'riq bilan xato chiqadi.

---

## 3. Ikkita konsol buyrug'i

Railway → backend servis → **Console** (yoki `railway run`) da ishlatiladi.
Boshqa hech qanday seed buyrug'i kerak emas.

### Soxta (demo) ma'lumot to'ldirish

```bash
python manage.py seed_fake --fresh
```

Avval bazani tozalab, so'ng realistik demo ma'lumot yaratadi: kategoriyalar,
bizneslar, egalar, kassirlar, mijozlar, xizmatlar, arizalar, tranzaksiyalar,
to'lovlar, bildirishnomalar va ~60 kunlik analitika.

| Kim | Login | Parol |
|---|---|---|
| Admin panel | `admin` | `admin12345` |
| Biznes egasi | `owner1@savin.uz` | `demo12345` |
| Kassir | `cashier1@savin.uz` | `demo12345` |

Mavjud ma'lumot ustiga **qo'shish** (tozalamasdan) kerak bo'lsa — `--fresh`siz:

```bash
python manage.py seed_fake
```

### Loyihani to'liq tozalash

```bash
python manage.py seed_demo
```

**Barcha** ma'lumotni o'chiradi va faqat bitta admin operator qoldiradi
(`admin` / `admin12345`). Jadval sxemasi va migratsiya tarixi saqlanadi.

Boshqa login/parol bilan:

```bash
python manage.py seed_demo --login boss --password 'Zor2024!' --email boss@savin.uz
```

> ⚠️ Ikkala buyruq ham bazani **o'chiradi**. Faqat qo'lda, ataylab ishlating.

---

## 4. Kerakli env-o'zgaruvchilar

| O'zgaruvchi | Majburiymi | Izoh |
|---|---|---|
| `DATABASE_URL` | **Ha** | Postgres. Bo'lmasa deploy to'xtaydi. |
| `DJANGO_SECRET_KEY` | **Ha** | Tasodifiy maxfiy kalit. |
| `DJANGO_DEBUG` | Yo'q | Standart `False`. Production'da qo'ymang. |
| `DJANGO_ALLOWED_HOSTS` | Yo'q | Standart `*`. Railway domenlari avtomatik qo'shiladi. |
| `CORS_ALLOWED_ORIGINS` | Ha (frontend uchun) | Vergul bilan: `https://admin.savin.uz,https://savin.uz` |
| `CSRF_TRUSTED_ORIGINS` | Ha (admin form uchun) | Masalan `https://savin-backend-production.up.railway.app` |
| `SECURE_SSL_REDIRECT` | Yo'q | Standart `False` — Railway healthcheck buzilmasligi uchun. |
| `SEED` | **Yo'q** | **Eskirgan va e'tiborga olinmaydi.** Variables'dan o'chiring. |
| `ALLOW_SQLITE_IN_PRODUCTION` | Yo'q | Faqat ataylab ma'lumot yo'qotish kerak bo'lsa. |

---

## 5. Media fayllar haqida ogohlantirish

Biznes logolari, avatarlar va QR rasmlar `MEDIA_ROOT` ichiga yoziladi va endi
production'da ham to'g'ri ko'rsatiladi (ilgari 404 qaytarardi).

Ammo **Railway diski vaqtinchalik** — yuklangan fayllar har redeploy'da
o'chadi. Doimiy saqlash uchun object storage (S3, Cloudflare R2) yoki Railway
Volume ulash kerak. Bazadagi ma'lumotga bu ta'sir qilmaydi.
