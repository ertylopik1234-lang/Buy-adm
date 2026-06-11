import requests
import time
import json
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# ========== КОНФИГУРАЦИЯ (ЗАМЕНИТЕ ТОКЕН) ==========
BOT_TOKEN = "8669616261:AAE49hFlnQIgsBIVaDdz__k9gL2wfF_fDcA"  # <--- СЮДА ВСТАВЬТЕ ТОКЕН ОТ @BotFather
ADMIN_ID = 8744429026
YOOMONEY_WALLET = "4100119550918047"
CRYPTOBOT_API_KEY = "594576:AAUhkSu0iId6WyMMLwwP5urmizhRSaD7pOG"
GROUP_ID = -1003841665487
INVITE_LINK = "https://t.me/+S8CmDuNpaLU3NGVi"

last_update_id = 0
pending_payments = {}  # {user_id: {"type": "crypto", "invoice_id": 123, "amount": 3}}

# ========== ВЕБ-СЕРВЕР ДЛЯ ХОСТИНГА ==========
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

# ========== ФУНКЦИИ ==========
def send_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        data["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def send_invite(chat_id):
    send_message(chat_id, f"✅ Доступ открыт! Перейдите по ссылке:\n\n{INVITE_LINK}")

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
        print("CryptoBot ошибка:", result)
        return None, None
    except Exception as e:
        print(f"CryptoBot исключение: {e}")
        return None, None

def check_crypto_invoice(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_API_KEY}
    data = {"invoice_ids": invoice_id}
    try:
        r = requests.post(url, headers=headers, data=data)
        result = r.json()
        if result.get("ok") and result["result"]["items"]:
            status = result["result"]["items"][0].get("status")
            return status == "paid"
        return False
    except Exception as e:
        print(f"Ошибка проверки крипто-счёта: {e}")
        return False

def approve_join_request(user_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/approveChatJoinRequest"
    data = {"chat_id": GROUP_ID, "user_id": user_id}
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"Ошибка принятия заявки: {e}")

# ========== ОСНОВНОЙ ЦИКЛ БОТА ==========
print("✅ Бот запущен")

while True:
    try:
        # Фоновая проверка крипто-платежей
        for user_id, payment in list(pending_payments.items()):
            if payment["type"] == "crypto":
                if check_crypto_invoice(payment["invoice_id"]):
                    send_invite(user_id)
                    approve_join_request(user_id)
                    send_message(ADMIN_ID, f"✅ Пользователь {user_id} оплатил {payment['amount']} USDT (авто)")
                    del pending_payments[user_id]

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id+1}&timeout=10"
        response = requests.get(url).json()
        
        for update in response.get("result", []):
            last_update_id = update["update_id"]
            message = update.get("message", {})
            callback = update.get("callback_query", {})
            
            # Обработка обычных сообщений
            if message:
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "")
                
                if text == "/start":
                    keyboard = [
                        [{"text": "🇷🇺 ЮMoney (250 ₽)", "callback_data": "pay_yoomoney"}],
                        [{"text": "⭐ Telegram Stars (125⭐)", "callback_data": "pay_stars"}],
                        [{"text": "₿ CryptoBot USDT (3 USDT)", "callback_data": "pay_crypto"}]
                    ]
                    send_message(chat_id, "Добро пожаловать!\nВыберите способ оплаты для доступа в закрытый канал:", keyboard)
                
                elif text.startswith("/grant") and chat_id == ADMIN_ID:
                    try:
                        parts = text.split()
                        user_id = int(parts[1])
                        send_invite(user_id)
                        approve_join_request(user_id)
                        send_message(chat_id, f"✅ Доступ выдан пользователю {user_id}")
                    except:
                        send_message(chat_id, "❌ Ошибка. Используйте: /grant user_id")
                
                elif chat_id == ADMIN_ID and text.startswith("/broadcast"):
                    # Рассылка всем пользователям (опционально)
                    msg = text.replace("/broadcast", "").strip()
                    if msg:
                        # Здесь нужна база пользователей, упрощённо — пропускаем
                        send_message(chat_id, "✅ Рассылка запущена (функция требует базы)")
                    else:
                        send_message(chat_id, "❌ Укажите текст рассылки")
            
            # Обработка нажатий на кнопки
            if callback:
                chat_id = callback.get("from", {}).get("id")
                data = callback.get("data")
                callback_id = callback.get("id")
                
                if data == "pay_yoomoney":
                    amount = 250
                    comment = f"Доступ {chat_id}"
                    link = generate_yoomoney_link(amount, comment)
                    keyboard = [
                        [{"text": "💸 Оплатить", "url": link}],
                        [{"text": "📎 Отправить чек", "callback_data": f"check_yoomoney_{chat_id}"}]
                    ]
                    send_message(chat_id, f"Переведите {amount} ₽ на ЮMoney с комментарием:\n`{comment}`\n\nПосле оплаты нажмите «Отправить чек» и пришлите квитанцию.", keyboard)
                
                elif data == "pay_stars":
                    amount = 125
                    link = generate_stars_link(amount)
                    keyboard = [
                        [{"text": "⭐ Оплатить", "url": link}],
                        [{"text": "📎 Отправить скриншот", "callback_data": f"check_stars_{chat_id}"}]
                    ]
                    send_message(chat_id, f"Переведите {amount} Telegram Stars по ссылке.\n\nПосле оплаты нажмите «Отправить скриншот» и пришлите подтверждение.", keyboard)
                
                elif data == "pay_crypto":
                    amount = 3
                    pay_url, invoice_id = create_crypto_invoice(amount)
                    if pay_url:
                        pending_payments[chat_id] = {"type": "crypto", "invoice_id": invoice_id, "amount": amount}
                        keyboard = [[{"text": "💸 Оплатить", "url": pay_url}]]
                        send_message(chat_id, f"Создан счёт на {amount} USDT. После оплаты доступ откроется автоматически.", keyboard)
                    else:
                        send_message(chat_id, "❌ Ошибка создания счёта. Попробуйте позже.")
                
                elif data.startswith("check_yoomoney_"):
                    user_id = int(data.split("_")[2])
                    send_message(ADMIN_ID, f"📎 Пользователь {user_id} отправил чек ЮMoney. Проверьте и выдайте доступ командой:\n/grant {user_id}")
                    send_message(chat_id, "✅ Чек отправлен администратору. После проверки вы получите доступ.")
                
                elif data.startswith("check_stars_"):
                    user_id = int(data.split("_")[2])
                    send_message(ADMIN_ID, f"📸 Пользователь {user_id} отправил скриншот оплаты Stars. Проверьте и выдайте доступ командой:\n/grant {user_id}")
                    send_message(chat_id, "✅ Скриншот отправлен администратору. После проверки вы получите доступ.")
                
                # Ответ на callback (убираем "часики")
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": callback_id})
                except:
                    pass
        
        time.sleep(3)
        
    except Exception as e:
        print(f"Ошибка в основном цикле: {e}")
        time.sleep(5)
