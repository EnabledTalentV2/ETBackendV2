from rest_framework.routers import DefaultRouter
from .views import OrganizationsViewSet

router = DefaultRouter()
router.register(r'organizations', OrganizationsViewSet, basename="organizations")

urlpatterns = router.urls
