import telebot
from telebot import types
import random
import json
import os
import signal
import sys
from datetime import datetime, timedelta
import time

bot = telebot.TeleBot("8673834935:AAH5SMnyzcMKOXFDXU-48rTOwnbGuG9-yU8")
DATA_FILE = "casino_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('balances', {}), data.get('stats', {}), data.get('language', {}), data.get('promo_used', {}), data.get('promo_codes', {})
        except:
            pass
    return {}, {}, {}, {}, {}

def save_data():
    data = {
        'balances': user_balances,
        'stats': user_stats,
        'language': user_language,
        'promo_used': promo_used,
        'promo_codes': promo_codes
    }
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

user_balances, user_stats, user_language, promo_used, promo_codes = load_data()
user_in_game = {}
user_bet = {}
user_game_data = {}
mines_games = {}
blackjack_games = {}
last_game = {}  # Запоминаем последнюю игру пользователя

# ---------- СИСТЕМА ПРОМОКОДОВ ----------
promo_codes = promo_codes or {}
temp_promo_data = {}  # Временные данные для создания промокода

def create_promo_code(code, reward, max_uses):
    """Создает новый промокод"""
    promo_codes[code] = {
        'reward': reward,
        'max_uses': max_uses,
        'used_count': 0,
        'users': []
    }
    save_data()
    return True

def use_promo_code(user_id, code):
    """Активирует промокод"""
    code = code.lower()
    if code not in promo_codes:
        return False, "invalid"
    
    promo = promo_codes[code]
    if promo['used_count'] >= promo['max_uses']:
        return False, "max_uses"
    
    if user_id in promo['users']:
        return False, "already"
    
    # Активируем
    promo['used_count'] += 1
    promo['users'].append(user_id)
    user_balances[user_id] = user_balances.get(user_id, 0) + promo['reward']
    promo_used[user_id] = True
    save_data()
    return True, promo['reward']

# ---------- АДМИН-КОНСОЛЬ ----------
admin_sessions = {}
ADMIN_PASSWORD = "r08082013"
ADMIN_SESSION_TIMEOUT = timedelta(minutes=30)

user_names_cache = {}

user_names_cache = {}

def get_user_name(uid):
    if uid in user_names_cache:
        return user_names_cache[uid]
    try:
        chat = bot.get_chat(uid)
        # Получаем username или имя
        if chat.username:
            name = f"@{chat.username}"
        else:
            name = chat.first_name or str(uid)
    except Exception as e:
        print(f"⚠️ Ошибка получения имени для {uid}: {e}")
        name = str(uid)
    user_names_cache[uid] = name
    return name

def is_admin_authenticated(user_id):
    if user_id not in admin_sessions:
        return False
    if datetime.now() - admin_sessions[user_id] > ADMIN_SESSION_TIMEOUT:
        del admin_sessions[user_id]
        return False
    return True

ADMIN_TEXTS = {
    'menu': "🔐 *Админ-панель*\nВыберите действие:",
    'users_list': "📋 *Список пользователей* (стр. {page}/{total_pages}):",
    'balances_list': "💰 *Балансы пользователей* (стр. {page}/{total_pages}):",
    'promo_list': "🎁 *Промокоды*:",
    'enter_user_id': "✏️ Введите ID пользователя:",
    'enter_new_balance': "💰 Введите новую сумму баланса (целое число):",
    'balance_changed': "✅ Баланс пользователя {user_id} изменён на {new_balance} ⭐",
    'user_not_found': "❌ Пользователь с ID {user_id} не найден",
    'invalid_amount': "❌ Некорректная сумма",
    'stats_header': "📊 *Статистика пользователя {user_id}*",
    'stats_format': "🏆 Побед: {wins}\n💀 Поражений: {losses}\n📈 Винрейт: {winrate:.1f}%",
    'no_stats': "Нет данных",
    'session_expired': "⏰ Сессия админа истекла. Введите /console заново.",
    'access_denied': "🔒 Доступ запрещён. Введите пароль.",
    'enter_password': "🔐 Введите пароль для входа в админ-панель:",
    'wrong_password': "❌ Неверный пароль! Доступ запрещён.",
    'login_success': "✅ Доступ разрешён. Добро пожаловать в админ-панель!",
    'logout': "🚪 Вы вышли из админ-панели.",
    'enter_promo_code': "✏️ Введите название промокода:",
    'enter_promo_reward': "💰 Введите количество звёзд для начисления:",
    'enter_promo_max_uses': "👥 Введите максимальное количество активаций (1-500):",
    'promo_created': "✅ Промокод *{code}* создан!\n🎁 Награда: {reward} ⭐\n👥 Макс. активаций: {max_uses}",
    'promo_activations': "📊 *Активации промокода {code}*:\n🎁 Награда: {reward} ⭐\n👥 Активирован: {used}/{max_uses} раз\n\nСписок активировавших:"
}

def get_admin_text(key, **kwargs):
    text = ADMIN_TEXTS.get(key, key)
    return text.format(**kwargs)

def get_admin_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📋 Список пользователей", callback_data="admin_users_list_0"),
        types.InlineKeyboardButton("💰 Балансы", callback_data="admin_balances_list_0"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats_prompt"),
        types.InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promo_menu"),
        types.InlineKeyboardButton("✏️ Изменить баланс", callback_data="admin_change_balance"),
        types.InlineKeyboardButton("🚪 Выйти", callback_data="admin_logout")
    )
    return markup

def get_admin_promo_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Активации", callback_data="admin_promo_activations"),
        types.InlineKeyboardButton("➕ Создать промокод", callback_data="admin_promo_create"),
        types.InlineKeyboardButton("◀️ В меню", callback_data="admin_back_to_menu")
    )
    return markup

