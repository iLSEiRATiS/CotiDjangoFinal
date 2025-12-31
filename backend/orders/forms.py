from django import forms

from .models import Order, OrderItem
from products.models import Product


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["nombre", "email", "direccion", "ciudad", "estado", "cp", "telefono", "nota"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "ciudad": forms.TextInput(attrs={"class": "form-control"}),
            "estado": forms.TextInput(attrs={"class": "form-control"}),
            "cp": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "nota": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class OrderItemSimpleForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(activo=True),
        widget=forms.Select(attrs={"class": "form-select"})
    )
    cantidad = forms.IntegerField(min_value=1, initial=1, widget=forms.NumberInput(attrs={"class": "form-control"}))
