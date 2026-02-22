from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.http import JsonResponse, HttpResponse
from django.urls import include, path, re_path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.utils import timezone

from products.views import ProductCreateView
from users.views import SignUpView, CustomLoginView, ProfileView
from products import views as product_views
from products.views import AdminDashboardView, UserDashboardView
from orders.views import MyOrdersView
from . import api_bridge

# Cambia el enlace "Ver sitio" del admin para apuntar al frontend React local
admin.site.site_url = "http://localhost:5173"


def health_check(_request):
    return JsonResponse({"ok": True, "ts": int(timezone.now().timestamp()), "service": "cotidjango"})


urlpatterns = [
    path("", health_check, name="home"),
    path("catalogo/", product_views.StoreListView.as_view(), name="catalogo"),
    path("producto/<int:pk>/", product_views.StoreDetailView.as_view(), name="product-detail"),
    path("orden/nueva/", product_views.StoreOrderView.as_view(), name="order-new"),
    path("panel/admin/", AdminDashboardView.as_view(), name="admin-panel"),
    path("panel/usuario/", UserDashboardView.as_view(), name="user-panel"),
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("account/", ProfileView.as_view(), name="account"),
    path("mis-ordenes/", MyOrdersView.as_view(), name="orders-mine"),
    path("productos/nuevo/", ProductCreateView.as_view(), name="product-new"),
    path("api/", include("users.urls")),
    path("api/", include("products.urls")),
    path("api/", include("orders.urls")),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/browsable-auth/", include("rest_framework.urls")),
]

# API bridge con las rutas esperadas por el frontend React
urlpatterns += [
    re_path(r"^api/auth/register/?$", api_bridge.AuthRegisterView.as_view(), name="api-bridge-register"),
    re_path(r"^api/auth/login/?$", api_bridge.AuthLoginView.as_view(), name="api-bridge-login"),
    re_path(r"^api/auth/me/?$", api_bridge.AuthMeView.as_view(), name="api-bridge-me"),
    re_path(r"^api/account/profile/?$", api_bridge.AccountProfileView.as_view(), name="api-bridge-profile"),
    re_path(r"^api/account/password/?$", api_bridge.AccountPasswordView.as_view(), name="api-bridge-password"),
    re_path(r"^api/home-images/?$", api_bridge.HomeImagesView.as_view(), name="api-bridge-home-images"),
    re_path(r"^api/products/?$", api_bridge.ProductListView.as_view(), name="api-bridge-products"),
    re_path(r"^api/products/(?P<pk>[^/]+)/?$", api_bridge.ProductDetailView.as_view(), name="api-bridge-product-detail"),
    re_path(r"^api/orders/?$", api_bridge.OrderCreateView.as_view(), name="api-bridge-orders"),
    re_path(r"^api/orders/mine/?$", api_bridge.MyOrdersView.as_view(), name="api-bridge-orders-mine"),
    re_path(r"^api/orders/(?P<pk>[^/]+)/?$", api_bridge.OrderDetailView.as_view(), name="api-bridge-order-detail"),
    re_path(r"^api/orders/(?P<pk>[^/]+)/pay/?$", api_bridge.OrderMarkPaidView.as_view(), name="api-bridge-order-pay"),
    re_path(r"^api/admin/overview/?$", api_bridge.AdminOverviewView.as_view(), name="api-bridge-admin-overview"),
    re_path(r"^api/admin/users/?$", api_bridge.AdminUsersView.as_view(), name="api-bridge-admin-users"),
    re_path(r"^api/admin/users/(?P<pk>[^/]+)/?$", api_bridge.AdminUserDetailView.as_view(), name="api-bridge-admin-user"),
    re_path(r"^api/admin/orders/?$", api_bridge.AdminOrdersView.as_view(), name="api-bridge-admin-orders"),
    re_path(r"^api/admin/orders/(?P<pk>[^/]+)/?$", api_bridge.AdminOrderDetailView.as_view(), name="api-bridge-admin-order"),
    re_path(r"^api/admin/orders/(?P<pk>[^/]+)/pdf/?$", api_bridge.AdminOrderPdfView.as_view(), name="api-bridge-admin-order-pdf"),
    re_path(r"^api/admin/products/?$", api_bridge.AdminProductsView.as_view(), name="api-bridge-admin-products"),
    re_path(r"^api/admin/products/(?P<pk>[^/]+)/?$", api_bridge.AdminProductDetailView.as_view(), name="api-bridge-admin-product"),
    re_path(r"^api/admin/upload-image/?$", api_bridge.AdminUploadImageView.as_view(), name="api-bridge-admin-upload"),
    re_path(r"^api/offers/?$", api_bridge.OffersListView.as_view(), name="api-bridge-offers"),
    re_path(r"^api/admin/offers/?$", api_bridge.AdminOffersView.as_view(), name="api-bridge-admin-offers"),
    re_path(r"^api/admin/offers/(?P<pk>[^/]+)/?$", api_bridge.AdminOfferDetailView.as_view(), name="api-bridge-admin-offer"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
