from django.db import models

class TelegramUser(models.Model):
    chat_id = models.IntegerField(unique=True)
    username = models.CharField(null=True, blank=True)
    first_name = models.CharField(null=True, blank=True)

    def __str__(self):
        if self.first_name:
            return self.first_name
        elif self.username:
            return self.username
        else:
            return str(self.chat_id)


class Reminder(models.Model):
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE)

    text = models.TextField()

    remind_at = models.DateTimeField()

    def __str__(self):
        return f'Напоминание для {self.user.first_name} в {self.remind_at.strftime("%H:%M")}'
