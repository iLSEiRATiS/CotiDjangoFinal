from django.contrib.auth import get_user_model, authenticate, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.urls import reverse_lazy
from django.views import generic
from rest_framework import viewsets, permissions, generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token

from .forms import CustomUserCreationForm, CustomAuthenticationForm, ProfileForm, CustomPasswordChangeForm
from .models import CustomUser
from .serializers import UserSerializer, RegisterSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]


class SignUpView(generic.CreateView):
    template_name = "signup.html"
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")


class CustomLoginView(LoginView):
    template_name = "login.html"
    authentication_form = CustomAuthenticationForm


class ProfileView(LoginRequiredMixin, generic.TemplateView):
    template_name = "account/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Perfil"
        ctx["profile_form"] = ProfileForm(instance=self.request.user)
        ctx["password_form"] = CustomPasswordChangeForm(self.request.user)
        return ctx

    def post(self, request, *args, **kwargs):
        if "change_password" in request.POST:
            pwd_form = CustomPasswordChangeForm(request.user, request.POST)
            profile_form = ProfileForm(instance=request.user)
            if pwd_form.is_valid():
                user = pwd_form.save()
                update_session_auth_hash(request, user)
                return self.render_to_response({
                    "title": "Perfil",
                    "profile_form": profile_form,
                    "password_form": CustomPasswordChangeForm(request.user),
                    "msg": "Contraseña actualizada",
                })
            return self.render_to_response({
                "title": "Perfil",
                "profile_form": profile_form,
                "password_form": pwd_form,
            })
        profile_form = ProfileForm(request.POST, instance=request.user)
        pwd_form = CustomPasswordChangeForm(request.user)
        if profile_form.is_valid():
            profile_form.save()
            return self.render_to_response({
                "title": "Perfil",
                "profile_form": ProfileForm(instance=request.user),
                "password_form": pwd_form,
                "msg": "Perfil actualizado",
            })
        return self.render_to_response({
            "title": "Perfil",
            "profile_form": profile_form,
            "password_form": pwd_form,
        })


class TokenLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get("username") or request.data.get("email")
        password = request.data.get("password")
        user = None

        if identifier and "@" in str(identifier):
            candidate = User.objects.filter(email__iexact=identifier).first()
            if candidate:
                user = authenticate(request, username=candidate.username, password=password)
        if not user and identifier:
            user = authenticate(request, username=identifier, password=password)

        if not user:
            return Response({"detail": "Credenciales invalidas"}, status=status.HTTP_400_BAD_REQUEST)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class SignupApiView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        headers = self.get_success_headers(serializer.data)
        token, _ = Token.objects.get_or_create(user=user)
        data = {"token": token.key, "user": UserSerializer(user).data}
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"user": UserSerializer(request.user).data})


class ProfileApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PasswordApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        old = (request.data.get("old_password") or "").strip()
        new = (request.data.get("new_password") or "").strip()
        if not request.user.check_password(old):
            return Response({"detail": "Contraseña actual incorrecta"}, status=status.HTTP_400_BAD_REQUEST)
        if not new:
            return Response({"detail": "La nueva contraseña es requerida"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new, user=request.user)
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(new)
        request.user.save()
        return Response({"detail": "Contraseña actualizada"})
