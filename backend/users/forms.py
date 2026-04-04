from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm

from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Correo electrónico')
    phone = forms.CharField(required=False, label='Teléfono')
    address = forms.CharField(required=False, label='Dirección')
    city = forms.CharField(required=False, label='Ciudad')
    zip_code = forms.CharField(required=False, label='CP')

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "name", "phone", "address", "city", "zip_code")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["name", "email", "phone", "address", "city", "zip_code"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "zip_code": forms.TextInput(attrs={"class": "form-control"}),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class AdminCustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(required=True, label="Nombre")
    last_name = forms.CharField(required=True, label="Apellido")
    email = forms.EmailField(required=True, label="Email")
    approval_status = forms.ChoiceField(
        required=True,
        label="Estado de aprobacion",
        choices=CustomUser.APPROVAL_CHOICES,
        initial="pending",
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("first_name", "last_name", "email", "password1", "password2", "approval_status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("username", None)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = str(self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("El email es obligatorio.")
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe un usuario con ese email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        first_name = str(self.cleaned_data.get("first_name") or "").strip()
        last_name = str(self.cleaned_data.get("last_name") or "").strip()
        email = self.cleaned_data["email"]
        approval_status = self.cleaned_data.get("approval_status") or "pending"
        user.username = email
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.name = " ".join(part for part in [first_name, last_name] if part).strip()
        user.approval_status = approval_status
        if commit:
            user.save()
        return user
