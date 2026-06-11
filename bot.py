import requests
import time
import json
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

# ========== КОНФИГУРАЦИЯ (ЗАМЕНИТЕ ТОКЕН И ССЫЛКУ) ==========
BOT_TOKEN = "8669616261:AAE49hFlnQIgsBIVaDdz__k9gL2wfF_fDcA"  # <--- СЮДА ВСТАВЬТЕ ТОКЕН ОТ @BotFather
ADMIN_ID = 8744429026
YOOMONEY_WALLET = "4100119550918047"
CRYPTOBOT_API_KEY = "594576:AAUhkSu0iId6WyMMLwwP5urmizhRSaD7pOG"
CHANNEL_ID = -1003841665487  # ID канала (где выдаём админку)
TEMPLATES_GROUP_INVITE = "https://t.me/+XXXXXXXXXXX"  # <--- ССЫЛКА НА ГРУППУ С ШАБЛОНАМИ

USERS_FILE = "users.json"

last_update_id = 0
pending_payments = {}

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

users = load_users()

# ========== ВЕБ-СЕРВЕР ДЛЯ РАБОТЫ НА ХОСТИНГЕ ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')

def run_health_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# ========== ФУНКЦИИ БОТА ==========
def send_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        data["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def promote_to_admin(chat_id, user_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/promoteChatMember"
    data = {
        "chat_id": chat_id,
        "user_id": user_id,
        "can_post_messages": True,
        "can_edit_messages": True,
        "can_delete_messages": True,
        "can_invite_users": True,
        "can_pin_messages": True
    }
    try:
        r = requests.post(url, json=data)
        return r.json().get("ok", False)
    except:
        return False

def send_templates_group_link(user_id):
    send_message(user_id, f"✅ Ссылка для вступления в группу с шаблонами:\n{TEMPLATES_GROUP_INVITE}")

def generate_yoomoney_link(amount, comment):
    return f"https://yoomoney.ru/transfer?to={YOOMONEY_WALLET}&amount={amount}&comment={comment}"

def generate_stars_link(amount):
    return f"https://t.me/telegram?start=star{amount}"

def create_crypto_invoice(amount):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_API_KEY}
    data = {"asset": "USDT", "amount": str(amount)}
    try:
        r = requests.post(url, headers=headers, data=data)
        result = r.json()
        if result.get("ok"):
            return result["result"]["pay_url"], result["result"]["invoice_id"]
        return None, None
    except:
        return None, None

def check_crypto_invoice(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_API_KEY}
    data = {"invoice_ids": invoice_id}
    try:
        r = requests.post(url, headers=headers, data=data)
        result = r.json()
        if result.get("ok") and result["result"]["items"]:
            return result["result"]["items"][0].get("status") == "paid"
        return False
    except:
        return False

def grant_access(user_id, duration):
    now = datetime.now()
    if duration == "week":
        expires = (now + timedelta(days=7)).isoformat()
    elif duration == "month":
        expires = (now + timedelta(days=30)).isoformat()
    else:
        expires = None
    users[str(user_id)] = {"expires": expires}
    save_users(users)

    promote_to_admin(CHANNEL_ID, user_id)
    send_templates_group_link(user_id)
    send_message(user_id, f"✅ Вы получили доступ к админке канала на срок: {duration}")

# ========== ОСНОВНОЙ ЦИКЛ ==========
print("✅ Бот запущен")

