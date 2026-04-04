from math import ceil

from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Category, Offer, Product
from .api_common import (
    _norm_text,
    get_descendant_ids,
    resolve_product,
    serialize_category,
    serialize_product,
)


class CategoriesListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        items = Category.objects.select_related("parent").all().order_by("nombre", "id")
        data = [{
            "id": cat.id,
            "nombre": cat.nombre,
            "slug": cat.slug,
            "descripcion": cat.descripcion or "",
            "parent": cat.parent_id,
        } for cat in items]
        return Response({"items": data})


class ProductListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = (request.query_params.get("q") or request.query_params.get("search") or "").strip()
        category = request.query_params.get("category") or request.query_params.get("cat")
        category_id = request.query_params.get("category_id")
        include_inactive = str(request.query_params.get("all") or "").lower() in {"1", "true", "yes", "si", "s"}
        sort = (request.query_params.get("sort") or "").strip().lower()
        page = max(1, int(request.query_params.get("page") or 1))
        limit = max(1, min(100, int(request.query_params.get("limit") or 20)))

        qs = Product.objects.select_related("categoria").prefetch_related("extra_images")
        if not include_inactive:
            qs = qs.filter(activo=True)
        if q:
            q_norm = _norm_text(q)
            q_like = q.strip()
            tokens = [t for t in q_like.split() if t] or ([q_like] if q_like else [])
            search_filter = Q()
            for token in tokens:
                t = token.strip()
                if not t:
                    continue
                token_filter = (
                    Q(nombre__icontains=t)
                    | Q(descripcion__icontains=t)
                    | Q(slug__icontains=t)
                    | Q(categoria__nombre__icontains=t)
                )
                if q_norm != t.lower():
                    token_filter |= Q(nombre__icontains=q_norm) | Q(descripcion__icontains=q_norm)
                search_filter &= token_filter
            if search_filter:
                qs = qs.filter(search_filter)
        if category_id:
            try:
                root_id = int(category_id)
            except Exception:
                root_id = None
            if root_id:
                qs = qs.filter(categoria_id__in=get_descendant_ids(root_id))
        elif category:
            root = Category.objects.filter(slug=category).first()
            if not root:
                wanted = _norm_text(category)
                wanted_slug = _norm_text(slugify(category))
                wanted_space = wanted.replace("-", " ")
                for c in Category.objects.all().only("id", "nombre", "slug"):
                    name_norm = _norm_text(c.nombre)
                    slug_norm = _norm_text(c.slug)
                    if wanted == name_norm or wanted_slug == slug_norm or wanted_space == slug_norm.replace("-", " ") or wanted in name_norm or wanted in slug_norm:
                        root = c
                        break
            if root:
                qs = qs.filter(categoria_id__in=get_descendant_ids(root.id))

        if sort in {"mas_vendidos", "relevancia"}:
            qs = qs.annotate(sold=Coalesce(Sum("order_items__cantidad"), 0)).order_by("-sold", "-creado_en")
        elif sort == "precio_asc":
            qs = qs.order_by("precio")
        elif sort == "precio_desc":
            qs = qs.order_by("-precio")
        elif sort == "nombre_asc":
            qs = qs.order_by("nombre")
        elif sort == "nombre_desc":
            qs = qs.order_by("-nombre")
        else:
            qs = qs.order_by("-creado_en")

        total = qs.count()
        items = qs[(page - 1) * limit:(page - 1) * limit + limit]
        return Response({"items": [serialize_product(p, request) for p in items], "total": total, "page": page, "pages": ceil(total / limit) if total else 1})


class ProductDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        prod = resolve_product(pk)
        if not prod:
            return Response({"error": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_product(prod, request))


class OffersListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        now = timezone.now()
        offers = Offer.objects.filter(activo=True).filter(
            models.Q(empieza__isnull=True) | models.Q(empieza__lte=now),
            models.Q(termina__isnull=True) | models.Q(termina__gte=now),
        ).order_by("-porcentaje")
        data = [{
            "id": off.id,
            "slug": off.slug,
            "name": off.nombre,
            "description": off.descripcion,
            "percent": float(off.porcentaje),
            "product": serialize_product(off.producto, request) if off.producto else None,
            "category": serialize_category(off.categoria),
            "starts": off.empieza.isoformat() if off.empieza else None,
            "ends": off.termina.isoformat() if off.termina else None,
        } for off in offers]
        return Response({"items": data})
