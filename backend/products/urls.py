from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProductViewSet, CategoryViewSet, OfferViewSet

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="products")
router.register(r"categories", CategoryViewSet, basename="categories")
router.register(r"offers", OfferViewSet, basename="offers")

urlpatterns = [
    path("", include(router.urls)),
]
