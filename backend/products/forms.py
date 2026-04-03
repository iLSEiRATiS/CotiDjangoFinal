from django import forms
import re

from .models import Product, ProductImage, HomeMarquee


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["nombre", "categoria", "precio", "stock", "descripcion", "imagen", "image_url", "video_url", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "precio": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "image_url": forms.URLInput(attrs={"class": "form-control"}),
            "video_url": forms.URLInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    imagen = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "form-control"}))


class ProductAdminForm(forms.ModelForm):
    image_urls_bulk = forms.CharField(
        required=False,
        label="Image url (multiples)",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "style": "font-family: monospace;",
                "placeholder": "Pega URLs separadas por linea, coma, punto y coma o |",
            }
        ),
        help_text="La primera URL se guarda en image_url. El resto se guarda como imagenes extra del producto.",
    )

    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            urls = []
            if self.instance.image_url:
                urls.append(self.instance.image_url)
            extra_urls = list(
                ProductImage.objects.filter(product=self.instance, activo=True)
                .order_by("order", "id")
                .values_list("image_url", flat=True)
            )
            for url in extra_urls:
                if url and url not in urls:
                    urls.append(url)
            self.fields["image_urls_bulk"].initial = "\n".join(urls)

    def _parse_urls(self, raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return []
        urls = []
        seen = set()
        parts = [p.strip() for p in re.split(r"[\r\n,;|]+", text)]
        for part in parts:
            if not part:
                continue
            url = part.strip()
            if not url.startswith(("http://", "https://")):
                continue
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
        return urls

    def save(self, commit=True):
        product = super().save(commit=commit)
        if not commit:
            return product

        urls = self._parse_urls(self.cleaned_data.get("image_urls_bulk"))
        if urls:
            main_url = urls[0]
            if product.image_url != main_url:
                product.image_url = main_url
                product.save(update_fields=["image_url"])
            gallery_urls = urls[1:]
            existing = {x.image_url: x for x in ProductImage.objects.filter(product=product)}
            keep = set()
            for idx, url in enumerate(gallery_urls, start=1):
                keep.add(url)
                row = existing.get(url)
                if row:
                    changed = False
                    if row.order != idx:
                        row.order = idx
                        changed = True
                    if not row.activo:
                        row.activo = True
                        changed = True
                    if changed:
                        row.save(update_fields=["order", "activo"])
                else:
                    ProductImage.objects.create(product=product, image_url=url, order=idx, activo=True)
            ProductImage.objects.filter(product=product).exclude(image_url__in=keep).delete()
        return product


class HomeMarqueeAdminForm(forms.ModelForm):
    class Meta:
        model = HomeMarquee
        fields = "__all__"
        widgets = {
            "text": forms.TextInput(attrs={"class": "vTextField"}),
            "text_color": forms.TextInput(attrs={"type": "color", "style": "width: 64px; height: 40px; padding: 4px;"}),
            "background_color": forms.TextInput(attrs={"type": "color", "style": "width: 64px; height: 40px; padding: 4px;"}),
        }