def get_pagination_keyboard(base_callback, page, total_pages):
    markup = types.InlineKeyboardMarkup()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("◀️ Назад", callback_data=f"{base_callback}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton("Вперёд ▶️", callback_data=f"{base_callback}_{page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)
    markup.add(types.InlineKeyboardButton("◀️ В меню", callback_data="admin_back_to_menu"))
    return markup

def get_all_users_sorted():
    users = []
    for uid in user_balances.keys():
        try:
            name = get_user_name(uid)
            users.append((uid, name, user_balances[uid]))
        except Exception as e:
            print(f"⚠️ Ошибка при обработке пользователя {uid}: {e}")
            users.append((uid, str(uid), user_balances[uid]))
    return sorted(users, key=lambda x: x[0])

def get_users_page(page, per_page=5):
    users = get_all_users_sorted()
    total = len(users)
    start = page * per_page
    end = start + per_page
    return users[start:end], total, (total + per_page - 1) // per_page

# ---------- ТЕКСТЫ ИГР (оставляем как было) ----------
TEXTS = {
    'ru': {
        'welcome': "✨ ДОБРО ПОЖАЛОВАТЬ ✨", 'player': "👤 Игрок", 'balance': "💰 Баланс",
        'wins': "🏆 Побед", 'make_bet': "🎲 Сделать ставку!", 'menu': "📋 Меню", 'profile': "👤 Профиль",
        'language': "🌐 Язык", 'back': "◀️ Назад", 'coin': "🪙 Монетка", 'blackjack': "♠️ Блэкджек",
        'slots': "🎰 Слоты", 'basketball': "🏀 Баскетбол", 'football': "⚽ Футбол", 'dice': "🎲 Угадайка", 
        'darts': "🎯 Дартс", 'mines': "💣 Мины", 'choose_side': "🎯 Сделайте выбор:", 'heads': "👑 Орёл", 'tails': "⭐ Решка",
        'enter_bet': "💰 Введите сумму ставки:", 'min_bet': "📉 Минимум: 1 ⭐", 'max_bet': "📈 Максимум:",
        'victory': "🏆 ПОБЕДА! 🎉", 'defeat': "💔 ПОРАЖЕНИЕ 😢", 'flipping': "🔄 ПОДБРАСЫВАЕМ МОНЕТУ...",
        'result': "🎯 РЕЗУЛЬТАТ:", 'you_chose': "✨ Вы выбрали:", 'new_balance': "💎 Новый баланс:",
        'game_started': "🎮 ИГРА НАЧАЛАСЬ!", 'your_turn': "🔥 Ваш ход:", 'points': "очк",
        'game_result': "📊 ИТОГ ИГРЫ", 'bust': "💥 ПЕРЕБОР!", 'you_lose': "😭 ВЫ ПРОИГРАЛИ!",
        'lost': "💸 Потеряно:", 'draw': "🤝 НИЧЬЯ!", 'bet_returned': "💰 Ставка возвращена",
        'stats': "📈 СТАТИСТИКА", 'win_rate': "📊 Винрейт:", 'wins_count': "🏆 Побед:", 'losses': "💀 Поражений:",
        'topup': "💎 ПОПОЛНЕНИЕ", 'enter_amount': "🔢 Введите сумму:", 'min_max': "💎 от 1 до 1000 ⭐",
        'type_number': "✏️ Напишите число:", 'invalid_amount': "⚠️ Некорректная сумма!",
        'error': "❌ Ошибка!", 'payment_success': "✅ ПЛАТЕЖ УСПЕШЕН!", 'thanks': "🙏 Спасибо за пополнение!",
        'language_selected': "🌐 Выберите язык:", 'games': "🎮 Доступные игры", 'place_bet': "🎲 Сделать ставку",
        'main_menu': "🏠 Главное меню", 'in_game': "⏳ Вы сейчас в игре! Завершите текущую игру.",
        'slots_rules': "🎰 *Правила игры Слоты*\n\nЦель — собрать выигрышную комбинацию на барабанах.\n\n• 777 — выигрыш x20\n• Три одинаковых символа — выигрыш x10\n• Остальные комбинации — проигрыш\n\nУдачи! 🍀", 
        'basketball_rules': "🏀 *Баскетбол*\n\n• Гол - 1.8x – выигрыш при попадании мяча\n• Мимо - 1.4x – выигрыш при промахе",
        'football_rules': "⚽ *Футбол*\n\n• Гол - 1.4x – выигрыш при попадании мяча\n• Мимо - 1.8x – выигрыш при промахе",
        'dice_rules': "🎲 *Угадайка*\n\n• Число 1/6 - 5x - выигрыш при выпадении выбранного числа",
        'darts_rules': "🎯 *Дартс*\n\n• Красное - 1.8x\n• Белое - 2.0x\n• Центр - 5x\n• Мимо - 5x",
        'coin_rules': "🪙 *Монетка*\n\n• Орёл - 2x\n• Решка - 2x",
        'blackjack_rules': "♠️ *Блэкджек*\n\nЦель — набрать 21 очко",
        'mines_rules': "💣 *Мины*\n\nОткрывайте ячейки и не попадитесь на мину!",
        'choose_number': "🔢 Выберите число:", 'choose_sector': "🎯 Выберите сектор:",
        'your_cards': "🃏 Ваши карты:", 'dealer_card': "🃂 Карта дилера:", 'hidden': "скрыта",
        'dealer_turn': "🤖 ХОД ДИЛЕРА...", 'your_final_cards': "🎴 Ваши итоговые карты:",
        'dealer_final_cards': "🃟 Итоговые карты дилера:",
        'take_card': "🃏 Взять карту", 'stop': "✋ Остановиться", 'red': "🔴 Красное", 'white': "⚪ Белое",
        'center': "🎯 Центр", 'miss': "❌ Мимо", 'goal': "🏀 Гол!", 'miss_shot': "❌ Мимо!",
        'promo': "🎁 ПРОМОКОД", 'enter_promo': "✏️ Введите промокод:", 'promo_success': "🎉 ПРОМОКОД АКТИВИРОВАН!", 
        'promo_invalid': "❌ Неверный промокод!", 'promo_already': "⚠️ Вы уже активировали промокод!",
        'choose_mines': "💣 Выберите количество мин (3-17):", 'mines_count': "💣 Мин", 'cells_left': "📦 Осталось ячеек",
        'current_multiplier': "📈 Текущий множитель", 'open_cell': "🔓 Открыть ячейку", 'cashout': "💰 Забрать выигрыш",
        'mines_victory': "🎉 ВЫ УСПЕШНО ВЫВЕЛИ ВЫИГРЫШ!", 'mines_defeat': "💥 ВЫ ПОДОРВАЛИСЬ НА МИНЕ!",
        'mines_field': "💣 МИННОЕ ПОЛЕ", 'mode': "Режим", 'bet_type': "Тип ставки", 'stars': "⭐",
        'enter_manually': "Введите сумму вручную", 'make_bet_btn': "Сделать ставку", 'selected': "Выбрано",
        'play_again': "🎮 Играть снова"
    },
    'en': {
        'welcome': "✨ WELCOME TO CASINO ✨", 'player': "👤 Player", 'balance': "💰 Balance",
        'wins': "🏆 Wins", 'make_bet': "🎲 Place a bet!", 'menu': "📋 Menu", 'profile': "👤 Profile",
        'language': "🌐 Language", 'back': "◀️ Back", 'coin': "🪙 Coin", 'blackjack': "♠️ Blackjack",
        'slots': "🎰 Slots", 'basketball': "🏀 Basketball", 'football': "⚽ Football", 'dice': "🎲 Guess", 
        'darts': "🎯 Darts", 'mines': "💣 Mines", 'choose_side': "🎯 Make your choice:", 'heads': "👑 Heads", 'tails': "⭐ Tails",
        'enter_bet': "💰 Enter bet amount:", 'min_bet': "📉 Minimum: 1 ⭐", 'max_bet': "📈 Maximum:",
        'victory': "🏆 VICTORY! 🎉", 'defeat': "💔 DEFEAT 😢", 'flipping': "🔄 FLIPPING COIN...",
        'result': "🎯 RESULT:", 'you_chose': "✨ You chose:", 'new_balance': "💎 New balance:",
        'game_started': "🎮 GAME STARTED!", 'your_turn': "🔥 Your turn:", 'points': "pts",
        'game_result': "📊 GAME RESULT", 'bust': "💥 BUST!", 'you_lose': "😭 YOU LOSE!",
        'lost': "💸 Lost:", 'draw': "🤝 DRAW!", 'bet_returned': "💰 Bet returned",
        'stats': "📈 STATISTICS", 'win_rate': "📊 Win rate:", 'wins_count': "🏆 Wins:", 'losses': "💀 Losses:",
        'topup': "💎 TOP UP", 'enter_amount': "🔢 Enter amount:", 'min_max': "💎 from 1 to 1000 ⭐",
        'type_number': "✏️ Type a number:", 'invalid_amount': "⚠️ Invalid amount!",
        'error': "❌ Error!", 'payment_success': "✅ PAYMENT SUCCESSFUL!", 'thanks': "🙏 Thank you!",
        'language_selected': "🌐 Select language:", 'games': "🎮 Available games", 'place_bet': "🎲 Place a bet",
        'main_menu': "🏠 Main menu", 'in_game': "⏳ You are in a game! Finish your current game.",
        'slots_rules': "🎰 *Slots Rules*\n\n• 777 — win x20\n• Three identical — win x10", 
        'basketball_rules': "🏀 *Basketball*\n\n• Goal - 1.8x\n• Miss - 1.4x",
        'football_rules': "⚽ *Football*\n\n• Goal - 1.4x\n• Miss - 1.8x",
        'dice_rules': "🎲 *Guess*\n\n• Number 1/6 - 5x",
        'darts_rules': "🎯 *Darts*\n\n• Red - 1.8x\n• White - 2.0x\n• Center - 5x\n• Miss - 5x",
        'coin_rules': "🪙 *Coin*\n\n• Heads - 2x\n• Tails - 2x",
        'blackjack_rules': "♠️ *Blackjack*\n\nGoal — get 21 points",
        'mines_rules': "💣 *Mines*\n\nOpen cells without hitting a mine!",
        'choose_number': "🔢 Choose number:", 'choose_sector': "🎯 Choose sector:",
        'your_cards': "🃏 Your cards:", 'dealer_card': "🃂 Dealer card:", 'hidden': "hidden",
        'dealer_turn': "🤖 DEALER'S TURN...", 'your_final_cards': "🎴 Your final cards:",
        'dealer_final_cards': "🃟 Dealer's final cards:",
        'take_card': "🃏 Hit", 'stop': "✋ Stand", 'red': "🔴 Red", 'white': "⚪ White",
        'center': "🎯 Center", 'miss': "❌ Miss", 'goal': "🏀 Goal!", 'miss_shot': "❌ Miss!",
        'promo': "🎁 PROMO CODE", 'enter_promo': "✏️ Enter promo code:", 'promo_success': "🎉 PROMO CODE ACTIVATED!", 
        'promo_invalid': "❌ Invalid promo code!", 'promo_already': "⚠️ You already used a promo code!",
        'choose_mines': "💣 Choose mines count (3-17):", 'mines_count': "💣 Mines", 'cells_left': "📦 Cells left",
        'current_multiplier': "📈 Current multiplier", 'open_cell': "🔓 Open cell", 'cashout': "💰 Cashout",
        'mines_victory': "🎉 YOU SUCCESSFULLY CASHED OUT!", 'mines_defeat': "💥 YOU HIT A MINE!",
        'mines_field': "💣 MINE FIELD", 'mode': "Mode", 'bet_type': "Bet type", 'stars': "⭐",
        'enter_manually': "Enter amount manually", 'make_bet_btn': "Place bet", 'selected': "Selected",
        'play_again': "🎮 Play again"
    }
}

def get_text(user_id, key):
    lang = user_language.get(user_id, 'ru')
    return TEXTS[lang].get(key, TEXTS['ru'][key])

# ---------- ИГРОВЫЕ КЛАССЫ ----------
class BlackjackGame:
    def __init__(self, user_id, bet_amount, player_cards, dealer_cards, message_id):
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.player_cards = player_cards
        self.dealer_cards = dealer_cards
        self.player_score = sum(player_cards)
        self.dealer_score = sum(dealer_cards)
        self.message_id = message_id

class MinesGame:
    MULTIPLIERS = {
        3: [1.01, 1.16, 1.33, 1.55, 1.8, 2.13, 2.51, 3.03, 3.68, 4.52, 5.66, 7.19, 9.36, 12.48, 17.16, 24.51, 36.77, 58.83, 102.99, 205.98, 514.96, 2059.39],
        4: [1.07, 1.28, 1.55, 1.88, 2.33, 2.92, 3.7, 4.75, 6.22, 8.29, 11.31, 15.84, 22.87, 34.32, 53.94, 89.9, 161.8, 323.61, 755.19, 2265.28, 11326.42],
        5: [1.11, 1.41, 1.8, 2.33, 3.07, 4.09, 5.55, 7.69, 10.89, 15.83, 23.77, 36.96, 60.06, 102.99, 188.81, 377.62, 849.57, 2265.28, 7929.08, 47572.49],
        6: [1.18, 1.56, 2.13, 2.92, 4.09, 5.84, 8.54, 12.81, 19.8, 31.68, 52.81, 92.42, 171.66, 343.31, 755.19, 1887.98, 5663.95, 22655.79, 158608.5],
        7: [1.24, 1.75, 2.51, 3.7, 5.55, 8.54, 13.52, 22.13, 37.62, 66.88, 125.41, 250.83, 543.46, 1304.3, 3586.67, 11955.4, 53813.01, 430375.5],
        8: [1.31, 1.97, 3.03, 4.75, 7.69, 12.81, 22.13, 39.83, 75.24, 150.47, 322.49, 752.45, 1956.51, 5870.03, 21521.55, 107607.74, 968295.36],
        9: [1.39, 2.23, 3.68, 6.22, 10.89, 19.8, 37.62, 75.24, 159.91, 365.44, 913.91, 2558.51, 8315.08, 33269.32, 182966.96, 1829664.46],
        10: [1.49, 2.56, 4.52, 8.29, 15.83, 31.68, 66.88, 150.47, 365.44, 974.52, 2923.98, 10233.88, 44348.77, 266082.0, 2926783.26],
        11: [1.59, 2.95, 5.66, 11.31, 23.77, 52.81, 125.41, 322.49, 913.91, 2923.98, 10963.49, 51173.46, 332582.15, 3991406.31],
        12: [1.72, 3.44, 7.19, 15.84, 36.96, 92.42, 250.83, 752.45, 2558.51, 10233.88, 51173.46, 358177.76, 4656731.36],
        13: [1.85, 4.06, 9.36, 22.87, 60.06, 171.66, 543.46, 1956.51, 8315.08, 44348.77, 332582.15, 4656731.5],
        14: [2.03, 4.88, 12.48, 34.32, 102.99, 343.31, 1304.3, 5870.03, 33269.32, 266082.0, 3991406.31],
        15: [2.23, 5.97, 17.16, 53.94, 188.81, 755.19, 3586.67, 21521.55, 182966.96, 2926783.26],
        16: [2.48, 7.46, 24.51, 89.9, 377.62, 1887.98, 11955.4, 107607.74, 1829664.46],
        17: [2.78, 9.58, 36.77, 161.8, 849.57, 5663.95, 53813.01, 968295.36]
    }
    
    def __init__(self, user_id, bet_amount, mines_count):
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.cells = 25
        self.opened_cells = 0
        self.mines = random.sample(range(25), mines_count)
        self.message_id = None
        self.opened_cells_list = []
    
    def get_current_multiplier(self):
        if self.opened_cells >= len(self.MULTIPLIERS.get(self.mines_count, [])):
            return self.MULTIPLIERS.get(self.mines_count, [1])[-1]
        return self.MULTIPLIERS.get(self.mines_count, [1])[self.opened_cells]

# ---------- КЛАВИАТУРЫ ----------
def get_main_menu_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"👤 {get_text(user_id, 'profile')}", callback_data="show_profile"),
        types.InlineKeyboardButton(f"🎁 {get_text(user_id, 'promo')}", callback_data="show_promo")
    )
    markup.add(types.InlineKeyboardButton(f"🎲 {get_text(user_id, 'place_bet')}", callback_data="show_games"))
    markup.add(types.InlineKeyboardButton(f"🌐 {get_text(user_id, 'language')}", callback_data="change_language"))
    return markup

