from django.db import models

class Scene(models.Model):
    file_id = models.CharField(max_length=255, unique=True)
    scene_name = models.CharField(max_length=255, blank=True)
    platform = models.CharField(max_length=100, blank=True)
    sensor = models.CharField(max_length=100, blank=True)
    processing_level = models.CharField(max_length=100, blank=True)
    beam_mode = models.CharField(max_length=100, blank=True)
    polarization = models.CharField(max_length=100, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    stop_time = models.DateTimeField(null=True, blank=True)
    flight_direction = models.CharField(max_length=50, blank=True)
    orbit = models.IntegerField(null=True, blank=True)
    path_number = models.IntegerField(null=True, blank=True)
    frame_number = models.IntegerField(null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    download_url = models.URLField(max_length=1000, blank=True)
    geometry = models.JSONField(default=dict, blank=True)
    source_metadata = models.JSONField(default=dict, blank=True)
    local_file = models.FileField(upload_to='scenes/', blank=True, null=True)
    # Compact, "normal-photo-like" 3-band preview built from the raw SAR
    # polarizations (VV, VH, VV/VH ratio), capped at MAX_GEOTIFF_BYTES.
    geotiff_file = models.FileField(upload_to='scenes/geotiff/', blank=True, null=True)
    geotiff_band_count = models.PositiveSmallIntegerField(null=True, blank=True)
    geotiff_size_bytes = models.BigIntegerField(null=True, blank=True)
    # Response (route + report) from the GeoAI models API, called as a
    # separate service over HTTP -- see scenes/geoai_client.py.
    analysis_report = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_time', '-created_at']

    def __str__(self):
        return self.scene_name or self.file_id
