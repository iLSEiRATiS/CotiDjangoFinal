from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=110, blank=True)
    descripcion = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Product(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products")
    categoria = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    nombre = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.TextField(blank=True)
    imagen = models.ImageField(upload_to="products/", blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, default="")
    atributos = models.JSONField(default=dict, blank=True)
    atributos_stock = models.JSONField(default=dict, blank=True)
    atributos_precio = models.JSONField(default=dict, blank=True)
    stock = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self) -> str:
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug and self.nombre:
            base = slugify(self.nombre)[:110]
            candidate = base
            counter = 1
            while Product.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                counter += 1
                candidate = f"{base}-{counter}"
            self.slug = candidate
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="extra_images")
    image = models.ImageField(upload_to="products/gallery/", blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Imagen de producto"
        verbose_name_plural = "Imagenes de producto"

    def __str__(self):
        return f"{self.product_id} - {self.order}"


class Offer(models.Model):
    nombre = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    descripcion = models.TextField(blank=True)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, help_text="Ej: 10.00 para 10%")
    producto = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name="ofertas")
    categoria = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name="ofertas")
    activo = models.BooleanField(default=True)
    empieza = models.DateTimeField(null=True, blank=True)
    termina = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Oferta"
        verbose_name_plural = "Ofertas"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)[:130]
        super().save(*args, **kwargs)

    @property
    def esta_activa(self):
        if not self.activo:
            return False
        now = timezone.now()
        if self.empieza and now < self.empieza:
            return False
        if self.termina and now > self.termina:
            return False
        return True


class HomeImage(models.Model):
    SECTION_CHOICES = [
        ("hero", "Hero"),
        ("category_tile", "Explora por categoria"),
        ("featured_collection", "Colecciones destacadas"),
    ]

    key = models.SlugField(max_length=80, unique=True)
    section = models.CharField(max_length=20, choices=SECTION_CHOICES)
    title = models.CharField(max_length=120, blank=True)
    image_url = models.URLField()
    target_url = models.CharField(max_length=255, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["section", "order", "id"]
        verbose_name = "Imagen Home"
        verbose_name_plural = "Imagenes Home"

    def __str__(self):
        return f"{self.section}: {self.title or self.key}"


class HomeMarquee(models.Model):
    text = models.CharField(max_length=255, blank=True, default="")
    text_color = models.CharField(max_length=7, default="#ffffff")
    background_color = models.CharField(max_length=7, default="#dc3545")
    activo = models.BooleanField(default=False)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Franja Home"
        verbose_name_plural = "Franjas Home"

    def __str__(self):
        return self.text or "Franja Home"


class SupplierContact(models.Model):
    nombre = models.CharField(max_length=120)
    apellido = models.CharField(max_length=120)
    telefono = models.CharField(max_length=40)
    mensaje = models.TextField()
    archivo = models.FileField(upload_to="supplier_contacts/files/", blank=True, null=True)
    revisado = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Contacto de proveedor"
        verbose_name_plural = "Contactos de proveedores"

    def __str__(self):
        return f"{self.nombre} {self.apellido}".strip()
