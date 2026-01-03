# main/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import JobPostViewSet, AgentAPI

router = DefaultRouter()
router.register(r'jobs', JobPostViewSet, basename='jobs')

urlpatterns = [
    path('', include(router.urls)),
    path('agent/', AgentAPI.as_view(), name='agent-api'),
]
