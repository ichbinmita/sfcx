import random
import time
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command

BOT_TOKEN = ""
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подключаемся к базе данных (файл создастся автоматически)
conn = sqlite3.connect('bot_database.db')
cursor = conn.cursor()

# Создаем таблицу для пользователей с новыми полями
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    bot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    username TEXT,
    balance INTEGER DEFAULT 10000,
    last_game INTEGER DEFAULT 0,
    status TEXT DEFAULT 'player',
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
)
''')
conn.commit()

# Начальный баланс для нового пользователя
START_BALANCE = 10000

# ID создателя
CREATOR_USERNAME = "@cxpyuser"
CREATOR_TELEGRAM_ID = 8258660794  # Замени на реальный ID создателя

# Функции для работы с базой данных
def get_user_by_telegram_id(user_id):
    """Получить данные пользователя по Telegram ID"""
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def get_user_by_bot_id(bot_id):
    """Получить данные пользователя по ID в боте"""
    cursor.execute('SELECT * FROM users WHERE bot_id = ?', (bot_id,))
    return cursor.fetchone()

def create_user(user_id, username=None):
    """Создать нового пользователя"""
    # Проверяем, не является ли это создатель
    status = 'player'
    if user_id == CREATOR_TELEGRAM_ID:
        status = 'creator'
        # Для создателя создаем запись с bot_id = 0
        cursor.execute('''
        INSERT OR REPLACE INTO users (bot_id, user_id, username, balance, status) 
        VALUES (0, ?, ?, ?, ?)
        ''', (user_id, username, START_BALANCE, status))
    else:
        # Для обычных пользователей
        cursor.execute('''
        INSERT INTO users (user_id, username, balance, status) 
        VALUES (?, ?, ?, ?)
        ''', (user_id, username, START_BALANCE, status))
    
    conn.commit()
    return get_user_by_telegram_id(user_id)

def update_balance(user_id, new_balance):
    """Обновить баланс пользователя"""
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', 
                  (new_balance, user_id))
    conn.commit()

def update_last_game(user_id, timestamp):
    """Обновить время последней игры"""
    cursor.execute('UPDATE users SET last_game = ? WHERE user_id = ?', 
                  (timestamp, user_id))
    conn.commit()

def get_next_bot_id():
    """Получить следующий доступный bot_id"""
    cursor.execute('SELECT MAX(bot_id) FROM users WHERE bot_id > 0')
    result = cursor.fetchone()[0]
    return 1 if result is None else result + 1

def get_user_stats():
    """Получить статистику всех пользователей"""
    cursor.execute('SELECT COUNT(*) FROM users WHERE bot_id > 0')
    total_players = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(balance) FROM users WHERE bot_id > 0')
    total_balance = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT MAX(balance) FROM users WHERE bot_id > 0')
    max_balance_result = cursor.fetchone()[0]
    max_balance = max_balance_result if max_balance_result else 0
    
    cursor.execute('''
    SELECT username, balance FROM users 
    WHERE bot_id > 0 AND balance = ?
    LIMIT 1
    ''', (max_balance,))
    richest_player = cursor.fetchone()
    
    return {
        'total_players': total_players,
        'total_balance': total_balance,
        'max_balance': max_balance,
        'richest_player': richest_player
    }

def init_creator():
    """Инициализировать запись создателя если её нет"""
    cursor.execute('SELECT * FROM users WHERE bot_id = 0')
    creator = cursor.fetchone()
    
    if not creator:
        cursor.execute('''
        INSERT INTO users (bot_id, user_id, username, balance, status) 
        VALUES (0, ?, ?, ?, ?)
        ''', (CREATOR_TELEGRAM_ID, CREATOR_USERNAME, START_BALANCE, 'creator'))
        conn.commit()
        print(f"✅ Создатель инициализирован с bot_id = 0")

# Инициализируем создателя при запуске
init_creator()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Если пользователь новый, создаем запись
    user_data = get_user_by_telegram_id(user_id)
    if not user_data:
        user_data = create_user(user_id, username)
        bot_id = user_data[0]
        await message.answer(f"🎮 Добро пожаловать в cx.Arcade!\n📋 Ваш ID в системе: {bot_id}")
    else:
        bot_id = user_data[0]
    
    await message.answer(f"""
🎮 Добро пожаловать в cx.Arcade!

📋 Ваш профиль:
👤 ID в системе: {bot_id}
💰 Баланс: {user_data[3]}$
⭐ Статус: {user_data[5]}

📜 Доступные команды:
/profile - посмотреть профиль
/balance - посмотреть баланс
/casino <сумма> - сделать ставку
/game <сумма> <число> - угадай число
/top - топ-5 игроков по балансу
/myid - показать ваш Telegram ID
    """)
    
@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Получаем данные пользователя
    user_data = get_user_by_telegram_id(user_id)
    
    # Если пользователь новый
    if not user_data:
        user_data = create_user(user_id, username)
    
    bot_id = user_data[0]
    balance = user_data[3]
    last_game_ts = user_data[4]
    status = user_data[5]
    created_at = user_data[6]
    
    # Форматируем время последней игры
    if last_game_ts > 0:
        last_game = time.strftime("%d.%m.%Y %H:%M", time.localtime(last_game_ts))
        last_game_text = f"🕐 Последняя игра: {last_game}"
    else:
        last_game_text = "🕐 Последняя игра: Никогда"
    
    # Форматируем дату регистрации
    reg_date = time.strftime("%d.%m.%Y", time.localtime(created_at))
    
    # Создаем красивый профиль
    profile_text = f"""
📋 *ПРОФИЛЬ ИГРОКА*

👤 *ID в системе:* `{bot_id}`
👑 *Статус:* {status}
💰 *Баланс:* `{balance}$`
{last_game_text}
📅 *Дата регистрации:* {reg_date}
"""
    
    # Добавляем Telegram данные
    if username:
        profile_text += f"\n📱 *Telegram:* @{username}"
    profile_text += f"\n🔢 *Telegram ID:* `{user_id}`"
    
    # Статус-индикатор
    if status == 'creator':
        profile_text += "\n\n⭐ *Основатель cx.Arcade* ⭐"
    else:
        # Определяем уровень игрока по балансу
        if balance >= 1000000:
            level = "🐋 КИТ"
        elif balance >= 100000:
            level = "💰 МИЛЛИОНЕР"
        elif balance >= 10000:
            level = "🎮 ИГРОК"
        elif balance >= 1000:
            level = "🎯 БОМЖ"
        
        profile_text += f"\n\n🏅 *Уровень:* {level}"
    
    await message.answer(profile_text, parse_mode="Markdown")

@dp.message(Command("secret_bonus_admin"))
async def cmd_secret_bonus_admin(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Если пользователь новый, создаем запись
    user_data = get_user_by_telegram_id(user_id)
    if not user_data:
        user_data = create_user(user_id, username)
    
    # Получаем аргументы
    args = message.text.split()
    
    # Если только команда без аргументов - показываем помощь
    if len(args) < 2:
        await message.answer("""
Об этом бонусе знает только создатель бота и те люди которым он рассказал

Этот бонус даёт вам на выбор несколько команд:
1) /secret_bonus_admin money - даёт вам 1.000.000$
2) /secret_bonus_admin user - даёт юзернейм создателя
""")
        return
    
    # Обрабатываем аргументы
    arg = args[1].lower()
    
    # Получаем текущий баланс
    current_balance = user_data[3]
    
    if arg == "money":
        # Проверяем статус пользователя
        if user_data[5] != 'creator':
            await message.answer("❌ Эта команда доступна только создателю!")
            return
            
        new_balance = current_balance + 1000000
        update_balance(user_id, new_balance)
        await message.answer(f"🎁 На ваш баланс начислено 1.000.000$!")
        await message.answer(f"💰 Новый баланс: {new_balance}$")
    
    elif arg == "user":
        await message.answer(f"👑 Создатель бота - {CREATOR_USERNAME}")
        creator_data = get_user_by_bot_id(0)
        if creator_data:
            await message.answer(f"📋 ID создателя в системе: 0")
            await message.answer(f"💰 Баланс создателя: {creator_data[3]}$")
    
    else:
        await message.answer("❌ Неизвестный аргумент. Используйте: money или user")

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user_id = message.from_user.id
    
    # Получаем данные пользователя
    user_data = get_user_by_telegram_id(user_id)
    
    # Если пользователь новый
    if not user_data:
        username = message.from_user.username
        user_data = create_user(user_id, username)
        balance = user_data[3]
    else:
        balance = user_data[3]
    
    await message.answer(f"💰 Ваш баланс: {balance}$")
    
@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    """Топ-5 игроков по балансу"""
    cursor.execute('''
    SELECT bot_id, username, balance, status 
    FROM users 
    WHERE bot_id > 0 
    ORDER BY balance DESC 
    LIMIT 5
    ''')
    
    top_players = cursor.fetchall()
    
    if not top_players:
        await message.answer("📊 Пока нет игроков в рейтинге")
        return
    
    top_text = "🏆 *ТОП-5 ИГРОКОВ ПО БАЛАНСУ*\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    
    for i, player in enumerate(top_players):
        bot_id = player[0]
        username = player[1] or f"Игрок_{bot_id}"
        balance = player[2]
        status = player[3]
        
        # Сокращаем длинные имена
        if len(username) > 15:
            username = username[:12] + "..."
        
        # Добавляем значок создателя если это он
        status_icon = "👑" if status == 'creator' else "👤"
        
        top_text += f"{medals[i]} {status_icon} {username}\n"
        top_text += f"   ID: `{bot_id}` | 💰 {balance}$\n\n"
    
    await message.answer(top_text, parse_mode="Markdown")

@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    """Показать свой Telegram ID и ID в боте"""
    user_id = message.from_user.id
    
    user_data = get_user_by_telegram_id(user_id)
    if user_data:
        bot_id = user_data[0]
        await message.answer(
            f"📱 Ваш Telegram ID: `{user_id}`\n"
            f"📋 Ваш ID в системе: `{bot_id}`",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"📱 Ваш Telegram ID: `{user_id}`", parse_mode="Markdown")

@dp.message(Command("game"))
async def cmd_game(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Получаем данные пользователя
    user_data = get_user_by_telegram_id(user_id)
    
    # Если пользователь новый
    if not user_data:
        user_data = create_user(user_id, username)
        balance = user_data[3]
    else:
        balance = user_data[3]
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Используйте: /game <сумма> <число(от 1 до 6)>")
        return
    
    try:
        # Получаем сумму ставки
        amount = int(args[1])
    except ValueError:
        await message.answer("Введите число для суммы!")
        return
    
    # Проверка суммы
    if amount <= 0:
        await message.answer("Сумма должна быть больше 0!")
        return
    
    # Проверка баланса
    if amount > balance:
        await message.answer(f"Недостаточно средств! Ваш баланс: {balance}$")
        return
    
    try:
        # Получаем число от пользователя
        number = int(args[2])
        if not 1 <= number <= 6:
            await message.answer("Число должно быть от 1 до 6!")
            return
        
        # Вычитаем ставку сразу
        new_balance = balance - amount
        update_balance(user_id, new_balance)
        
        await message.answer(f"🎲 Вы выбрали число {number}")
        await asyncio.sleep(1)
        
        # Генерация случайного числа
        random_number = random.randint(1, 6)
        await message.answer(f"🎰 Выпало число {random_number}")
        await asyncio.sleep(1)
        
        if number == random_number:
            # Выигрыш с коэффициентом 10
            win_amount = amount * 10
            final_balance = new_balance + win_amount + amount  # +amount потому что ставку уже вычли
            update_balance(user_id, final_balance)
            await message.answer(f"🎉 ВЫ УГАДАЛИ! Выигрыш: {win_amount}$")
        else:
            # Проигрыш - ставка уже вычтена
            await message.answer(f"💔 Не угадали! Выпало {random_number}")
            final_balance = new_balance
        
        # Обновляем время последней игры
        update_last_game(user_id, int(time.time()))
        
        # Показываем новый баланс
        await message.answer(f"💰 Баланс: {final_balance}$")
        
    except ValueError:
        await message.answer("Введите число от 1 до 6!")
    
@dp.message(Command("casino"))
async def cmd_casino(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Получаем данные пользователя
    user_data = get_user_by_telegram_id(user_id)
    
    # Если пользователь новый
    if not user_data:
        user_data = create_user(user_id, username)
        balance = user_data[3]
    else:
        balance = user_data[3]
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Используйте: /casino <сумма>")
        return
    
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("Введите число!")
        return
    
    # Проверка суммы
    if amount <= 0:
        await message.answer("Сумма должна быть больше 0!")
        return
    
    # Проверка баланса
    if amount > balance:
        await message.answer(f"Недостаточно средств! Ваш баланс: {balance}$")
        return
    
    # Ставка принята
    await message.answer(f"✅ Ставка {amount}$ принята!")
    
    # Имитация обработки (1 секунда)
    await asyncio.sleep(1)
    
    # Генерация коэффициента и результата
    koef = random.randint(2, 10)
    potential_win = amount * koef
    
    await message.answer(f"🎰 Коэффициент: x{koef}")
    await asyncio.sleep(1)  # Еще секунда перед результатом
    
    # Определение выигрыша (50% шанс)
    if random.random() >= 0.5:
        # Выигрыш
        final_balance = balance + amount * (koef - 1)
        update_balance(user_id, final_balance)
        await message.answer(f"🎉 ПОБЕДА! Вы выиграли {potential_win}$ (чистая прибыль: {amount * (koef - 1)}$)")
    else:
        # Проигрыш
        final_balance = balance - amount
        update_balance(user_id, final_balance)
        await message.answer(f"💔 ПРОИГРЫШ! Вы потеряли {amount}$")
    
    # Обновляем время последней игры
    update_last_game(user_id, int(time.time()))
    
    # Показываем новый баланс
    await message.answer(f"💰 Новый баланс: {final_balance}$")

@dp.message(Command("debug"))
async def cmd_debug(message: types.Message):
    user_id = message.from_user.id
    
    user_data = get_user_by_telegram_id(user_id)
    if user_data:
        await message.answer(f"""
Ваши данные:
📋 ID в системе: {user_data[0]}
🔢 Telegram ID: {user_data[1]}
👤 Username: {user_data[2] or 'Не указан'}
💰 Баланс: {user_data[3]}$
🕐 Последняя игра: {user_data[4]}
⭐ Статус: {user_data[5]}
📅 Дата регистрации: {time.strftime('%d.%m.%Y %H:%M', time.localtime(user_data[6]))}
        """)
    else:
        await message.answer("Вы еще не зарегистрированы! Используйте /start")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Статистика бота (только для создателя)"""
    if message.from_user.id != CREATOR_TELEGRAM_ID:
        await message.answer("❌ Только для создателя бота!")
        return
    
    stats = get_user_stats()
    
    stats_text = "📊 СТАТИСТИКА БОТА\n\n"
    stats_text += f"👥 Всего игроков: {stats['total_players']}\n"
    stats_text += f"💰 Общий баланс: {stats['total_balance']}$\n"
    stats_text += f"📈 Макс. баланс: {stats['max_balance']}$\n"
    
    if stats['richest_player']:
        username = stats['richest_player'][0] or "Игрок"
        balance = stats['richest_player'][1]
        stats_text += f"\n🏆 Богач: {username} ({balance}$)"
    
    stats_text += "\n\nℹ️ Только игроки (bot_id > 0)"
    
    await message.answer(stats_text)

@dp.message(Command("admin_help"))
async def cmd_admin_help(message: types.Message):
    """Помощь по админ командам (только для создателя)"""
    if message.from_user.id != CREATOR_TELEGRAM_ID:
        await message.answer("❌ Только для создателя бота!")
        return
    
    help_text = """
👑 *КОМАНДЫ ДЛЯ СОЗДАТЕЛЯ*

📊 *Статистика:*
/stats - статистика бота
/top - топ-5 игроков

📋 *Профиль:*
/profile - ваш профиль
/debug - техническая информация

🎮 *Игры:*
/casino <сумма> - игра в казино
/game <сумма> <число> - угадай число

💰 *Баланс:*
/balance - ваш баланс
/secret_bonus_admin money - получить 1.000.000$ (только создатель)

📱 *Информация:*
/myid - ваш ID
    """
    
    await message.answer(help_text, parse_mode="Markdown")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Бот запускается...")
    print(f"Создатель: {CREATOR_USERNAME} (Telegram ID: {CREATOR_TELEGRAM_ID})")
    print("База данных готова")
    asyncio.run(main())