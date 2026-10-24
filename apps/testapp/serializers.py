from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.testapp.models import CustomUser


# 1. Сериализатор для регистрации
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ("email", "username", "phone", "password", "password_confirm")

    def validate(self, attrs):
        # Проверяем совпадение паролей
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password": "Пароли не совпадают."})
        return attrs

    def create(self, validated_data):
        # Удаляем поле подтверждения пароля — его нет в модели
        validated_data.pop("password_confirm")
        
        # Используем наш кастомный менеджер (он сам захэширует пароль)
        user = CustomUser.objects.create_user(**validated_data)
        return user


# 2. Сериализатор для просмотра профиля
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ("id", "email", "username", "role", "phone", "avatar")
        read_only_fields = ("id", "email", "role")  # Нельзя поменять email и роль через профиль


# 3. Кастомный JWT-сериализатор (добавляем email и role в ответ)
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['email'] = self.user.email
        data['role'] = self.user.role
        return data
    
class GoogleAuthSerializer(serializers.Serializer):
    code = serializers.CharField(
        required=True, 
        help_text="Одноразовый code, полученный фронтендом от Google"
    )