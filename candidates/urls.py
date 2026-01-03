from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CandidateViewSet,
    NoteViewSet,
    PromptAPI,
    CareerCoachAPI,
)

router = DefaultRouter()
router.register(r'profiles', CandidateViewSet, basename='candidate-profiles')
router.register(r'notes', NoteViewSet, basename='candidate-notes')

urlpatterns = [
    # CRUD + Resume Parsing + Notes
    path('', include(router.urls)),

    # Prompt-based resume chat
    path('prompt/', PromptAPI.as_view(), name='candidate-prompt'),

    # Career coach chat
    path('career-coach/', CareerCoachAPI.as_view(), name='career-coach'),
]
