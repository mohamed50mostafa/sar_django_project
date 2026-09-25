# SAR Django API (بدون Celery)

مشروع أولي بسيط مبني على Django وDjango REST Framework للبحث في مشاهد Sentinel-1 عبر NASA/ASF `asf_search` باستخدام WKT Polygon. لا يحتوي المشروع على Celery أو Redis أو أي عامل مهام خلفي؛ البحث يتم بشكل متزامن عبر طلب HTTP، ويمكن إضافة طبقات Prithvi-EO وSAM-Geo وInSAR لاحقًا كخدمات مستقلة.

## التشغيل

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py test
python manage.py runserver
```

ضع بيانات حساب NASA Earthdata في `.env` عند الحاجة:

```env
ASF_USERNAME=your_username
ASF_PASSWORD=your_password
```

## نقاط API

| الطريقة | المسار | الوظيفة |
|---|---|---|
| GET | `/health/` | فحص الخدمة والتأكد أن Celery غير مستخدم |
| POST | `/api/search/` | البحث في ASF وحفظ النتائج في SQLite |
| GET | `/api/scenes/` | عرض المشاهد المحفوظة |
| GET | `/api/scenes/{id}/` | عرض مشهد واحد |
| GET | `/admin/` | لوحة إدارة Django |

مثال طلب البحث:

```bash
curl -X POST http://127.0.0.1:8000/api/search/ \\
  -H 'Content-Type: application/json' \\
  -d '{"wkt":"POLYGON ((30 31, 30.1 31, 30.1 31.1, 30 31.1, 30 31))", "start_date":"2026-01-01", "end_date":"2026-09-18"}'
```

## ملاحظات مهمة

- نتائج ASF تُحفظ في قاعدة بيانات SQLite، وحقلا `geometry` و`source_metadata` يحفظان البيانات الجغرافية والبيانات الأصلية.
- حقل `local_file` مجهز للملفات التي ستُنزّل لاحقًا، لكن التنزيل التلقائي غير مفعّل في هذه النسخة لتجنب عمليات طويلة داخل طلب HTTP.
- النماذج الثقيلة مثل Prithvi-EO وSAM-Geo وPyGMTSAR وClimaX ليست مضمّنة في هذه النسخة الأولية؛ يمكن ربطها لاحقًا عبر endpoints أو خدمات تحليل منفصلة.
- يفضل استخدام PostgreSQL وObject Storage عند الانتقال إلى الإنتاج.
