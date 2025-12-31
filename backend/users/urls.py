from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import UserViewSet, TokenLoginView, SignupApiView, MeView, ProfileApiView, PasswordApiView

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", TokenLoginView.as_view(), name="api-login"),
    path("auth/signup/", SignupApiView.as_view(), name="api-signup"),
    path("auth/me/", MeView.as_view(), name="api-me"),
    path("account/profile/", ProfileApiView.as_view(), name="api-profile"),
    path("account/password/", PasswordApiView.as_view(), name="api-password"),
]
