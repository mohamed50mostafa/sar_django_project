from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import SceneViewSet, search_scenes
router = DefaultRouter()
router.register('scenes', SceneViewSet, basename='scene')
urlpatterns = [
    path('search/', search_scenes),
    path('', include(router.urls))
]
