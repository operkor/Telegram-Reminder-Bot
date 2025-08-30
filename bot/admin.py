from django.contrib import admin
from .models import TelegramUser, Reminder

admin.site.register(TelegramUser)
admin.site.register(Reminder)

