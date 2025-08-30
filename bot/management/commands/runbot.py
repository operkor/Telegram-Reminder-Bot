from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)
from django.core.management.base import BaseCommand
from django.conf import settings
from bot.models import TelegramUser, Reminder
from asgiref.sync import sync_to_async
from datetime import datetime, timedelta
from django.utils import timezone

GET_TEXT, GET_TIME = range(2)

@sync_to_async
def get_or_create_user(user_info):
    user, created = TelegramUser.objects.get_or_create(
        chat_id=user_info.id,
        defaults={'username': user_info.username, 'first_name': user_info.first_name}
    )
    return user, created


@sync_to_async
def create_reminder_db(user, text, remind_at):
    Reminder.objects.create(user=user, text=text, remind_at=remind_at)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_info = update.message.from_user
    user, created = await get_or_create_user(user_info)

    reply_keyboard = [["Создать напоминание"], ["Мои напоминания"]]

    if created:
        reply_text = f'Привет, {user.first_name}! Я твой бот-напоминалка.'
    else:
        reply_text = f'С возвращением, {user.first_name}!'

    await update.message.reply_text(
        reply_text,
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )


async def new_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Хорошо, давай создадим новое напоминание.\n'
        'Какой текст мне нужно запомнить? (или отправь /cancel для отмены)',
        reply_markup=ReplyKeyboardRemove(),
    )
    return GET_TEXT


async def get_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['reminder_text'] = update.message.text
    await update.message.reply_text(
        'Отлично! Теперь введи время, когда тебе нужно напомнить (в формате ЧЧ:ММ).',
    )
    return GET_TIME


async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    remind_time_str = update.message.text
    try:
        naive_time = datetime.strptime(remind_time_str, '%H:%M').time()
        now = timezone.now()

        aware_datetime = timezone.make_aware(datetime.combine(now.date(), naive_time))

        if aware_datetime < now:
            aware_datetime += timedelta(days=1)

        user_info = update.message.from_user
        user, _ = await get_or_create_user(user_info)

        reminder_text = context.user_data['reminder_text']
        await create_reminder_db(user, reminder_text, aware_datetime)

        day_text = "сегодня" if aware_datetime.date() == now.date() else "завтра"
        await update.message.reply_text(
            f'Готово! Я напомню тебе "{reminder_text}" {day_text} в {remind_time_str}.'
        )

        reply_keyboard = [["Создать напоминание"], ["Мои напоминания"]]
        await update.message.reply_text(
            'Что делаем дальше?',
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
        )
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text('Это не похоже на время. Пожалуйста, введи время в формате ЧЧ:ММ.')
        return GET_TIME


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Действие отменено.', reply_markup=ReplyKeyboardRemove()
    )
    reply_keyboard = [["Создать напоминание"], ["Мои напоминания"]]
    await update.message.reply_text(
        'Что делаем дальше?',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return ConversationHandler.END


@sync_to_async()
def get_user_reminders(user):
    reminders = []
    for reminder in user.reminder_set.all():
        reminders.append(reminder)
    return list(user.reminder_set.order_by('remind_at'))


async def show_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_info = update.message.from_user
    user, _ = await get_or_create_user(user_info)
    reminders = await get_user_reminders(user)

    if not reminders:
        await update.message.reply_text('У вас пока нет активных напоминаний.')
        return

    await update.message.reply_text('Вот твои напоминания (нажми на кнопку, чтобы удалить):')
    for reminder in reminders:
        local_time = reminder.remind_at.astimezone(timezone.get_current_timezone())

        callback_data = f"delete_{reminder.id}"

        keyboard = [
            [InlineKeyboardButton("Удалить 🗑️", callback_data=callback_data)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message_text = f"▪️ {reminder.text} в {local_time.strftime('%H:%M %d.%m.%Y')}"

        await update.message.reply_text(text=message_text, reply_markup=reply_markup)

@sync_to_async
def delete_reminder_db(reminder_id, user_chat_id):
    try:
        reminder = Reminder.objects.get(id=reminder_id, user__chat_id=user_chat_id)
        reminder.delete()
        return True
    except Reminder.DoesNotExist:
        return False

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("delete_"):
        reminder_id = int(data.split("_")[1])
        user_chat_id = query.from_user.id

        was_deleted = await delete_reminder_db(reminder_id, user_chat_id)

        if was_deleted:
            await query.edit_message_text(text=f'✅ Напоминание удалено')
        else:
            await query.edit_message_text(text=f'Это напоминание уже было удалено')


class Command(BaseCommand):
    help = 'Запускает Telegram-бота'

    def handle(self, *args, **options):
        application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        application.add_handler(MessageHandler(filters.Regex('^Мои напоминания$'), show_reminders))
        application.add_handler(CallbackQueryHandler(button_callback_handler))

        conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex('^Создать напоминание$'), new_reminder_start)],
            states={
                GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_text)],
                GET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )

        application.add_handler(CommandHandler("start", start))
        application.add_handler(conv_handler)

        self.stdout.write(self.style.SUCCESS('Бот успешно запущен...'))
        application.run_polling()