def get_game_result_keyboard(user_id, last_game_name):
    """Клавиатура после игры - кнопка 'Играть снова' и 'Назад'"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    if last_game_name:
        markup.add(types.InlineKeyboardButton(f"🎮 {get_text(user_id, 'play_again')}", callback_data=f"play_again_{last_game_name}"))
    markup.add(types.InlineKeyboardButton(f"◀️ {get_text(user_id, 'back')}", callback_data="back_to_games"))
    return markup

def get_games_menu_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"🪙 {get_text(user_id, 'coin')}", callback_data="game_coin"),
        types.InlineKeyboardButton(f"♠️ {get_text(user_id, 'blackjack')}", callback_data="game_blackjack"),
        types.InlineKeyboardButton(f"🎰 {get_text(user_id, 'slots')}", callback_data="game_slots"),
        types.InlineKeyboardButton(f"🏀 {get_text(user_id, 'basketball')}", callback_data="game_basketball"),
        types.InlineKeyboardButton(f"⚽ {get_text(user_id, 'football')}", callback_data="game_football"),
        types.InlineKeyboardButton(f"🎲 {get_text(user_id, 'dice')}", callback_data="game_dice"),
        types.InlineKeyboardButton(f"🎯 {get_text(user_id, 'darts')}", callback_data="game_darts"),
        types.InlineKeyboardButton(f"💣 {get_text(user_id, 'mines')}", callback_data="game_mines")
    )
    markup.add(types.InlineKeyboardButton(f"◀️ {get_text(user_id, 'back')}", callback_data="back_to_main"))
    return markup

def get_coin_inline_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"👑 {get_text(user_id, 'heads')}", callback_data="coin_heads"),
        types.InlineKeyboardButton(f"⭐ {get_text(user_id, 'tails')}", callback_data="coin_tails")
    )
    return markup

def get_blackjack_inline_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"🎴 {get_text(user_id, 'take_card')}", callback_data="blackjack_hit"),
        types.InlineKeyboardButton(f"✋ {get_text(user_id, 'stop')}", callback_data="blackjack_stand")
    )
    return markup

def get_dice_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [types.InlineKeyboardButton(f"Число {i} - 5x", callback_data=f"dice_{i}") for i in range(1, 7)]
    markup.add(*buttons)
    return markup

def get_darts_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔴 Красное - 1.8x", callback_data="darts_red"),
        types.InlineKeyboardButton("⚪ Белое - 2.0x", callback_data="darts_white"),
        types.InlineKeyboardButton("🎯 Центр - 5x", callback_data="darts_center"),
        types.InlineKeyboardButton("❌ Мимо - 5x", callback_data="darts_miss")
    )
    return markup

def get_mines_count_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = []
    for i in range(3, 18):
        buttons.append(types.InlineKeyboardButton(str(i), callback_data=f"mines_count_{i}"))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton(f"◀️ {get_text(user_id, 'back')}", callback_data="back_to_games"))
    return markup

def get_mines_game_keyboard(game):
    user_id = game.user_id
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = []
    for i in range(25):
        if i in game.opened_cells_list:
            buttons.append(types.InlineKeyboardButton("✅", callback_data=f"mines_cell_{i}_disabled"))
        else:
            buttons.append(types.InlineKeyboardButton("⬜", callback_data=f"mines_cell_{i}"))
    for i in range(0, 25, 5):
        markup.row(*buttons[i:i+5])
    multiplier = game.get_current_multiplier()
    if game.opened_cells > 0:
        markup.add(types.InlineKeyboardButton(f"💰 Забрать выигрыш (x{multiplier:.2f})", callback_data="mines_cashout"))
    else:
        markup.add(types.InlineKeyboardButton(f"⏸️ Забрать выигрыш (после 1 ячейки)", callback_data="mines_cashout_disabled"))
    return markup

def get_mines_info_keyboard(user_id, mines_count, max_multiplier):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(f"💰 {get_text(user_id, 'make_bet_btn')}", callback_data=f"mines_bet_{mines_count}"))
    markup.add(types.InlineKeyboardButton(f"◀️ {get_text(user_id, 'back')}", callback_data="back_to_games"))
    return markup

def get_language_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
    return markup

def get_bet_keyboard(user_id, game_name):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(f"💰 {get_text(user_id, 'make_bet_btn')}", callback_data=f"bet_{game_name}"))
    markup.add(types.InlineKeyboardButton(f"◀️ {get_text(user_id, 'back')}", callback_data="back_to_games"))
    return markup

def get_basketball_keyboard(bet_amount):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🏀 Гол - 1.8x", callback_data=f"basketball_goal_{bet_amount}"),
        types.InlineKeyboardButton("❌ Мимо - 1.4x", callback_data=f"basketball_miss_{bet_amount}")
    )
    return markup

def get_football_keyboard(bet_amount):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⚽ Гол - 1.4x", callback_data=f"football_goal_{bet_amount}"),
        types.InlineKeyboardButton("❌ Мимо - 1.8x", callback_data=f"football_miss_{bet_amount}")
    )
    return markup

def show_game_with_rules(user_id, game_name, rules_key, emoji):
    rules_text = get_text(user_id, rules_key)
    balance = user_balances.get(user_id, 0)
    game_text = f"{emoji} *{get_text(user_id, game_name)}*\n\n{rules_text}\n\n---\n\n💰 *{get_text(user_id, 'balance')}:* {balance} ⭐\n📉 {get_text(user_id, 'min_bet')}\n📈 {get_text(user_id, 'max_bet')} {balance} ⭐"
    bot.send_message(user_id, game_text, parse_mode='Markdown', reply_markup=get_bet_keyboard(user_id, game_name))

def show_mines_count(user_id):
    text = f"💣 *{get_text(user_id, 'mines')}*\n\n{get_text(user_id, 'choose_mines')}\n\n"
    for count in range(3, 18):
        multipliers = MinesGame.MULTIPLIERS.get(count, [])
        max_mult = multipliers[-1] if multipliers else 1
        text += f"• {count} 💣 — макс. x{max_mult:.2f}\n"
    bot.send_message(user_id, text, parse_mode='Markdown', reply_markup=get_mines_count_keyboard(user_id))

def show_main_menu(message_or_call):
    if isinstance(message_or_call, types.CallbackQuery):
        user_id = message_or_call.message.chat.id
        message = message_or_call.message
        try: 
            bot.delete_message(user_id, message.message_id)
        except: 
            pass
    else:
        user_id = message_or_call.chat.id
        message = message_or_call
    username = message.from_user.first_name
    balance = user_balances.get(user_id, 0)
    try:
        with open('welcome.jpg', 'rb') as photo:
            bot.send_photo(user_id, photo, caption=f"🎭 *{get_text(user_id, 'player')}:* {username}\n💰 *{get_text(user_id, 'balance')}:* {balance} ⭐\n\n🚀 {get_text(user_id, 'make_bet')}", parse_mode='Markdown', reply_markup=get_main_menu_keyboard(user_id))
    except:
        bot.send_message(user_id, f"🎭 *{get_text(user_id, 'player')}:* {username}\n💰 *{get_text(user_id, 'balance')}:* {balance} ⭐\n\n🚀 {get_text(user_id, 'make_bet')}", parse_mode='Markdown', reply_markup=get_main_menu_keyboard(user_id))

def show_profile(message_or_call):
    if isinstance(message_or_call, types.CallbackQuery):
        user_id = message_or_call.message.chat.id
        message = message_or_call.message
        try: 
            bot.delete_message(user_id, message.message_id)
        except: 
            pass
    else:
        user_id = message_or_call.chat.id
        message = message_or_call
    balance = user_balances.get(user_id, 0)
    stats = user_stats.get(user_id, {'wins': 0, 'losses': 0})
    total_games = stats['wins'] + stats['losses']
    win_rate = (stats['wins'] / total_games * 100) if total_games > 0 else 0
    profile_text = f"👤 *{get_text(user_id, 'profile')}*\n\n💰 *{get_text(user_id, 'balance')}:* {balance} ⭐\n🏆 *{get_text(user_id, 'wins_count')}:* {stats['wins']}\n💀 *{get_text(user_id, 'losses')}:* {stats['losses']}\n📊 *{get_text(user_id, 'win_rate')}:* {win_rate:.1f}%"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"💎 {get_text(user_id, 'topup')}", callback_data="topup_balance"))
    markup.add(types.InlineKeyboardButton(f"◀️ {get_text(user_id, 'back')}", callback_data="back_to_main"))
    bot.send_message(user_id, profile_text, parse_mode='Markdown', reply_markup=markup)

def show_games_with_animation(user_id):
    bot.send_message(user_id, f"🎮 *{get_text(user_id, 'games')}*", parse_mode='Markdown', reply_markup=get_games_menu_keyboard(user_id))

def show_promo(user_id, message_id):
    try: 
        bot.delete_message(user_id, message_id)
    except: 
        pass
    msg = bot.send_message(user_id, f"🎁 *{get_text(user_id, 'promo')}*\n\n✏️ {get_text(user_id, 'enter_promo')}", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_promo_code)

def process_promo_code(message):
    user_id = message.chat.id
    code = message.text.strip().lower()
    
    if user_id in promo_used and promo_used[user_id]:
        bot.send_message(user_id, f"⚠️ *{get_text(user_id, 'promo_already')}*", parse_mode='Markdown')
        show_main_menu(message)
        return
    
    result, data = use_promo_code(user_id, code)
    
    if result:
        bot.send_message(user_id, f"🎉 *{get_text(user_id, 'promo_success')}*\n\n⭐ +{data} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐", parse_mode='Markdown')
    elif data == "invalid":
        bot.send_message(user_id, f"❌ *{get_text(user_id, 'promo_invalid')}*", parse_mode='Markdown')
    elif data == "already":
        bot.send_message(user_id, f"⚠️ *{get_text(user_id, 'promo_already')}*", parse_mode='Markdown')
    elif data == "max_uses":
        bot.send_message(user_id, f"❌ Промокод больше не активен!", parse_mode='Markdown')
    
    show_main_menu(message)

# ---------- ОСНОВНОЙ ХЕНДЛЕР КОМАНД ----------
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.chat.id
    if user_in_game.get(user_id, False):
        bot.send_message(user_id, f"⚠️ {get_text(user_id, 'in_game')}", parse_mode='Markdown')
        return
    if user_id not in user_balances:
        user_balances[user_id] = 10
        user_stats[user_id] = {'wins': 0, 'losses': 0}
        user_language[user_id] = 'ru'
        if user_id not in promo_used:
            promo_used[user_id] = False
        save_data()
    show_main_menu(message)

@bot.message_handler(commands=["console"])
def admin_console(message):
    user_id = message.chat.id
    if is_admin_authenticated(user_id):
        bot.send_message(user_id, get_admin_text('menu'), parse_mode='Markdown', reply_markup=get_admin_main_keyboard())
    else:
        msg = bot.send_message(user_id, get_admin_text('enter_password'), parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_admin_password)

def process_admin_password(message):
    user_id = message.chat.id
    if message.text.strip() == ADMIN_PASSWORD:
        admin_sessions[user_id] = datetime.now()
        bot.send_message(user_id, get_admin_text('login_success'), parse_mode='Markdown')
        bot.send_message(user_id, get_admin_text('menu'), parse_mode='Markdown', reply_markup=get_admin_main_keyboard())
    else:
        bot.send_message(user_id, get_admin_text('wrong_password'), parse_mode='Markdown')

# ---------- ПЛАТЕЖИ ----------
@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout_query(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    user_id = message.chat.id
    payload = message.successful_payment.invoice_payload
    try:
        _, _, amount = payload.split('_')
        amount = int(amount)
    except:
        bot.send_message(user_id, "❌ Ошибка обработки платежа. Обратитесь к администратору.")
        return
    user_balances[user_id] = user_balances.get(user_id, 0) + amount
    save_data()
    bot.send_message(user_id, 
                     f"✅ *{get_text(user_id, 'payment_success')}*\n\n⭐ +{amount} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐\n\n{get_text(user_id, 'thanks')}",
                     parse_mode='Markdown')
    show_main_menu(message)

# ---------- ОБРАБОТЧИК CALLBACK ----------
@bot.callback_query_handler(func=lambda call: True)
def handle_admin_callbacks(call):
    user_id = call.message.chat.id
    data = call.data
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass

    try:
        if data == "admin_back_to_menu":
            bot.send_message(user_id, get_admin_text('menu'), parse_mode='Markdown', reply_markup=get_admin_main_keyboard())
        elif data == "admin_logout":
            if user_id in admin_sessions:
                del admin_sessions[user_id]
            bot.send_message(user_id, get_admin_text('logout'), parse_mode='Markdown')
        elif data.startswith("admin_users_list_"):
            page = int(data.split("_")[-1])
            users, total, total_pages = get_users_page(page)
            if not users:
                bot.send_message(user_id, "📋 Пользователей нет.")
                bot.send_message(user_id, get_admin_text('menu'), parse_mode='Markdown', reply_markup=get_admin_main_keyboard())
                return
            text = get_admin_text('users_list', page=page+1, total_pages=total_pages) + "\n\n"
            for uid, name, balance in users:
                text += f"• ID: `{uid}` – {name} – {balance} ⭐\n"
            bot.send_message(user_id, text, parse_mode='Markdown', reply_markup=get_pagination_keyboard("admin_users_list", page, total_pages))
        elif data.startswith("admin_balances_list_"):
            page = int(data.split("_")[-1])
            users, total, total_pages = get_users_page(page)
            if not users:
                bot.send_message(user_id, "💰 Балансов нет.")
                bot.send_message(user_id, get_admin_text('menu'), parse_mode='Markdown', reply_markup=get_admin_main_keyboard())
                return
            text = get_admin_text('balances_list', page=page+1, total_pages=total_pages) + "\n\n"
            for uid, name, balance in users:
                text += f"• ID: `{uid}` – {name} – {balance} ⭐\n"
            bot.send_message(user_id, text, parse_mode='Markdown', reply_markup=get_pagination_keyboard("admin_balances_list", page, total_pages))
        elif data == "admin_promo_menu":
            bot.send_message(user_id, get_admin_text('promo_list'), parse_mode='Markdown', reply_markup=get_admin_promo_keyboard())
        elif data == "admin_promo_activations":
            if not promo_codes:
                bot.send_message(user_id, "📊 Нет созданных промокодов", parse_mode='Markdown', reply_markup=get_admin_promo_keyboard())
                return
            text = "📊 *Список промокодов:*\n\n"
            for code, promo in promo_codes.items():
                text += f"• *{code}* - {promo['reward']} ⭐ (активирован {promo['used_count']}/{promo['max_uses']})\n"
                if promo['users']:
                    names = []
                    for uid in promo['users'][:5]:
                        try:
                            names.append(get_user_name(uid))
                        except:
                            names.append(str(uid))
                    text += f"  Активировали: {', '.join(names)}\n"
                    if len(promo['users']) > 5:
                        text += f"  и ещё {len(promo['users']) - 5}...\n"
                text += "\n"
            bot.send_message(user_id, text, parse_mode='Markdown', reply_markup=get_admin_promo_keyboard())
        elif data == "admin_promo_create":
            msg = bot.send_message(user_id, get_admin_text('enter_promo_code'), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_promo_code)
        elif data == "admin_stats_prompt":
            msg = bot.send_message(user_id, get_admin_text('enter_user_id'), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_stats)
        elif data == "admin_change_balance":
            msg = bot.send_message(user_id, get_admin_text('enter_user_id'), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_change_balance_userid)
    except Exception as e:
        print(f"❌ Ошибка в админ-колбэке: {e}")
        bot.send_message(user_id, f"⚠️ Произошла ошибка: {str(e)}", parse_mode='Markdown')
        bot.send_message(user_id, get_admin_text('menu'), parse_mode='Markdown', reply_markup=get_admin_main_keyboard())

def process_admin_change_balance_amount(message, target_id):
    user_id = message.chat.id
    if not is_admin_authenticated(user_id):
        bot.send_message(user_id, get_admin_text('session_expired'))
        return
    try:
        new_balance = int(message.text.strip())
        if new_balance < 0:
            raise ValueError
    except:
        bot.send_message(user_id, get_admin_text('invalid_amount'), parse_mode='Markdown')
        bot.send_message(user_id, get_admin_text('menu'), parse_mode='Markdown', reply_markup=get_admin_main_keyboard())
        return
    user_balances[target_id] = new_balance
    save_data()
    bot.send_message(user_id, get_admin_text('balance_changed', user_id=target_id, new_balance=new_balance), parse_mode='Markdown')
    bot.send_message(user_id, get_admin_text('menu'), parse_mode='Markdown', reply_markup=get_admin_main_keyboard())

# ---------- ОСТАЛЬНЫЕ ИГРОВЫЕ ФУНКЦИИ ----------
def process_topup_amount(message):
    user_id = message.chat.id
    if user_in_game.get(user_id, False):
        bot.send_message(user_id, f"⚠️ {get_text(user_id, 'in_game')}", parse_mode='Markdown')
        show_games_with_animation(user_id)
        return
    try:
        amount = int(message.text)
        if amount < 1 or amount > 1000:
            bot.send_message(user_id, f"⚠️ {get_text(user_id, 'invalid_amount')}", parse_mode='Markdown')
            show_profile(message)
            return
        prices = [types.LabeledPrice(label=f"{amount} Stars", amount=amount)]
        bot.send_invoice(
            user_id,
            title="💎 Пополнение игрового баланса",
            description=f"💰 Вы получаете {amount} ⭐ для игры в казино!",
            invoice_payload=f"topup_{user_id}_{amount}",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="topup_balance",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
    except ValueError:
        bot.send_message(message.chat.id, f"⚠️ {get_text(user_id, 'error')}", parse_mode='Markdown')
        show_profile(message)

def process_bet_amount(message, game):
    user_id = message.chat.id
    try:
        bet_amount = int(message.text)
        if bet_amount <= 0 or bet_amount > user_balances.get(user_id, 0):
            bot.send_message(user_id, f"⚠️ {get_text(user_id, 'invalid_amount')}", parse_mode='Markdown')
            show_games_with_animation(user_id)
            return
        
        # Запоминаем последнюю игру
        last_game[user_id] = game
        
        if game == "coin":
            user_in_game[user_id] = True
            user_bet[user_id] = bet_amount
            bot.send_message(user_id, f"🪙 *{get_text(user_id, 'choose_side')}*", parse_mode='Markdown', reply_markup=get_coin_inline_keyboard(user_id))
        elif game == "blackjack":
            process_bet_blackjack_amount(user_id, bet_amount)
        elif game == "slots":
            process_bet_slots_amount(user_id, bet_amount)
        elif game == "basketball":
            user_in_game[user_id] = True
            user_bet[user_id] = bet_amount
            bot.send_message(user_id, f"🏀 *{get_text(user_id, 'choose_side')}*", parse_mode='Markdown', reply_markup=get_basketball_keyboard(bet_amount))
        elif game == "football":
            user_in_game[user_id] = True
            user_bet[user_id] = bet_amount
            bot.send_message(user_id, f"⚽ *{get_text(user_id, 'choose_side')}*", parse_mode='Markdown', reply_markup=get_football_keyboard(bet_amount))
        elif game == "dice":
            user_in_game[user_id] = True
            user_bet[user_id] = bet_amount
            bot.send_message(user_id, f"🎲 *{get_text(user_id, 'choose_number')}*", parse_mode='Markdown', reply_markup=get_dice_keyboard(user_id))
        elif game == "darts":
            user_in_game[user_id] = True
            user_bet[user_id] = bet_amount
            bot.send_message(user_id, f"🎯 *{get_text(user_id, 'choose_sector')}*", parse_mode='Markdown', reply_markup=get_darts_keyboard(user_id))
    except ValueError:
        bot.send_message(message.chat.id, f"⚠️ {get_text(user_id, 'error')}", parse_mode='Markdown')
        show_games_with_animation(user_id)

def process_bet_blackjack_amount(user_id, bet_amount):
    player_cards = [random.randint(1, 11), random.randint(1, 11)]
    dealer_cards = [random.randint(1, 11), random.randint(1, 11)]
    game = BlackjackGame(user_id, bet_amount, player_cards, dealer_cards, None)
    blackjack_games[user_id] = game
    user_in_game[user_id] = True
    game_text = f"♠️ *{get_text(user_id, 'blackjack')}*\n\n🃏 {get_text(user_id, 'your_cards')} {', '.join(map(str, player_cards))} = {sum(player_cards)} {get_text(user_id, 'points')}\n🃂 {get_text(user_id, 'dealer_card')} {dealer_cards[0]} {get_text(user_id, 'points')} (❓ {get_text(user_id, 'hidden')})\n\n🔥 *{get_text(user_id, 'your_turn')}*"
    sent_msg = bot.send_message(user_id, game_text, parse_mode='Markdown', reply_markup=get_blackjack_inline_keyboard(user_id))
    game.message_id = sent_msg.message_id

def process_bet_slots_amount(user_id, bet_amount):
    user_in_game[user_id] = True
    reel = ['🍒', '🍋', '🍊', '🍉', '🔔', '7️⃣']
    result = [random.choice(reel), random.choice(reel), random.choice(reel)]
    result_text = f"🎰 *{get_text(user_id, 'slots')}*\n\n{' | '.join(result)}\n\n"
    if result[0] == '7️⃣' and result[1] == '7️⃣' and result[2] == '7️⃣':
        win = bet_amount * 20
        user_balances[user_id] += win
        user_stats[user_id]['wins'] += 1
        result_text += f"🏆 *{get_text(user_id, 'victory')}* x20!\n⭐ +{win} ⭐"
    elif result[0] == result[1] == result[2]:
        win = bet_amount * 10
        user_balances[user_id] += win
        user_stats[user_id]['wins'] += 1
        result_text += f"🏆 *{get_text(user_id, 'victory')}* x10!\n⭐ +{win} ⭐"
    else:
        user_balances[user_id] -= bet_amount
        user_stats[user_id]['losses'] += 1
        result_text += f"⚠️ *{get_text(user_id, 'defeat')}*\n⭐ -{bet_amount} ⭐"
    result_text += f"\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
    save_data()
    user_in_game[user_id] = False
    bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, last_game.get(user_id, 'slots')))

def handle_coin_bet(call):
    user_id = call.message.chat.id
    if not user_in_game.get(user_id, False):
        bot.answer_callback_query(call.id, "Сначала сделайте ставку!")
        return
    bet_amount = user_bet.get(user_id, 0)
    if bet_amount == 0:
        bot.answer_callback_query(call.id, "Ошибка: ставка не найдена!")
        return
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    user_choice = call.data.split("_")[1]
    result = random.choice(["heads", "tails"])
    if user_choice == result:
        win_amount = bet_amount * 2
        user_balances[user_id] += win_amount
        user_stats[user_id]['wins'] += 1
        result_side = "Орёл" if result == "heads" else "Решка"
        result_text = f"🪙 *Монетка*\n\n🏆 *{get_text(user_id, 'victory')}*\n\n👑 Выпало: {result_side}\n⭐ Выигрыш: +{win_amount} ⭐"
    else:
        user_balances[user_id] -= bet_amount
        user_stats[user_id]['losses'] += 1
        result_side = "Орёл" if result == "heads" else "Решка"
        result_text = f"🪙 *Монетка*\n\n💔 *{get_text(user_id, 'defeat')}*\n\n👑 Выпало: {result_side}\n⭐ Потеряно: -{bet_amount} ⭐"
    result_text += f"\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
    save_data()
    bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'coin'))
    del user_bet[user_id]
    user_in_game[user_id] = False

def handle_basketball_bet(call):
    user_id = call.message.chat.id
    if not user_in_game.get(user_id, False):
        bot.answer_callback_query(call.id, "Сначала сделайте ставку!")
        return
    bet_amount = user_bet.get(user_id, 0)
    if bet_amount == 0:
        bot.answer_callback_query(call.id, "Ошибка: ставка не найдена!")
        return
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    data = call.data.split("_")
    user_choice = data[1]
    result = random.choice(["goal", "miss"])
    if user_choice == result:
        if result == "goal":
            multiplier = 1.8
            result_text_result = "ГОЛ!"
        else:
            multiplier = 1.4
            result_text_result = "МИМО!"
        win_amount = bet_amount * multiplier
        user_balances[user_id] += win_amount
        user_stats[user_id]['wins'] += 1
        result_text = f"🏀 *Баскетбол*\n\n🏆 *{get_text(user_id, 'victory')}*\n\n🏀 Результат: {result_text_result} (x{multiplier})\n⭐ Выигрыш: +{win_amount:.1f} ⭐"
    else:
        if result == "goal":
            result_text_result = "ГОЛ!"
        else:
            result_text_result = "МИМО!"
        user_balances[user_id] -= bet_amount
        user_stats[user_id]['losses'] += 1
        result_text = f"🏀 *Баскетбол*\n\n💔 *{get_text(user_id, 'defeat')}*\n\n🏀 Результат: {result_text_result}\n⭐ Потеряно: -{bet_amount} ⭐"
    result_text += f"\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]:.1f} ⭐"
    save_data()
    bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'basketball'))
    del user_bet[user_id]
    user_in_game[user_id] = False

def handle_football_bet(call):
    user_id = call.message.chat.id
    if not user_in_game.get(user_id, False):
        bot.answer_callback_query(call.id, "Сначала сделайте ставку!")
        return
    bet_amount = user_bet.get(user_id, 0)
    if bet_amount == 0:
        bot.answer_callback_query(call.id, "Ошибка: ставка не найдена!")
        return
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    data = call.data.split("_")
    user_choice = data[1]
    result = random.choice(["goal", "miss"])
    if user_choice == result:
        if result == "goal":
            multiplier = 1.4
            result_text_result = "ГОЛ!"
        else:
            multiplier = 1.8
            result_text_result = "МИМО!"
        win_amount = bet_amount * multiplier
        user_balances[user_id] += win_amount
        user_stats[user_id]['wins'] += 1
        result_text = f"⚽ *Футбол*\n\n🏆 *{get_text(user_id, 'victory')}*\n\n⚽ Результат: {result_text_result} (x{multiplier})\n⭐ Выигрыш: +{win_amount:.1f} ⭐"
    else:
        if result == "goal":
            result_text_result = "ГОЛ!"
        else:
            result_text_result = "МИМО!"
        user_balances[user_id] -= bet_amount
        user_stats[user_id]['losses'] += 1
        result_text = f"⚽ *Футбол*\n\n💔 *{get_text(user_id, 'defeat')}*\n\n⚽ Результат: {result_text_result}\n⭐ Потеряно: -{bet_amount} ⭐"
    result_text += f"\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]:.1f} ⭐"
    save_data()
    bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'football'))
    del user_bet[user_id]
    user_in_game[user_id] = False

def handle_dice_bet(call):
    user_id = call.message.chat.id
    if not user_in_game.get(user_id, False):
        bot.answer_callback_query(call.id, "Сначала сделайте ставку!")
        return
    bet_amount = user_bet.get(user_id, 0)
    if bet_amount == 0:
        bot.answer_callback_query(call.id, "Ошибка: ставка не найдена!")
        return
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    user_number = int(call.data.split("_")[1])
    result = random.randint(1, 6)
    if user_number == result:
        win_amount = bet_amount * 5
        user_balances[user_id] += win_amount
        user_stats[user_id]['wins'] += 1
        result_text = f"🎲 *Угадайка*\n\n🏆 *{get_text(user_id, 'victory')}*\n\n🎲 Выпало: {result}\n⭐ Выигрыш: +{win_amount} ⭐"
    else:
        user_balances[user_id] -= bet_amount
        user_stats[user_id]['losses'] += 1
        result_text = f"🎲 *Угадайка*\n\n💔 *{get_text(user_id, 'defeat')}*\n\n🎲 Выпало: {result}\n⭐ Потеряно: -{bet_amount} ⭐"
    result_text += f"\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
    save_data()
    bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'dice'))
    del user_bet[user_id]
    user_in_game[user_id] = False

def handle_darts_bet(call):
    user_id = call.message.chat.id
    if not user_in_game.get(user_id, False):
        bot.answer_callback_query(call.id, "Сначала сделайте ставку!")
        return
    bet_amount = user_bet.get(user_id, 0)
    if bet_amount == 0:
        bot.answer_callback_query(call.id, "Ошибка: ставка не найдена!")
        return
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    user_sector = call.data.split("_")[1]
    sectors = ["red", "white", "center", "miss"]
    weights = [0.4, 0.3, 0.2, 0.1]
    result = random.choices(sectors, weights=weights)[0]
    multipliers = {"red": 1.8, "white": 2.0, "center": 5, "miss": 5}
    sector_names = {"red": "🔴 Красное", "white": "⚪ Белое", "center": "🎯 Центр", "miss": "❌ Мимо"}
    if user_sector == result:
        win_amount = bet_amount * multipliers[result]
        user_balances[user_id] += win_amount
        user_stats[user_id]['wins'] += 1
        result_text = f"🎯 *Дартс*\n\n🏆 *{get_text(user_id, 'victory')}*\n\n🎯 Попадание: {sector_names[result]} x{multipliers[result]}!\n⭐ Выигрыш: +{win_amount:.1f} ⭐"
    else:
        user_balances[user_id] -= bet_amount
        user_stats[user_id]['losses'] += 1
        result_text = f"🎯 *Дартс*\n\n💔 *{get_text(user_id, 'defeat')}*\n\n🎯 Выпало: {sector_names[result]}\n⭐ Потеряно: -{bet_amount} ⭐"
    result_text += f"\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]:.1f} ⭐"
    save_data()
    bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'darts'))
    del user_bet[user_id]
    user_in_game[user_id] = False

def process_bet_mines(message, mines_count):
    user_id = message.chat.id
    try:
        bet_amount = int(message.text)
        if bet_amount <= 0 or bet_amount > user_balances.get(user_id, 0):
            bot.send_message(user_id, f"⚠️ {get_text(user_id, 'invalid_amount')}", parse_mode='Markdown')
            show_games_with_animation(user_id)
            return
        user_in_game[user_id] = True
        last_game[user_id] = 'mines'
        game = MinesGame(user_id, bet_amount, mines_count)
        mines_games[user_id] = game
        multiplier = game.get_current_multiplier()
        multipliers = MinesGame.MULTIPLIERS.get(mines_count, [])
        multipliers_preview = " → ".join([f"x{m:.2f}" for m in multipliers[:8]])
        if len(multipliers) > 8:
            multipliers_preview += " → ..."
        game_text = f"💣 *{get_text(user_id, 'mines')}*\n\n📊 {get_text(user_id, 'selected')}: {mines_count} 💣\n💰 Ставка: {bet_amount} ⭐\n📈 {get_text(user_id, 'current_multiplier')}: x{multiplier:.2f}\n📦 {get_text(user_id, 'cells_left')}: {25}\n\n📈 *Множители:*\n{multipliers_preview}\n\n🎯 {get_text(user_id, 'mines_field')}:"
        sent_msg = bot.send_message(user_id, game_text, parse_mode='Markdown', reply_markup=get_mines_game_keyboard(game))
        game.message_id = sent_msg.message_id
    except ValueError:
        bot.send_message(message.chat.id, f"⚠️ {get_text(user_id, 'error')}", parse_mode='Markdown')
        show_games_with_animation(user_id)

def handle_mines_cell(call):
    user_id = call.message.chat.id
    game = mines_games.get(user_id)
    if not game:
        bot.answer_callback_query(call.id, "Игра не найдена")
        return
    cell = int(call.data.split("_")[2])
    if cell in game.opened_cells_list:
        bot.answer_callback_query(call.id, "Эта ячейка уже открыта!")
        return
    if cell in game.mines:
        user_balances[user_id] -= game.bet_amount
        user_stats[user_id]['losses'] += 1
        save_data()
        result_text = f"💥 *{get_text(user_id, 'mines_defeat')}*\n\n💣 Вы попали на мину!\n⭐ Потеряно: {game.bet_amount} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
        bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'mines'))
        del mines_games[user_id]
        user_in_game[user_id] = False
        return
    game.opened_cells += 1
    game.opened_cells_list.append(cell)
    multiplier = game.get_current_multiplier()
    multipliers = MinesGame.MULTIPLIERS.get(game.mines_count, [])
    multipliers_preview = " → ".join([f"x{m:.2f}" for m in multipliers[:8]])
    if len(multipliers) > 8:
        multipliers_preview += " → ..."
    game_text = f"💣 *{get_text(user_id, 'mines')}*\n\n📊 {get_text(user_id, 'selected')}: {game.mines_count} 💣\n💰 Ставка: {game.bet_amount} ⭐\n📈 {get_text(user_id, 'current_multiplier')}: x{multiplier:.2f}\n📦 {get_text(user_id, 'cells_left')}: {25 - game.opened_cells}\n\n📈 *Множители:*\n{multipliers_preview}\n\n🎯 {get_text(user_id, 'mines_field')}:"
    try:
        bot.edit_message_text(game_text, user_id, game.message_id, parse_mode='Markdown', reply_markup=get_mines_game_keyboard(game))
    except:
        pass

def handle_mines_cashout(call):
    user_id = call.message.chat.id
    game = mines_games.get(user_id)
    if not game:
        bot.answer_callback_query(call.id, "Игра не найдена")
        return
    if game.opened_cells == 0:
        bot.answer_callback_query(call.id, "💰 Вы можете вывести выигрыш после открытия хотя бы одной ячейки!", show_alert=True)
        return
    multiplier = game.get_current_multiplier()
    win_amount = game.bet_amount * multiplier
    user_balances[user_id] += win_amount
    user_stats[user_id]['wins'] += 1
    save_data()
    result_text = f"🎉 *{get_text(user_id, 'mines_victory')}*\n\n📈 Множитель: x{multiplier:.2f}\n⭐ Выигрыш: +{win_amount - game.bet_amount:.2f} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]:.2f} ⭐"
    try:
        bot.edit_message_text(result_text, user_id, game.message_id, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'mines'))
    except:
        bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'mines'))
    del mines_games[user_id]
    user_in_game[user_id] = False

def blackjack_hit(call):
    user_id = call.message.chat.id
    game = blackjack_games.get(user_id)
    if not game:
        return
    new_card = random.randint(1, 11)
    game.player_cards.append(new_card)
    game.player_score = sum(game.player_cards)
    game_text = f"♠️ *{get_text(user_id, 'blackjack')}*\n\n🃏 {get_text(user_id, 'your_cards')} {', '.join(map(str, game.player_cards))} = {game.player_score} {get_text(user_id, 'points')}\n🃂 {get_text(user_id, 'dealer_card')} {game.dealer_cards[0]} {get_text(user_id, 'points')} (❓ {get_text(user_id, 'hidden')})\n\n🔥 *{get_text(user_id, 'your_turn')}*"
    try: 
        bot.edit_message_text(game_text, user_id, game.message_id, parse_mode='Markdown', reply_markup=get_blackjack_inline_keyboard(user_id))
    except: 
        pass
    if game.player_score > 21:
        try: 
            bot.edit_message_reply_markup(user_id, game.message_id, reply_markup=None)
        except: 
            pass
        bot.send_message(user_id, f"🃂 *{get_text(user_id, 'dealer_turn')}*", parse_mode='Markdown')
        game.dealer_score = sum(game.dealer_cards)
        while game.dealer_score < 17:
            new_card = random.randint(1, 11)
            game.dealer_cards.append(new_card)
            game.dealer_score = sum(game.dealer_cards)
        result_text = f"♠️ *{get_text(user_id, 'game_result')}*\n\n🃏 {get_text(user_id, 'your_final_cards')} {', '.join(map(str, game.player_cards))} = {game.player_score} {get_text(user_id, 'points')}\n🃂 {get_text(user_id, 'dealer_final_cards')} {', '.join(map(str, game.dealer_cards))} = {game.dealer_score} {get_text(user_id, 'points')}\n\n"
        if game.player_score > 21 and game.dealer_score > 21:
            result_text += f"🤝 *{get_text(user_id, 'draw')}*\n{get_text(user_id, 'bet_returned')}\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
        elif game.player_score > 21:
            user_balances[user_id] -= game.bet_amount
            user_stats[user_id]['losses'] += 1
            result_text += f"❌ *{get_text(user_id, 'you_lose')}*\n💸 {get_text(user_id, 'lost')} -{game.bet_amount} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
        elif game.dealer_score > 21 or game.player_score > game.dealer_score:
            user_balances[user_id] += game.bet_amount
            user_stats[user_id]['wins'] += 1
            result_text += f"🏆 *{get_text(user_id, 'victory')}*\n⭐ +{game.bet_amount} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
        elif game.player_score < game.dealer_score:
            user_balances[user_id] -= game.bet_amount
            user_stats[user_id]['losses'] += 1
            result_text += f"❌ *{get_text(user_id, 'you_lose')}*\n💸 {get_text(user_id, 'lost')} -{game.bet_amount} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
        else:
            result_text += f"🤝 *{get_text(user_id, 'draw')}*\n{get_text(user_id, 'bet_returned')}\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
        save_data()
        bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'blackjack'))
        del blackjack_games[user_id]
        user_in_game[user_id] = False

def blackjack_stand(call):
    user_id = call.message.chat.id
    game = blackjack_games.get(user_id)
    if not game:
        return
    try: 
        bot.edit_message_reply_markup(user_id, game.message_id, reply_markup=None)
    except: 
        pass
    bot.send_message(user_id, f"🃂 *{get_text(user_id, 'dealer_turn')}*", parse_mode='Markdown')
    game.dealer_score = sum(game.dealer_cards)
    while game.dealer_score < 17:
        new_card = random.randint(1, 11)
        game.dealer_cards.append(new_card)
        game.dealer_score = sum(game.dealer_cards)
    result_text = f"♠️ *{get_text(user_id, 'game_result')}*\n\n🃏 {get_text(user_id, 'your_final_cards')} {', '.join(map(str, game.player_cards))} = {game.player_score} {get_text(user_id, 'points')}\n🃂 {get_text(user_id, 'dealer_final_cards')} {', '.join(map(str, game.dealer_cards))} = {game.dealer_score} {get_text(user_id, 'points')}\n\n"
    if game.player_score > 21 and game.dealer_score > 21:
        result_text += f"🤝 *{get_text(user_id, 'draw')}*\n{get_text(user_id, 'bet_returned')}\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
    elif game.player_score > 21:
        user_balances[user_id] -= game.bet_amount
        user_stats[user_id]['losses'] += 1
        result_text += f"❌ *{get_text(user_id, 'you_lose')}*\n💸 {get_text(user_id, 'lost')} -{game.bet_amount} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
    elif game.dealer_score > 21 or game.player_score > game.dealer_score:
        user_balances[user_id] += game.bet_amount
        user_stats[user_id]['wins'] += 1
        result_text += f"🏆 *{get_text(user_id, 'victory')}*\n⭐ +{game.bet_amount} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
    elif game.player_score < game.dealer_score:
        user_balances[user_id] -= game.bet_amount
        user_stats[user_id]['losses'] += 1
        result_text += f"❌ *{get_text(user_id, 'you_lose')}*\n💸 {get_text(user_id, 'lost')} -{game.bet_amount} ⭐\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
    else:
        result_text += f"🤝 *{get_text(user_id, 'draw')}*\n{get_text(user_id, 'bet_returned')}\n💰 {get_text(user_id, 'new_balance')} {user_balances[user_id]} ⭐"
    save_data()
    bot.send_message(user_id, result_text, parse_mode='Markdown', reply_markup=get_game_result_keyboard(user_id, 'blackjack'))
    del blackjack_games[user_id]
    user_in_game[user_id] = False

# ---------- АВТОПЕРЕЗАПУСК С ОЧИСТКОЙ КОНФЛИКТОВ ----------
def run_bot():
    """Запуск бота с обработкой ошибок и авто-перезапуском"""
    while True:
        try:
            print("🚀 Бот запущен и готов к работе! (админ-консоль активна, платежи исправлены)")
            # Используем обычный polling вместо infinity_polling для лучшего контроля
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ Ошибка: {error_msg}")
            
            # Если ошибка 409 (конфликт), ждём дольше
            if "409" in error_msg or "Conflict" in error_msg:
                print("🔄 Обнаружен конфликт экземпляров. Ожидание 10 секунд...")
                time.sleep(10)
            else:
                print("🔄 Перезапуск через 5 секунд...")
                time.sleep(5)

# ---------- ЗАПУСК БОТА ----------
if __name__ == "__main__":
    run_bot() 