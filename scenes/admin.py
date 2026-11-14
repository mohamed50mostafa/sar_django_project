from django.contrib import admin
from .models import Scene
@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ('file_id', 'platform', 'start_time', 'processing_level')
    search_fields = ('file_id', 'scene_name')
