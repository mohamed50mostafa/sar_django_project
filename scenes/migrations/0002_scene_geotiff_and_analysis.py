from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scenes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(model_name='scene', name='geotiff_file',
                             field=models.FileField(blank=True, null=True, upload_to='scenes/geotiff/')),
        migrations.AddField(model_name='scene', name='geotiff_band_count',
                             field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='scene', name='geotiff_size_bytes',
                             field=models.BigIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='scene', name='analysis_report',
                             field=models.JSONField(blank=True, default=dict)),
    ]
