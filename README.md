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
| POST | `/api/scenes/{id}/geotiff/` | بناء معاينة GeoTIFF مضغوطة (3 أبواند) من بوابين VV/VH الخام |
| POST | `/api/scenes/{id}/analyze/` | إرسال المعاينة إلى مشروع GeoAI المنفصل (API آخر تمامًا) للتحليل |
| GET | `/admin/` | لوحة إدارة Django |

### بناء معاينة GeoTIFF بحجم لا يتجاوز 100 ميجا

مشاهد Sentinel-1 GRD تأتي عادة كبوابين (VV وVH) أحادية القناة، بينما الصورة العادية فيها 3 قنوات (RGB). لذلك `POST /api/scenes/{id}/geotiff/` يبني GeoTIFF بـ 3 أبواند دائمًا (VV، VH، ونسبة VV/VH كقناة ثالثة شبه-لونية) بعمق 8-بت، ويحسب تلقائيًا نسبة إنقاص الدقة (downsampling) اللازمة حتى لا يتجاوز الناتج `MAX_GEOTIFF_BYTES` (افتراضيًا 100MB). الحساب الرياضي والتحقق منه موجودان في `scenes/geotiff_builder.py` ومُختبَران في `scenes/tests/test_geotiff_builder.py`.

```bash
curl -X POST http://127.0.0.1:8000/api/scenes/1/geotiff/ \\
  -F "vv_file=@VV.tif" -F "vh_file=@VH.tif"
```

### الربط بمشروع GeoAI (نموذجين كـ APIs منفصلة)

هذا المشروع **لا يستورد** أي كود من مشروع GeoAI (نماذج Gemini/Prithvi/SAM-HQ)؛ الاثنان يتواصلان فقط عبر HTTP تمامًا كأي خدمتين مستقلتين، عبر `scenes/geoai_client.py`. اضبط `GEOAI_API_BASE_URL` في `.env` على رابط الـ Space بعد نشره على Hugging Face، ثم:

```bash
curl -X POST http://127.0.0.1:8000/api/scenes/1/analyze/ \\
  -H 'Content-Type: application/json' \\
  -d '{"prompt":"حدد مناطق الماء في هذا المشهد", "requested_model":"auto"}'
```

> ملاحظة: نماذج GGUF المحلية (llama_vision/moondream/qwen_vl) أُلغي دورها في مشروع GeoAI لأنها لم تعمل بشكل موثوق؛ الخيارات المتاحة الآن هي `auto`، `gemini_only`، `prithvi`، `sam_hq` فقط.

## النشر (Deployment)

المشروعان على خطط مجانية بدون أي بطاقة ائتمان:

- **مشروع النماذج (GeoAI)**: على **Hugging Face Spaces** (نوع Docker)، عبر `Dockerfile` و`README.md` بترويسة YAML في مجلده — مجاني تمامًا بدون بطاقة.
- **هذا المشروع (SAR)**: على **Render.com** (خطة Free Web Service، لا تتطلب بطاقة ائتمان). يحتوي الجذر على `Dockerfile` و`render.yaml` لنشر بضغطة واحدة (Blueprint):
  1. ادفع هذا المجلد كمستودع GitHub.
  2. من Render: New + → Blueprint → اختر المستودع.
  3. أدخل `ASF_USERNAME`، `ASF_PASSWORD`، و`GEOAI_API_BASE_URL` (رابط Space الخاص بمشروع GeoAI) كمتغيرات بيئة سرّية.
  4. ملاحظة: الخطة المجانية على Render "تنام" بعد ~15 دقيقة بدون طلبات وتستيقظ تلقائيًا عند أول طلب جديد (قد يستغرق ثوانٍ قليلة)، وقاعدة SQLite على القرص المؤقت تُعاد عند كل إعادة نشر — للإنتاج الحقيقي يُنصح بالترقية لاحقًا إلى قرص دائم أو PostgreSQL.

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
