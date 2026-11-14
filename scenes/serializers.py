from rest_framework import serializers
from .models import Scene

class SceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scene
        fields = '__all__'


class GeoTIFFBuildSerializer(serializers.Serializer):
    vv_file = serializers.FileField()
    vh_file = serializers.FileField(required=False, allow_null=True)
    max_bytes = serializers.IntegerField(required=False, min_value=1024)


class GeoAIAnalyzeSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=8000)
    requested_model = serializers.ChoiceField(
        choices=['auto', 'gemini_only', 'prithvi', 'sam_hq'], default='auto',
    )
    point = serializers.ListField(child=serializers.IntegerField(), required=False, min_length=2, max_length=2)
    box = serializers.ListField(child=serializers.IntegerField(), required=False, min_length=4, max_length=4)
