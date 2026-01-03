from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from users.jwt_views import EmailTokenObtainPairView


urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),

    # Auth + Users
    path('api/auth/', include('users.urls')),  
    path('api/auth/password_reset/', include('django_rest_passwordreset.urls', namespace='password_reset')),

    # Organization
    path('api/organization/', include('organization.urls')),

    # Main (Job posts, ranking, agents, channels)
    path('api/channels/', include('main.urls')),

    # Candidates (resume parsing, notes, coach, context)
    path('api/candidates/', include('candidates.urls')),
    
    path("api/token/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

]