while True:
    try:
        # Авто-проверка крипто-платежей
        for user_id, payment in list(pending_payments.items()):
            if payment["type"] == "crypto":
                if check_crypto_invoice(payment["invoice_id"]):
                    grant_access(user_id, payment["duration"])
                    send_message(ADMIN_ID, f"✅ Пользователь {user_id} оплатил {payment['amount']} USDT ({payment['duration']})")
                    del pending_payments[user_id]

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id+1}&timeout=10"
        response = requests.get(url).json()
        
        for update in response.get("result", []):
            last_update_id = update["update_id"]
            message = update.get("message", {})
            callback = update.get("callback_query", {})
            
            if message:
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "")
                
                if text == "/start":
                    keyboard = [
                        [{"text": "📅 Выбрать подписку", "callback_data": "choose_duration"}]
                    ]
                    send_message(chat_id, "Добро пожаловать!\nВыберите способ оплаты для доступа к админке и группе с шаблонами:", keyboard)
                
                elif text.startswith("/grant") and chat_id == ADMIN_ID:
                    try:
                        parts = text.split()
                        user_id = int(parts[1])
                        duration = parts[2] if len(parts) > 2 else "forever"
                        if duration not in ["week", "month", "forever"]:
                            duration = "forever"
                        grant_access(user_id, duration)
                        send_message(chat_id, f"✅ Доступ выдан пользователю {user_id} ({duration})")
                    except:
                        send_message(chat_id, "❌ Используйте: /grant user_id [week/month/forever]")
            
            if callback:
                chat_id = callback.get("from", {}).get("id")
                data = callback.get("data")
                callback_id = callback.get("id")
                
                if data == "choose_duration":
                    keyboard = [
                        [{"text": "🗓 Неделя (50⭐ / 1 USDT / 50₽)", "callback_data": "pay_week"}],
                        [{"text": "📅 Месяц (100⭐ / 2 USDT / 150₽)", "callback_data": "pay_month"}],
                        [{"text": "♾ Навсегда (125⭐ / 3 USDT / 250₽)", "callback_data": "pay_forever"}]
                    ]
                    send_message(chat_id, "Выберите срок подписки:", keyboard)
                
                elif data in ["pay_week", "pay_month", "pay_forever"]:
                    duration = data.split("_")[1]
                    if duration == "week":
                        crypto_amount = 1
                        stars_amount = 50
                        yoomoney_amount = 50
                    elif duration == "month":
                        crypto_amount = 2
                        stars_amount = 100
                        yoomoney_amount = 150
                    else:
                        crypto_amount = 3
                        stars_amount = 125
                        yoomoney_amount = 250
                    
                    keyboard = [
                        [{"text": "🇷🇺 ЮMoney", "callback_data": f"pay_yoomoney_{duration}_{yoomoney_amount}"}],
                        [{"text": "⭐ Telegram Stars", "callback_data": f"pay_stars_{duration}_{stars_amount}"}],
                        [{"text": "₿ CryptoBot USDT (авто)", "callback_data": f"pay_crypto_{duration}_{crypto_amount}"}]
                    ]
                    send_message(chat_id, f"Вы выбрали подписку на {duration}. Выберите способ оплаты:", keyboard)
                
                elif data.startswith("pay_yoomoney_"):
                    parts = data.split("_")
                    duration = parts[2]
                    amount = int(parts[3])
                    comment = f"Доступ {duration} {chat_id}"
                    link = generate_yoomoney_link(amount, comment)
                    keyboard = [
                        [{"text": "💸 Оплатить", "url": link}],
                        [{"text": "📎 Отправить чек", "callback_data": f"check_yoomoney_{duration}_{chat_id}"}]
                    ]
                    send_message(chat_id, f"Переведите {amount} ₽ на ЮMoney с комментарием:\n`{comment}`\n\nПосле оплаты нажмите «Отправить чек».", keyboard)
                
                elif data.startswith("pay_stars_"):
                    parts = data.split("_")
                    duration = parts[2]
                    amount = int(parts[3])
                    link = generate_stars_link(amount)
                    keyboard = [
                        [{"text": "⭐ Оплатить", "url": link}],
                        [{"text": "📎 Отправить скриншот", "callback_data": f"check_stars_{duration}_{chat_id}"}]
                    ]
                    send_message(chat_id, f"Переведите {amount} Telegram Stars по ссылке.\n\nПосле оплаты нажмите «Отправить скриншот».", keyboard)
                
                elif data.startswith("pay_crypto_"):
                    parts = data.split("_")
                    duration = parts[2]
                    amount = int(parts[3])
                    pay_url, invoice_id = create_crypto_invoice(amount)
                    if pay_url:
                        pending_payments[chat_id] = {"type": "crypto", "invoice_id": invoice_id, "amount": amount, "duration": duration}
                        keyboard = [[{"text": "💸 Оплатить", "url": pay_url}]]
                        send_message(chat_id, f"Создан счёт на {amount} USDT. После оплаты доступ откроется автоматически.", keyboard)
                    else:
                        send_message(chat_id, "❌ Ошибка создания счёта. Попробуйте позже.")
                
                elif data.startswith("check_yoomoney_"):
                    parts = data.split("_")
                    duration = parts[2]
                    user_id = int(parts[3])
                    send_message(ADMIN_ID, f"📎 Пользователь {user_id} оплатил {duration} через ЮMoney. Проверьте и выдайте доступ:\n/grant {user_id} {duration}")
                    send_message(chat_id, "✅ Чек отправлен администратору. Доступ будет выдан после проверки.")
                
                elif data.startswith("check_stars_"):
                    parts = data.split("_")
                    duration = parts[2]
                    user_id = int(parts[3])
                    send_message(ADMIN_ID, f"📸 Пользователь {user_id} оплатил {duration} через Stars. Проверьте и выдайте доступ:\n/grant {user_id} {duration}")
                    send_message(chat_id, "✅ Скриншот отправлен администратору. Доступ будет выдан после проверки.")
                
                # Ответ на callback
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": callback_id})
                except:
                    pass
        
        time.sleep(3)
        
    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(5)
