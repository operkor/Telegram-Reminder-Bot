import httpx
from django.core.management.base import BaseCommand
from django.conf import settings
from bot.models import Reminder
from django.utils import timezone
import time
from django.db import connection


class Command(BaseCommand):
    help = 'Запускает процесс отправки напоминаний'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Процесс отправки напоминаний запущен..."))

        while True:
            now = timezone.now()

            self.stdout.write(f"--- Проверка в {now.strftime('%Y-%m-%d %H:%M:%S %Z')} ---")

            reminders_to_send = list(Reminder.objects.filter(remind_at__lte=now))

            if not reminders_to_send:
                self.stdout.write("Нет напоминаний для отправки.")
            else:
                self.stdout.write(self.style.SUCCESS(f"Найдено {len(reminders_to_send)} напоминаний для отправки!"))

            for reminder in reminders_to_send:
                try:
                    message = f"🔔 Напоминаю: {reminder.text}"

                    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
                    params = {'chat_id': reminder.user.chat_id, 'text': message}

                    response = httpx.get(url, params=params)
                    response.raise_for_status()

                    self.stdout.write(self.style.SUCCESS(f"Отправлено напоминание для '{reminder.user}'"))

                    reminder.delete()

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Ошибка при отправке напоминания ID {reminder.id}: {e}"))

            connection.close()

            time.sleep(60)