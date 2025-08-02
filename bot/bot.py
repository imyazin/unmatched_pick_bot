from dotenv import load_dotenv
import logging
import os
from typing import List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from system import HeroWinrateSystem


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.winrate_system = HeroWinrateSystem()
        self.user_sessions = {}  # Хранит состояние пользователей

    def create_application(self):
        """Создает приложение бота"""
        application = Application.builder().token(self.token).build()

        # Обработчики команд
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("heroes", self.list_heroes))
        application.add_handler(CommandHandler("clear", self.clear_session))

        # Обработчики сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(CallbackQueryHandler(self.button_callback))

        return application

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        self.user_sessions[user_id] = {'enemy_team': []}

        welcome_text = """
🎮 **Добро пожаловать в бота для помощи с контрпиками для соревновательного Unmatched!**

Я помогу вам найти лучших персонажей с наибольшим общим винрейтом для введенного набора героев.

**Как пользоваться:**
• Напишите героев противника через пробел
• Получите топ-10 лучших контрпиков
• Используйте /help для подробной справки

**Пример:**
`Achilles, Ciri, Robin`
        """

        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📖 **Справка по использованию бота**

**Команды:**
• `/start` - Начать работу с ботом
• `/help` - Показать эту справку
• `/heroes` - Показать список всех персонажей
• `/clear` - Очистить текущую сессию

**Использование:**
1. Напишите имена персонажей противника через запятую
2. Бот найдет и покажет топ-10 лучших контр-персонажей
3. Нажмите на персонажа для подробной информации

**Примеры запросов:**
• `Achilles, Ciri, Robin`
• `ach cir robi` (можно без запятых и частично)

**Особенности:**
• Поиск работает по частичному совпадению имен
• Регистр не важен
• Для поиска например T. Rex достаточно ввести t.
        """

        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def list_heroes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список всех персонажей"""
        heroes_text = "📋 **Список всех персонажей:**\n\n"

        heroes_text += "\n".join(f"• {hero}" for hero in self.winrate_system.hero_names)

        # Telegram имеет ограничение на длину сообщения
        if len(heroes_text) > 4000:
            parts = [heroes_text[i:i + 4000] for i in range(0, len(heroes_text), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='Markdown')
        else:
            await update.message.reply_text(heroes_text, parse_mode='Markdown')

    async def clear_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Очищает сессию пользователя"""
        user_id = update.effective_user.id
        self.user_sessions[user_id] = {'enemy_team': []}
        await update.message.reply_text("✅ Сессия очищена. Можете вводить новую команду противника.")

    def parse_hero_input(self, text: str) -> Tuple[List[str], List[str]]:
        """Парсит ввод пользователя и находит персонажей"""
        # Разделяем по запятым или пробелам
        if ',' in text:
            raw_names = [name.strip() for name in text.split(',')]
        else:
            raw_names = text.split()

        found_heroes = []
        not_found = []

        for raw_name in raw_names:
            if not raw_name:
                continue

            hero = self.winrate_system.find_hero_by_name(raw_name)
            if hero:
                found_heroes.append(hero)
            else:
                not_found.append(raw_name)

        return found_heroes, not_found

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        text = update.message.text

        # Инициализируем сессию если её нет
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {'enemy_team': []}

        # Парсим ввод
        found_heroes, not_found = self.parse_hero_input(text)

        if not found_heroes:
            error_text = "❌ Персонажи не найдены.\n\n"
            if not_found:
                error_text += f"Не удалось найти: {', '.join(not_found)}\n"
            error_text += "Используйте /heroes для просмотра списка всех персонажей."
            await update.message.reply_text(error_text)
            return

        # Обновляем команду противника
        self.user_sessions[user_id]['enemy_team'] = found_heroes

        # Формируем ответ
        response = f"🎯 **Команда противника:** {', '.join(found_heroes)}\n\n"

        if not_found:
            response += f"⚠️ Не найдены: {', '.join(not_found)}\n\n"

        # Получаем лучших контр-персонажей
        best_counters = self.winrate_system.find_best_heroes(found_heroes, top_n=10)

        if not best_counters:
            response += "❌ Не удалось найти подходящих персонажей."
            await update.message.reply_text(response, parse_mode='Markdown')
            return

        response += "🏆 **Топ-10 лучших контр-персонажей:**\n\n"

        # Создаем кнопки для детальной информации
        keyboard = []
        for i, (hero, winrate) in enumerate(best_counters, 1):
            response += f"{i:2d}. **{hero}** - {winrate:.1%}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i}. {hero} ({winrate:.1%})",
                callback_data=f"details_{hero}"
            )])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        user_id = query.from_user.id

        await query.answer()

        if user_id not in self.user_sessions:
            await query.edit_message_text("❌ Сессия истекла. Используйте /start для начала работы.")
            return

        if query.data.startswith("details_"):
            hero = query.data.replace("details_", "")
            enemy_team = self.user_sessions[user_id]['enemy_team']

            details = self.winrate_system.get_hero_details(hero, enemy_team)

            detail_text = f"📊 **Детали для {hero}**\n\n"
            detail_text += f"📈 **Средний винрейт:** {details['average_winrate']:.1%}\n\n"
            detail_text += "⚔️ **Матчапы:**\n"

            for enemy, info in details['matchups'].items():
                winrate = info['winrate']
                games = info['games']
                emoji = "🟢" if winrate > 0.6 else "🟡" if winrate > 0.4 else "🔴"
                detail_text += f"{emoji} vs {enemy}: {winrate:.1%} игр: {games}\n"

            # Кнопка возврата
            back_keyboard = [[InlineKeyboardButton("← Назад к списку", callback_data="back_to_list")]]
            reply_markup = InlineKeyboardMarkup(back_keyboard)

            await query.edit_message_text(detail_text, parse_mode='Markdown', reply_markup=reply_markup)

        elif query.data == "back_to_list":
            # Возвращаемся к списку
            enemy_team = self.user_sessions[user_id]['enemy_team']
            best_counters = self.winrate_system.find_best_heroes(enemy_team, top_n=10)

            response = f"🎯 **Команда противника:** {', '.join(enemy_team)}\n\n"
            response += "🏆 **Топ-10 лучших контр-персонажей:**\n\n"

            keyboard = []
            for i, (hero, winrate) in enumerate(best_counters, 1):
                response += f"{i:2d}. **{hero}** - {winrate:.1%}\n"
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {hero} ({winrate:.1%})",
                    callback_data=f"details_{hero}"
                )])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(response, parse_mode='Markdown', reply_markup=reply_markup)


def main():
    """Основная функция для запуска бота"""
    BOT_TOKEN = os.environ["BOT_TOKEN"]

    bot = TelegramBot(BOT_TOKEN)
    application = bot.create_application()

    print("🤖 Бот запускается...")
    print("Нажмите Ctrl+C для остановки")

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()