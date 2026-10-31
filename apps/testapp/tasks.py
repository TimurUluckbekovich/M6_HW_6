import time
from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from apps.testapp.models import CustomUser

User = get_user_model()


# 💥 ПРИМЕР 1: Фоновая задача (Worker)
# Реальный кейс: При регистрации отправляем приветственное письмо.
# Запрос к почтовому серверу занимает 2-4 секунды. Если делать синхронно — фронт зависнет.
@shared_task
def send_welcome_email_task(user_email: str):
    """Отправка приветственного письма в фоновом режиме."""
    # Имитируем задержку сети
    time.sleep(3)
    
    # Реальная отправка (требует настроек EMAIL_HOST в settings.py)
    # send_mail(
    #     subject="Добро пожаловать!",
    #     message="Спасибо за регистрацию на нашей платформе!",
    #     from_email="noreply@myproject.com",
    #     recipient_list=[user_email],
    # )
    
    print(f"[Celery Worker] Успешно отправлено письмо для {user_email}")
    return f"Email sent to {user_email}"


# ⏰ ПРИМЕР 2: Периодическая задача (Beat)
# Реальный кейс: Каждую ночь очищать inactive/unverified пользователей или собирать статистику.
@shared_task
def monthly_user_stats_task():
    """Считает общее количество пользователей и выводит статистику."""
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    
    report = f"[Celery Beat Report] Всего юзеров: {total_users}, Активных: {active_users}"
    print(report)
    return report

@shared_task
def clean_inactive_users_task(days=30):
    """Удаляет пользователей с флагом is_active=False."""
    # При необходимости можно добавить фильтрацию по дате регистрации/последнего входа, 
    # но базовое условие — фильтрация по is_active=False
    inactive_users = CustomUser.objects.filter(is_active=False)
    count, _ = inactive_users.delete()
    
    report = f"Удалено неактивных пользователей: {count}"
    print(report)
    return report

@shared_task
def send_daily_admin_report_task():
    """Считает количество пользователей по ролям и выводит в консоль."""
    admin_count = CustomUser.objects.filter(role=CustomUser.Role.ADMIN).count()
    moderator_count = CustomUser.objects.filter(role=CustomUser.Role.MODERATOR).count()
    user_count = CustomUser.objects.filter(role=CustomUser.Role.USER).count()
    
    report = (
        f"Ежедневный отчет по ролям — "
        f"ADMIN: {admin_count}, MODERATOR: {moderator_count}, USER: {user_count}"
    )
    print(report)
    return report