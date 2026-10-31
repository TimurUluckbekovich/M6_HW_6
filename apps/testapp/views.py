from django.shortcuts import render

# Create your views here.
from apps.testapp.models import CustomUser
from apps.testapp.services import get_google_access_token, get_google_user_info
from rest_framework.permissions import IsAuthenticated, AllowAny
from apps.testapp.permissions import IsModeratorOrAdmin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache
from apps.testapp.tasks import User
from apps.testapp.tasks import send_welcome_email_task

from apps.testapp.serializers import CustomTokenObtainPairSerializer, GoogleAuthSerializer, RegisterSerializer, UserProfileSerializer


class PublicDataView(APIView):
   permission_classes = [IsAuthenticated]

   def get(self, request):
      return Response({"message": f"Привет, {request.user.email}! Это обычные данные."})


# Эндпоинт 2: Доступен ТОЛЬКО Модераторам и Админам
class SecretModeratorView(APIView):
   permission_classes = [IsModeratorOrAdmin]

   def get(self, request):
      return Response({"message": f"Секретная панель! Твоя роль: {request.user.role}."})
   
# --- 1. РЕГИСТРАЦИЯ (Открыта для всех) ---
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # 🚀 Запускаем фоновую задачу отправки письма через .delay()
            send_welcome_email_task.delay(user.email)
            
            return Response(
                {
                    "message": "Пользователь успешно зарегистрирован!",
                    "user": {"id": user.id, "email": user.email, "role": user.role}
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --- 2. ЛОГИН ЧЕРЕЗ JWT (Открыт для всех) ---
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# --- 3. ПРОФИЛЬ ТЕКУЩЕГО ЮЗЕРА (Нужен JWT Bearer токен) ---
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    

class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data['code']
        
        # 1. Обмениваем code на Google Access Token
        google_token = get_google_access_token(code)
        
        # 2. Получаем данные профиля Google (email, username)
        user_info = get_google_user_info(google_token)
        email = user_info.get('email')
        
        if not email:
            return Response(
                {"error": "Google не предоставил email пользователя."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Находим пользователя по email или создаем нового
        user = CustomUser.objects.filter(email=email).first()
        created = False

        if not user:
            user = CustomUser.objects.create_user(
                email=email,
                username=user_info.get('name', ''),
                role=CustomUser.Role.USER,
                is_active=True
            )
            user.set_unusable_password()
            user.save()
            created = True

        # 4. Генерируем ваши внутренние SimpleJWT токены
        refresh = RefreshToken.for_user(user)
        refresh['email'] = user.email
        refresh['role'] = user.role
        refresh['phone'] = user.phone or ''

        return Response({
            "message": "Успешная авторизация через Google",
            "is_new_user": created,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role,
                "phone": user.phone,
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)
        
# 🧠 А ВОТ ПРИМЕР С REDIS KЭШЕМ (Кэширование списка юзеров для Админа)
class AdminUsersListView(APIView):
    """Пример ручки с простым и понятным кэшированием через Redis."""
    
    def get(self, request):
        cache_key = "all_users_list"
        
        # 1. Проверяем, есть ли готовый список в Redis
        cached_data = cache.get(cache_key)
        if cached_data:
            print("--- ОТДАЕМ ДАННЫЕ ИЗ REDIS КЭША ---")
            return Response(cached_data)

        # 2. Если в Redis пусто — запрашиваем из базы PostgreSQL
        print("--- ДЕЛАЕМ ЗАПРОС К БАЗЕ ДАННЫХ PostgreSQL ---")
        users = User.objects.all().values("id", "email", "role", "is_active")
        data = list(users)

        # 3. Кладем результат в Redis на 60 секунд
        cache.set(cache_key, data, timeout=60)

        return Response(data)