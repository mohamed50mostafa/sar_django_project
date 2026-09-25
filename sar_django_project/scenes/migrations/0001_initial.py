from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name='Scene', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('file_id', models.CharField(max_length=255, unique=True)), ('scene_name', models.CharField(blank=True, max_length=255)),
        ('platform', models.CharField(blank=True, max_length=100)), ('sensor', models.CharField(blank=True, max_length=100)),
        ('processing_level', models.CharField(blank=True, max_length=100)), ('beam_mode', models.CharField(blank=True, max_length=100)),
        ('polarization', models.CharField(blank=True, max_length=100)), ('start_time', models.DateTimeField(blank=True, null=True)),
        ('stop_time', models.DateTimeField(blank=True, null=True)), ('flight_direction', models.CharField(blank=True, max_length=50)),
        ('orbit', models.IntegerField(blank=True, null=True)), ('path_number', models.IntegerField(blank=True, null=True)),
        ('frame_number', models.IntegerField(blank=True, null=True)), ('file_size_bytes', models.BigIntegerField(blank=True, null=True)),
        ('download_url', models.URLField(blank=True, max_length=1000)), ('geometry', models.JSONField(blank=True, default=dict)),
        ('source_metadata', models.JSONField(blank=True, default=dict)), ('local_file', models.FileField(blank=True, null=True, upload_to='scenes/')),
        ('created_at', models.DateTimeField(auto_now_add=True)),
    ], options={'ordering': ['-start_time', '-created_at']})]
