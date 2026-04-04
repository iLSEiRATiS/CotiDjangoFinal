from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "name", "first_name", "last_name", "phone", "address", "city", "zip_code", "role", "approval_status"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "name", "first_name", "last_name", "phone", "address", "city", "zip_code"]
        extra_kwargs = {"username": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        username = attrs.get("username") or attrs.get("email")
        if not username:
            raise serializers.ValidationError({"username": "Se requiere username o email"})
        attrs["username"] = username
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError({"username": "Usuario ya existe"})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
            name=validated_data.get("name", ""),
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            approval_status="pending",
            is_active=False,
        )
