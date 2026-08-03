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
| `ESKIZ_EMAIL` / `ESKIZ_PASSWORD` | Ha (SMS uchun) | Bo'lmasa SMS ketmaydi — pastdagi 5-bo'limga qarang. |
| `ESKIZ_SENDER` | Yo'q | Standart `4546`. |
| `SMS_OTP_TEMPLATE` | Yo'q | Eskiz'da tasdiqlangan matn. `{code}` — kod o'rni. |
| `SMS_DEV_MODE` | Yo'q | `True` — kredensiallar bor bo'lsa ham SMS yubormaslik. |
| `SMS_STATUS_TOKEN` | Yo'q | `/api/v1/mobile/sms-status/` tashxisini production'da ochish kaliti. |

Lokal ishlashda bularni terminalga yozish shart emas: `backend/.env` fayliga
qo'ying (namuna — `backend/.env.example`). Haqiqiy muhit o'zgaruvchisi har doim
`.env` dan ustun turadi, shuning uchun Railway'dagi qiymatlar buzilmaydi.

---

## 5. SMS (Eskiz.uz)

SMS uchta joyda ishlatiladi: mobil ilovaga kirish kodi (OTP), biznes arizasi
tasdiqlangani/rad etilgani, kassir qo'shilganda kirish ma'lumotlari.

**Rejimlar.** `ESKIZ_EMAIL` va `ESKIZ_PASSWORD` bo'lmasa — *test rejimi*: SMS
ketmaydi, kod API javobida `dev_otp` bo'lib qaytadi va ilovada avtomatik
to'ldiriladi. Ikkalasi qo'yilsa — SMS haqiqatda yuboriladi.

### ⚠️ Hozirgi vaqtinchalik holat (Eskiz tiketi kutilmoqda)

Eskiz hisobi hali **`test` rolida** va tasdiqlangan shablon yo'q — Eskiz o'z
matnimizni rad etadi (`"Number is forbidden"`, `"faqat test matnini yuborish
mumkin"`). Shu davr uchun ikkita vaqtinchalik yechim qo'yilgan:

1. **Kredensiallar `mobileapi/sms_credentials.py` faylida** — `.env` da emas.
   Sabab: hech qanday muhit sozlamasisiz hamma joyda ishlashi kerak.
   ⚠️ Bu fayl `.env` dan farqli o'laroq **git'ga tushadi**.
2. **`ESKIZ_TEST_TEXT_FALLBACK = "True"`** — Eskiz o'z matnimizni rad etsa,
   uning standart test matni (`"Bu Eskiz dan test"`) yuboriladi. Foydalanuvchi
   kodni emas, shu matnni oladi, lekin **SMS jismonan keladi**. Barcha SMS
   turlariga tegishli: kirish kodi, ariza tasdiqlangani, kassir qo'shilgani.
3. **`SMS_ALLOW_OTP_IN_RESPONSE = "True"`** — SMS ketmasa tasdiqlash kodi API
   javobida qaytadi, ilova uni o'zi to'ldiradi. Natijada ro'yxatdan o'tish
   **barcha raqamlar uchun xatosiz** ishlaydi.
   ⚠️ Kod javobda ochiq kelgani uchun **istalgan odam istalgan raqam nomidan
   kira oladi**.

> Eskiz test rolida raqamlarni ham cheklaydi: sinovda ba'zi raqamlar
> `"Number is forbidden"` bilan qaytdi. Bunday raqamga test matni ham
> bormaydi — bu Eskiz tomonidagi cheklov.

**Tiket hal bo'lgach (hammasini bajaring):**

```
1) sms_credentials.py -> SMS_ALLOW_OTP_IN_RESPONSE = ""   (zaxira yo'lni yopish)
2) sms_credentials.py -> ESKIZ_TEST_TEXT_FALLBACK  = ""   (haqiqiy matn ketsin)
3) ESKIZ_EMAIL / ESKIZ_PASSWORD -> .env yoki Railway Variables ga ko'chirish,
   sms_credentials.py dagilarini "" qilish
4) Eskiz kabinetidan yashirin kalitni YANGILASH (git tarixida qolgani uchun)
```

Muhit o'zgaruvchisi fayldan ustun, shuning uchun 2-qadamda kodni o'zgartirish
shart emas. `python manage.py sms_test` har bir qadamdan keyin holatni
ko'rsatadi.

**Tekshirish:**

```bash
python manage.py sms_test                  # sozlamalar + Eskiz bilan aloqa
python manage.py sms_test +998901234567    # sinov SMS ham yuboradi
```

Buyruq sababni aniq ajratadi: kredensiallar muhitga tushmaganmi, email/parol
noto'g'rimi, yoki matn moderatsiyadan o'tmaganmi.

**Matn moderatsiyasi.** Eskiz faqat tasdiqlangan shablonni yuboradi va matn
tasdiqlangan variantga **aynan** mos kelishi kerak. Moderatsiyada matn
o'zgarsa, kodni qayta joylashtirmasdan `SMS_OTP_TEMPLATE` orqali moslash
mumkin. Shablon tasdiqlanmagan bo'lsa Eskiz 400 qaytaradi, ro'yxatdan o'tish
so'rovi esa `503` va tushunarli xabar bilan tugaydi (ilgari "kod yuborildi"
deb ko'rsatilardi, foydalanuvchi esa kelmaydigan SMSni kutib qolardi) — aniq
sabab server logida, Eskiz javobi bilan birga yoziladi.

---

## 6. Media fayllar haqida ogohlantirish

Biznes logolari, avatarlar va QR rasmlar `MEDIA_ROOT` ichiga yoziladi va endi
production'da ham to'g'ri ko'rsatiladi (ilgari 404 qaytarardi).

Ammo **Railway diski vaqtinchalik** — yuklangan fayllar har redeploy'da
o'chadi. Doimiy saqlash uchun object storage (S3, Cloudflare R2) yoki Railway
Volume ulash kerak. Bazadagi ma'lumotga bu ta'sir qilmaydi.
