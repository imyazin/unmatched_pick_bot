from dotenv import load_dotenv
import logging
import redis
import os
from typing import List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from system import HeroWinrateSystem
from redis_helper import RedisHelper


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0)),
    decode_responses=True
)


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.winrate_system = HeroWinrateSystem()
        self.user_sessions = {}  # Хранит состояние пользователей
        self.redis_helper = RedisHelper(redis_client)

    def create_application(self):
        """Создает приложение бота"""
        application = Application.builder().token(self.token).build()

        # Обработчики команд
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("heroes", self.list_heroes))
        application.add_handler(CommandHandler("clear", self.clear_session))
        application.add_handler(CommandHandler("ban", self.ban_command))

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
• `/ban` - Список банов
• `/help` - Показать эту справку
• `/heroes` - Показать список всех персонажей
• `/clear` - Очистить текущую сессию

**Использование:**
1. Напишите имена персонажей противника через запятую
2. Бот найдет и покажет топ-10 лучших контр-пиков
3. Нажмите на персонажа для подробной информации

**Примеры запросов:**
• `Achilles, Ciri, Robin`
• `ach cir robi` (можно без запятых и частично)

**Особенности:**
• В подборке не участвуют персонажи с кол-вом игр меньше 10
• В подборке не участвуют забаненные персонажи
• Поиск работает по частичному совпадению имен
• Регистр не важен
• Для поиска например `T. Rex` достаточно ввести `t`.
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

    def _build_ban_keyboard(self, user_id: int, page: int = 0, page_size: int = 20) -> InlineKeyboardMarkup:
        """Строит пагинированную клавиатуру со всеми героями и статусом бана"""
        heroes = self.winrate_system.hero_names
        total = len(heroes)
        start = page * page_size
        end = min(start + page_size, total)
        page_heroes = heroes[start:end]

        rows = []
        for hero in page_heroes:
            banned = self.redis_helper.is_character_banned(user_id, hero)
            mark = "🚫" if banned else "✅"
            rows.append([InlineKeyboardButton(f"{mark} {hero}", callback_data=f"toggleban_{hero}_{page}")])

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️", callback_data=f"banpage_{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{(total + page_size - 1)//page_size}", callback_data="noop"))
        if end < total:
            nav.append(InlineKeyboardButton("➡️", callback_data=f"banpage_{page+1}"))
        rows.append(nav)

        rows.append([InlineKeyboardButton("Закрыть", callback_data="close_ban")])
        return InlineKeyboardMarkup(rows)

    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список всех героев с чек-боксами бана"""
        user_id = update.effective_user.id
        keyboard = self._build_ban_keyboard(user_id=user_id, page=0)
        await update.message.reply_text("Выберите героев для бана (забаненные герои помечены 🚫):", reply_markup=keyboard)

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

        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {'enemy_team': []}

        found_heroes, not_found = self.parse_hero_input(text)

        if not found_heroes:
            error_text = "❌ Персонажи не найдены.\n\n"
            if not_found:
                error_text += f"Не удалось найти: {', '.join(not_found)}\n"
            error_text += "Используйте /heroes для просмотра списка всех персонажей."
            await update.message.reply_text(error_text)
            return

        self.user_sessions[user_id]['enemy_team'] = found_heroes
        response = f"🎯 **Команда противника:** {', '.join(found_heroes)}\n\n"

        if not_found:
            response += f"⚠️ Не найдены: {', '.join(not_found)}\n\n"

        banned_heroes = self.redis_helper.get_bans_list(user_id)
        best_counters = self.winrate_system.find_best_heroes(found_heroes, top_n=10, exclude_heroes=banned_heroes)

        if not best_counters:
            response += "❌ Не удалось найти подходящих персонажей."
            await update.message.reply_text(response, parse_mode='Markdown')
            return

        response += "🏆 **Топ-10 лучших контр-пиков:**\n\n"

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

            detail_keyboard = [
                [InlineKeyboardButton("🚫 Добавить в бан", callback_data=f"ban_{hero}")],
                [InlineKeyboardButton("← Назад к списку", callback_data="back_to_list")]
            ]
            reply_markup = InlineKeyboardMarkup(detail_keyboard)

            await query.edit_message_text(detail_text, parse_mode='Markdown', reply_markup=reply_markup)

        elif query.data == "back_to_list":
            enemy_team = self.user_sessions[user_id]['enemy_team']
            banned_heroes = self.redis_helper.get_bans_list(user_id)
            best_counters = self.winrate_system.find_best_heroes(enemy_team, top_n=10, exclude_heroes=banned_heroes)

            response = f"🎯 **Команда противника:** {', '.join(enemy_team)}\n\n"
            response += "🏆 **Топ-10 лучших контр-пиков:**\n\n"

            keyboard = []
            for i, (hero, winrate) in enumerate(best_counters, 1):
                response += f"{i:2d}. **{hero}** - {winrate:.1%}\n"
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {hero} ({winrate:.1%})",
                    callback_data=f"details_{hero}"
                )])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(response, parse_mode='Markdown', reply_markup=reply_markup)

        elif query.data.startswith("ban_"):
            hero = query.data.replace("ban_", "")
            new_len = self.redis_helper.add_character_to_bans_list(user_id, hero)
            await query.answer(text=f"Добавлен в баны: {hero} (всего: {new_len})", show_alert=False)

        elif query.data == "show_bans":
            bans = self.redis_helper.get_bans_list(user_id)
            if bans:
                text = "Ваш список банов:\n\n" + "\n".join(f"• {name}" for name in bans)
            else:
                text = "Ваш список банов пуст."

            # Показываем отдельным сообщением, не ломая текущий экран
            await query.message.reply_text(text)

        elif query.data == "clear_bans":
            self.redis_helper.clear_bans_list(user_id)
            await query.answer(text="Список банов очищен", show_alert=False)

        elif query.data.startswith("toggleban_"):
            # toggleban_<Hero>_<page>
            _, hero, page_str = query.data.split("_", 2)
            page = int(page_str)
            if self.redis_helper.is_character_banned(user_id, hero):
                self.redis_helper.remove_character_from_bans_list(user_id, hero)
            else:
                self.redis_helper.add_character_to_bans_list(user_id, hero)

            # Перестраиваем клавиатуру текущей страницы
            keyboard = self._build_ban_keyboard(user_id=user_id, page=page)
            await query.edit_message_reply_markup(reply_markup=keyboard)

        elif query.data.startswith("banpage_"):
            page = int(query.data.split("_", 1)[1])
            keyboard = self._build_ban_keyboard(user_id=user_id, page=page)
            await query.edit_message_reply_markup(reply_markup=keyboard)

        elif query.data == "close_ban":
            await query.edit_message_text("Меню банов закрыто. Вводите команду соперников через запятую или пробел")


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