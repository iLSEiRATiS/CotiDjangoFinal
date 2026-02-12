from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction, models
from django.urls import reverse_lazy
from django.views import generic
from rest_framework import viewsets, permissions, filters

from .forms import ProductForm
from .models import Product, Category, Offer
from .serializers import ProductSerializer, CategorySerializer, OfferSerializer
from orders.forms import OrderForm, OrderItemSimpleForm
from orders.models import Order, OrderItem


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = None
    lookup_field = "slug"
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "descripcion"]


class OfferViewSet(viewsets.ModelViewSet):
    queryset = Offer.objects.select_related("producto", "categoria").all()
    serializer_class = OfferSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "descripcion", "producto__nombre", "categoria__nombre"]
    ordering_fields = ["empieza", "termina", "creado_en", "porcentaje"]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("user", "categoria").all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "descripcion", "slug", "categoria__nombre"]
    ordering_fields = ["creado_en", "precio", "nombre"]

    def get_queryset(self):
        qs = super().get_queryset()
        categoria = self.request.query_params.get("categoria")
        q = self.request.query_params.get("q") or self.request.query_params.get("search")
        activo = self.request.query_params.get("activo")
        if q:
            qs = qs.filter(
                models.Q(nombre__icontains=q)
                | models.Q(descripcion__icontains=q)
                | models.Q(slug__icontains=q)
                | models.Q(categoria__nombre__icontains=q)
            )
        if categoria:
            qs = qs.filter(categoria__slug=categoria)
        if activo is not None:
            qs = qs.filter(activo=str(activo).lower() in ["true", "1", "yes"])
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProductCreateView(LoginRequiredMixin, generic.CreateView):
    model = Product
    form_class = ProductForm
    template_name = "products/form.html"
    success_url = reverse_lazy("product-new")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class StoreHomeView(generic.TemplateView):
    template_name = "store/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["destacados"] = Product.objects.filter(activo=True).select_related("categoria")[:6]
        ctx["categorias"] = Category.objects.all()
        return ctx


class StoreListView(generic.ListView):
    template_name = "store/catalogo.html"
    paginate_by = 12
    context_object_name = "products"

    def get_queryset(self):
        qs = Product.objects.filter(activo=True).select_related("categoria")
        cat = self.request.GET.get("categoria")
        q = self.request.GET.get("q")
        if cat:
            qs = qs.filter(categoria__slug=cat)
        if q:
            qs = qs.filter(nombre__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categorias"] = Category.objects.all()
        ctx["current_cat"] = self.request.GET.get("categoria") or ""
        ctx["q"] = self.request.GET.get("q") or ""
        ctx["static_categories"] = [
            "COTILLON",
            "GLOBOS Y PIÑATAS",
            "GUIRNALDAS Y DECORACIÓN",
            "DECORACION PARA TORTAS",
            "DECORACIÓN LED",
            "LUMINOSO",
            "LIBRERÍA",
            "DISFRACES",
            "DESCARTABLES",
            "REPOSTERIA",
            "MINIATURAS-JUGUETITOS",
            "FECHAS ESPECIALES",
            "LANZAPAPELITOS",
            "PAPELERA",
            "ARTICULOS CON SONIDO",
            "ARTICULOS EN TELGOPOR",
            "ARTÍCULOS PARA MANUALIDADES",
            "ARTÍCULOS PARA COMUNIÓN",
        ]
        return ctx


class StoreDetailView(generic.DetailView):
    model = Product
    template_name = "store/detalle.html"
    context_object_name = "product"


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, generic.TemplateView):
    template_name = "panel/admin_dashboard.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["counts"] = {
            "productos": Product.objects.count(),
            "categorias": Category.objects.count(),
        }
        return ctx


class UserDashboardView(LoginRequiredMixin, generic.TemplateView):
    template_name = "panel/user_dashboard.html"


class StoreOrderView(generic.FormView):
    template_name = "store/order.html"
    form_class = OrderForm
    success_url = reverse_lazy("home")

    def get_initial(self):
        initial = super().get_initial()
        user = self.request.user
        if user.is_authenticated:
            initial.update({
                "nombre": user.name or user.username,
                "email": user.email,
            })
        product_id = self.request.GET.get("product")
        if product_id:
            initial["product_id"] = product_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product_id = self.request.GET.get("product")
        item_form = OrderItemSimpleForm(initial={"product": product_id} if product_id else None)
        ctx["item_form"] = item_form
        return ctx

    def form_valid(self, form):
        item_form = OrderItemSimpleForm(self.request.POST)
        if not item_form.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            order = form.save(commit=False)
            if self.request.user.is_authenticated:
                order.user = self.request.user
            order.save()
            product = item_form.cleaned_data["product"]
            qty = item_form.cleaned_data["cantidad"]
            OrderItem.objects.create(
                order=order,
                product=product,
                cantidad=qty,
                precio_unitario=product.precio,
            )
            order.recalc_total()
        return super().form_valid(form)
