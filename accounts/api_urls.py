from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .api_views import LoginAPIView, ProfileAPIView, RegisterAPIView

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='api-register'),
    path('token/', LoginAPIView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', ProfileAPIView.as_view(), name='api-me'),
]
