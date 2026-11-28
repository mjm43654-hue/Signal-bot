import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime

# ==============================================================================
# Telegram Settings (تنظیمات تلگرام و ادمین)
# ==============================================================================
TELEGRAM_BOT_TOKEN = "9129289513:AAEYueiZOQOlmZ07iHP1mC5db0tKRPy-7o4"
ADMIN_CHAT_ID = 1991886913  # شناسه محمود (مدیر اصلی)

# اعضای دائم و اولیه
DEFAULT_APPROVED_IDS = [1991886913, 234659465, 100238424]

SUBSCRIBERS_FILE = "subscribers.json"
PENDING_FILE = "pending_users.json"
SENT_SIGNALS_FILE = "sent_signals.json"
PROCESSED_UPDATES_FILE = ".processed_updates.json"

# ==============================================================================
# مدیریت فایل‌ها و دیتابیس
# ==============================================================================
def load_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_val

def save_json(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {filepath}: {e}")

def get_approved_users():
    saved = load_json(SUBSCRIBERS_FILE, [])
    return set(DEFAULT_APPROVED_IDS) | set(saved)

def get_pending_users():
    return set(load_json(PENDING_FILE, []))

# ==============================================================================
# ارسال پیام و دکمه‌های تلگرام (Telegram API Helpers)
# ==============================================================================
def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")
        return None

def edit_telegram_message(chat_id, message_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Error editing message {message_id}: {e}")
        return None

def answer_callback(callback_query_id, text=None, alert=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = alert
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return None

# ==============================================================================
# کیبوردهای شیشه‌ای و کیبوردهای ثابت پایین صفحه (Persistent Keyboards)
# ==============================================================================
def get_main_menu_keyboard(is_admin=False):
    buttons = [
        [
            {"text": "📊 آخرین وضعیت بازار و سیگنال‌ها", "callback_data": "menu_signals"},
            {"text": "📈 راهنمای استراتژی گن", "callback_data": "menu_strategy"}
        ],
        [
            {"text": "🔔 وضعیت اشتراک من", "callback_data": "menu_status"},
            {"text": "💎 درخواست عضویت VIP", "callback_data": "menu_req_vip"}
        ]
    ]
    if is_admin:
        buttons.append([
            {"text": "🛡 پنل مدیریت ادمین", "callback_data": "menu_admin_panel"}
        ])
    return {"inline_keyboard": buttons}

def get_reply_keyboard(is_admin=False):
    keyboard = [
        [{"text": "📊 آخرین وضعیت بازار و سیگنال‌ها"}, {"text": "📈 راهنمای استراتژی گن"}],
        [{"text": "🔔 وضعیت اشتراک من"}, {"text": "💎 درخواست عضویت VIP"}]
    ]
    if is_admin:
        keyboard.append([{"text": "🛡 پنل مدیریت ادمین"}])
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "persistent": True
    }

def get_admin_panel_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "👥 لیست کاربران تاییدشده", "callback_data": "admin_list_users"},
                {"text": "⏳ صف انتظار تایید", "callback_data": "admin_list_pending"}
            ],
            [
                {"text": "⚡️ اسکن دستی فوری بازار", "callback_data": "admin_scan_now"},
                {"text": "🔙 بازگشت به منو", "callback_data": "menu_back_main"}
            ]
        ]
    }

def get_admin_verify_keyboard(user_id):
    return {
        "inline_keyboard": [
            [
                {"text": "✅ تایید و فعال‌سازی اشتراک", "callback_data": f"approve:{user_id}"},
                {"text": "❌ رد درخواست", "callback_data": f"reject:{user_id}"}
            ]
        ]
    }

def get_back_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "menu_back_main"}]
        ]
    }

# ==============================================================================
# نمادها و استراتژی معاملاتی (Gann + Ichimoku v6.18)
# ==============================================================================
SYMBOLS = [
    {"priority": 1, "name": "سولانا (SOL)", "symbol": "SOL-USDT", "desc": "مومنتوم ۲ سال اخیر"},
    {"priority": 2, "name": "بیت‌کوین (BTC)", "symbol": "BTC-USDT", "desc": "رهبر بازار کریپتو"},
    {"priority": 3, "name": "دوج‌کوین (DOGE)", "symbol": "DOGE-USDT", "desc": "جهش‌های شارپ صعودی"},
    {"priority": 4, "name": "انس طلای جهانی (Gold)", "symbol": "PAXG-USDT", "desc": "پایداری و رکورد تاریخی"},
    {"priority": 5, "name": "بایننس کوین (BNB)", "symbol": "BNB-USDT", "desc": "سودآوری اکوسیستم بایننس"},
    {"priority": 6, "name": "اتریوم (ETH)", "symbol": "ETH-USDT", "desc": "دومین دارایی برتر"},
    {"priority": 7, "name": "ریپل (XRP)", "symbol": "XRP-USDT", "desc": "حجم بالای شکست‌های تکنیکال"},
    {"priority": 8, "name": "کاردانو (ADA)", "symbol": "ADA-USDT", "desc": "روند حرکتی بلندمدت"}
]

TIMEFRAME = "4hour"
LOOKBACK_CANDLES = 4

def fetch_candles(symbol: str):
    url = f"https://api.kucoin.com/api/v1/market/candles?type={TIMEFRAME}&symbol={symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read().decode())
            data = raw.get("data", [])
            data.reverse()
            candles = []
            for c in data:
                candles.append({
                    "time": int(c[0]),
                    "open": float(c[1]),
                    "close": float(c[2]),
                    "high": float(c[3]),
                    "low": float(c[4]),
                    "volume": float(c[5])
                })
            return candles
    except Exception as e:
        return []

def calc_atr(candles, length=14):
    if len(candles) < length + 1:
        return [0.0] * len(candles)
    tr_list = []
    for i in range(len(candles)):
        if i == 0:
            tr = candles[i]["high"] - candles[i]["low"]
        else:
            h = candles[i]["high"]
            l = candles[i]["low"]
            prev_c = candles[i-1]["close"]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        tr_list.append(tr)
    atr = [0.0] * len(candles)
    atr[length-1] = sum(tr_list[:length]) / length
    for i in range(length, len(candles)):
        atr[i] = (atr[i-1] * (length - 1) + tr_list[i]) / length
    return atr

def calc_rsi(closes, length=7):
    if len(closes) < length + 1:
        return [50.0] * len(closes)
    gains = [0.0] * len(closes)
    losses = [0.0] * len(closes)
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff >= 0:
            gains[i] = diff
        else:
            losses[i] = -diff
    avg_gain = sum(gains[1:length+1]) / length
    avg_loss = sum(losses[1:length+1]) / length
    rsi = [50.0] * len(closes)
    if avg_loss == 0:
        rsi[length] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[length] = 100.0 - (100.0 / (1.0 + rs))
    for i in range(length + 1, len(closes)):
        avg_gain = (avg_gain * (length - 1) + gains[i]) / length
        avg_loss = (avg_loss * (length - 1) + losses[i]) / length
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def evaluate_gann_ichimoku_4h(candles):
    if len(candles) < 60:
        return None
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    def donchian(start, end): return (max(highs[start:end+1]) + min(lows[start:end+1])) / 2.0
    curr = len(candles) - 1
    prev = curr - 1
    tenkan_curr = donchian(curr - 6, curr)
    tenkan_prev = donchian(prev - 6, prev)
    kijun_curr = donchian(curr - 21, curr)
    kijun_prev = donchian(prev - 21, prev)
    spanA = (tenkan_curr + kijun_curr) / 2.0
    spanB = donchian(curr - 43, curr)
    cloud_top = max(spanA, spanB)
    cloud_bot = min(spanA, spanB)
    atr = calc_atr(candles, 14)[curr]
    rsi = calc_rsi(closes, 7)[curr]
    current_price = closes[curr]
    candle_time = candles[curr]["time"]
    tk_cross_up = (tenkan_prev <= kijun_prev) and (tenkan_curr > kijun_curr)
    tk_cross_down = (tenkan_prev >= kijun_prev) and (tenkan_curr < kijun_curr)
    stop_dist = max(atr * 1.5, current_price * 0.01)
    tp_dist = max(atr * 3.5, stop_dist * 1.6)
    signal = None
    if tk_cross_up and current_price >= cloud_bot and (42 <= rsi <= 75):
        signal = {
            "type": "BUY",
            "action": "🟢 *سیگنال خرید ۴ ساعته (BUY / LONG)*",
            "price": current_price,
            "sl": current_price - stop_dist,
            "tp1": current_price + (tp_dist * 0.5),
            "tp2": current_price + tp_dist,
            "rsi": round(rsi, 1),
            "cloud": "بالای ابر کومو ☁️" if current_price > cloud_top else "درون ابر کومو",
            "rr": round(tp_dist / stop_dist, 2),
            "candle_time": candle_time
        }
    elif tk_cross_down and current_price <= cloud_top and (25 <= rsi <= 58):
        signal = {
            "type": "SELL",
            "action": "🔴 *سیگنال فروش ۴ ساعته (SELL / SHORT)*",
            "price": current_price,
            "sl": current_price + stop_dist,
            "tp1": current_price - (tp_dist * 0.5),
            "tp2": current_price - tp_dist,
            "rsi": round(rsi, 1),
            "cloud": "زیر ابر کومو ☁️" if current_price < cloud_bot else "درون ابر کومو",
            "rr": round(tp_dist / stop_dist, 2),
            "candle_time": candle_time
        }
    return signal, current_price, rsi, (tenkan_curr, kijun_curr)

def get_market_summary_text():
    lines = ["📊 *وضعیت زنده ۸ دارایی برتر (تایم‌فریم ۴ ساعته):*\n"]
    for item in SYMBOLS:
        symbol = item["symbol"]
        name = item["name"]
        candles = fetch_candles(symbol)
        if not candles or len(candles) < 60:
            lines.append(f"• *{name}:* در حال دریافت اطلاعات...")
            continue
        curr = len(candles) - 1
        price = candles[curr]["close"]
        rsi = calc_rsi([c["close"] for c in candles], 7)[curr]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        def donchian(start, end): return (max(highs[start:end+1]) + min(lows[start:end+1])) / 2.0
        tenkan = donchian(curr - 6, curr)
        kijun = donchian(curr - 21, curr)
        trend = "صعودی 🟢" if tenkan > kijun else "نزولی 🔴"
        lines.append(f"• *{name}:* `{price}` | روند: {trend} | RSI: `{round(rsi, 1)}`")
    lines.append("\n⚡️ _استراتژی هوشمند Gann + Ichimoku v6.18_")
    return "\n".join(lines)

def get_strategy_info_text():
    return (
        "📈 *استراتژی Gann + Ichimoku [v6.18 MarginSafe 2%]*\n\n"
        "این سیستم معاملاتی بر پایه هندسه گن و ابر تعادل ژاپنی ایچیموکو طراحی شده است:\n\n"
        "🔹 *تایم‌فریم معاملاتی:* ۴ ساعته (4H)\n"
        "🔹 *تنظیمات ایچیموکو:* تنکان‌سن ۷، کیجون‌سن ۲۲، سنکو بی ۴۴\n"
        "🔹 *فیلتر ابر کومو:* ورود خرید فقط بالای کف ابر، ورود فروش فقط زیر سقف ابر\n"
        "🔹 *فیلتر مومنتوم RSI (دوره‌ ۷):* خرید بین ۴۲ تا ۷۵ | فروش بین ۲۵ تا ۵۸\n"
        "🔹 *مدیریت ریسک هوشمند:* حد ضرر پویا ۱.۵ برابر ATR و تارگت سود ۳.۵ برابر ATR با حداقل نسبت سود به ریسک ۱.۶ (MarginSafe)\n\n"
        "🎯 *۸ دارایی دارای اولویت:* سولانا، بیت‌کوین، دوج‌کوین، انس طلای جهانی، بایننس کوین، اتریوم، ریپل و کاردانو."
    )

def get_user_status_text(sender_id, first_name):
    approved = get_approved_users()
    pending = get_pending_users()
    if sender_id in approved:
        return (
            f"سلام {first_name} عزیز! 👋\n\n"
            "✅ *اشتراک VIP شما فعال است.*\n\n"
            "تمامی سیگنال‌های ۴ ساعته به محض صدور با نوتیفیکیشن اختصاصی برای شما ارسال می‌شوند."
        )
    elif sender_id in pending:
        return (
            f"سلام {first_name} عزیز! 👋\n\n"
            "⏳ *درخواست شما در صف بررسی ادمین است.*\n\n"
            "به محض تأیید ادمین، عضویت شما فعال و اطلاع داده خواهد شد."
        )
    else:
        return (
            f"سلام {first_name} عزیز! 👋\n\n"
            "❌ *حساب شما هنوز فعال نشده است.*\n"
            "برای دسترسی به سیگنال‌ها روی دکمه «💎 درخواست عضویت VIP» بزنید."
        )

# ==============================================================================
# پردازش فوق‌سریع و لحظه‌ای تلگرام (Instant Real-time Handler)
# ==============================================================================
def process_telegram_updates(poll_timeout=1):
    approved = get_approved_users()
    pending = get_pending_users()
    processed_ids = set(load_json(PROCESSED_UPDATES_FILE, []))

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset=-30&timeout={poll_timeout}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=poll_timeout + 5) as r:
            updates = json.loads(r.read().decode()).get("result", [])
    except Exception as e:
        return approved

    for update in updates:
        uid = update.get("update_id")
        if uid in processed_ids:
            continue
        processed_ids.add(uid)

        # ۱. رویداد دکمه‌های شیشه‌ای (Inline Callbacks)
        cb = update.get("callback_query")
        if cb:
            cb_id = cb.get("id")
            cb_data = cb.get("data", "")
            cb_sender = cb.get("from", {})
            cb_sender_id = cb_sender.get("id")
            cb_first_name = cb_sender.get("first_name", "کاربر")
            cb_username = cb_sender.get("username", "بدون آیدی")
            msg = cb.get("message", {})
            msg_id = msg.get("message_id")

            if cb_data == "menu_signals":
                answer_callback(cb_id, "در حال استخراج دیتای صرافی کوکوین...")
                summary = get_market_summary_text()
                edit_telegram_message(cb_sender_id, msg_id, summary, get_back_keyboard())

            elif cb_data == "menu_strategy":
                answer_callback(cb_id)
                strat_text = get_strategy_info_text()
                edit_telegram_message(cb_sender_id, msg_id, strat_text, get_back_keyboard())

            elif cb_data == "menu_status":
                answer_callback(cb_id)
                status_text = get_user_status_text(cb_sender_id, cb_first_name)
                edit_telegram_message(cb_sender_id, msg_id, status_text, get_back_keyboard())

            elif cb_data == "menu_req_vip":
                if cb_sender_id in approved:
                    answer_callback(cb_id, "✅ حساب شما قبلاً فعال شده است!", alert=True)
                elif cb_sender_id in pending:
                    answer_callback(cb_id, "⏳ درخواست شما قبلاً ارسال شده و در صف بررسی است.", alert=True)
                else:
                    pending.add(cb_sender_id)
                    save_json(PENDING_FILE, list(pending))
                    answer_callback(cb_id, "درخواست عضویت شما برای مدیر ارسال شد!", alert=True)
                    
                    edit_telegram_message(
                        cb_sender_id, msg_id,
                        f"⏳ *درخواست عضویت شما دریافت شد.*\nبه دلیل ظرفیت محدود، حساب شما باید توسط مدیر تأیید شود. به محض تأیید اطلاع داده خواهد شد.",
                        get_back_keyboard()
                    )
                    
                    admin_text = (
                        f"👤 *درخواست عضویت VIP کاربر جدید!*\n\n"
                        f"🔹 *نام:* {cb_first_name}\n"
                        f"🔹 *نام کاربری:* @{cb_username}\n"
                        f"🔹 *شناسه عددی:* `{cb_sender_id}`\n\n"
                        f"آیا دسترسی این کاربر را تأیید می‌کنید؟"
                    )
                    send_telegram(ADMIN_CHAT_ID, admin_text, get_admin_verify_keyboard(cb_sender_id))

            elif cb_data.startswith("approve:"):
                if cb_sender_id == ADMIN_CHAT_ID:
                    target_id = int(cb_data.split(":")[1])
                    approved.add(target_id)
                    if target_id in pending:
                        pending.remove(target_id)
                    save_json(SUBSCRIBERS_FILE, list(approved))
                    save_json(PENDING_FILE, list(pending))
                    
                    answer_callback(cb_id, f"کاربر {target_id} تایید شد ✅")
                    edit_telegram_message(
                        ADMIN_CHAT_ID, msg_id,
                        f"✅ *کاربر `{target_id}` با موفقیت تأیید شد و به لیست مشترکین پیوست.*"
                    )
                    send_telegram(
                        target_id,
                        "🎉 *تبریک! حساب شما توسط ادمین تأیید شد.*\nاز این پس تمامی سیگنال‌های معاملاتی ۴ ساعته به صورت لحظه‌ای برای شما ارسال خواهند شد.",
                        get_main_menu_keyboard(False)
                    )

            elif cb_data.startswith("reject:"):
                if cb_sender_id == ADMIN_CHAT_ID:
                    target_id = int(cb_data.split(":")[1])
                    if target_id in pending:
                        pending.remove(target_id)
                    save_json(PENDING_FILE, list(pending))
                    answer_callback(cb_id, f"درخواست رد شد ❌")
                    edit_telegram_message(ADMIN_CHAT_ID, msg_id, f"❌ *درخواست کاربر `{target_id}` رد شد.*")

            elif cb_data == "menu_admin_panel":
                if cb_sender_id == ADMIN_CHAT_ID:
                    answer_callback(cb_id)
                    edit_telegram_message(ADMIN_CHAT_ID, msg_id, "🛡 *پنل مدیریت ادمین:*", get_admin_panel_keyboard())

            elif cb_data == "admin_list_users":
                if cb_sender_id == ADMIN_CHAT_ID:
                    answer_callback(cb_id)
                    u_list = "\n".join([f"• `{uid}`" for uid in approved])
                    edit_telegram_message(ADMIN_CHAT_ID, msg_id, f"👥 *کاربران فعال ({len(approved)} نفر):*\n\n{u_list}", get_admin_panel_keyboard())

            elif cb_data == "admin_list_pending":
                if cb_sender_id == ADMIN_CHAT_ID:
                    answer_callback(cb_id)
                    p_list = "\n".join([f"• `{uid}`" for uid in pending]) if pending else "هیچ کاربری در صف نیست."
                    edit_telegram_message(ADMIN_CHAT_ID, msg_id, f"⏳ *کاربران در صف انتظار ({len(pending)} نفر):*\n\n{p_list}", get_admin_panel_keyboard())

            elif cb_data == "admin_scan_now":
                if cb_sender_id == ADMIN_CHAT_ID:
                    answer_callback(cb_id, "در حال اسکن فوری...")
                    run_scan_internal(force_report=True)

            elif cb_data == "menu_back_main":
                answer_callback(cb_id)
                is_adm = (cb_sender_id == ADMIN_CHAT_ID)
                welcome_text = (
                    f"💎 *به ربات هوشمند سیگنال‌دهی VIP خوش آمدید!*\n\n"
                    f"این سیستم با تحلیل ریاضی **Gann + Ichimoku v6.18**، هشت دارایی برتر را در تایم‌فریم ۴ ساعته رصد می‌کند.\n\n"
                    f"لطفاً یکی از گزینه‌های زیر را انتخاب نمایید:"
                )
                edit_telegram_message(cb_sender_id, msg_id, welcome_text, get_main_menu_keyboard(is_adm))

            continue

        # ۲. رویداد دکمه‌های ثابت پایین صفحه (Persistent Keyboard) و پیام‌های متنی
        message = update.get("message", {})
        sender = message.get("from", {})
        sender_id = sender.get("id")
        first_name = sender.get("first_name", "کاربر")
        username = sender.get("username", "بدون آیدی")
        text = message.get("text", "").strip()

        if not text or not sender_id:
            continue

        is_adm = (sender_id == ADMIN_CHAT_ID)

        # دکمه‌های پایین صفحه:
        if "آخرین وضعیت بازار" in text or "آخرین سیگنال" in text:
            summary = get_market_summary_text()
            send_telegram(sender_id, summary, get_reply_keyboard(is_adm))

        elif "راهنمای استراتژی" in text or "استراتژی گن" in text:
            strat_text = get_strategy_info_text()
            send_telegram(sender_id, strat_text, get_reply_keyboard(is_adm))

        elif "وضعیت اشتراک" in text:
            status_text = get_user_status_text(sender_id, first_name)
            send_telegram(sender_id, status_text, get_reply_keyboard(is_adm))

        elif "درخواست عضویت" in text or "ارتباط با ادمین" in text:
            if sender_id in approved:
                send_telegram(sender_id, "✅ *حساب شما قبلاً فعال شده است و تمام سیگنال‌ها را دریافت می‌کنید.*", get_reply_keyboard(is_adm))
            elif sender_id in pending:
                send_telegram(sender_id, "⏳ *درخواست شما قبلاً ثبت شده و در صف بررسی ادمین قرار دارد.*", get_reply_keyboard(is_adm))
            else:
                pending.add(sender_id)
                save_json(PENDING_FILE, list(pending))
                send_telegram(sender_id, "⏳ *درخواست عضویت شما دریافت شد و برای ادمین ارسال گردید.*", get_reply_keyboard(is_adm))
                admin_text = (
                    f"👤 *درخواست عضویت VIP جدید!*\n\n"
                    f"🔹 *نام:* {first_name}\n"
                    f"🔹 *نام کاربری:* @{username}\n"
                    f"🔹 *شناسه عددی:* `{sender_id}`\n\n"
                    f"جهت فعال‌سازی، دکمه زیر را لمس کنید:"
                )
                send_telegram(ADMIN_CHAT_ID, admin_text, get_admin_verify_keyboard(sender_id))

        elif "پنل مدیریت" in text and is_adm:
            send_telegram(ADMIN_CHAT_ID, "🛡 *پنل مدیریت ادمین:*", get_admin_panel_keyboard())

        elif text == "/start":
            welcome_text = (
                f"سلام {first_name} عزیز! 👋\n\n"
                f"💎 *به ربات هوشمند سیگنال‌دهی VIP خوش آمدید!*\n\n"
                f"این سیستم با تحلیل ریاضی **Gann + Ichimoku v6.18**، هشت دارایی برتر (سولانا، بیت‌کوین، دوج‌کوین، طلا، بایننس، اتریوم، ریپل و کاردانو) را در تایم‌فریم ۴ ساعته رصد می‌کند.\n\n"
                f"لطفاً یکی از گزینه‌های زیر را انتخاب نمایید:"
            )
            # ارسال همزمان منوی شیشه‌ای و کیبورد ثابت پایین صفحه
            send_telegram(sender_id, welcome_text, get_main_menu_keyboard(is_adm))
            # تثبیت کیبورد در پایین صفحه
            send_telegram(sender_id, "👇 از دکمه‌های زیر نیز می‌توانید در هر لحظه استفاده کنید:", get_reply_keyboard(is_adm))

            if sender_id not in approved and sender_id not in pending and sender_id != ADMIN_CHAT_ID:
                pending.add(sender_id)
                save_json(PENDING_FILE, list(pending))
                admin_text = (
                    f"👤 *کاربر جدید دکمه Start را زد!*\n\n"
                    f"🔹 *نام:* {first_name}\n"
                    f"🔹 *نام کاربری:* @{username}\n"
                    f"🔹 *شناسه عددی:* `{sender_id}`\n\n"
                    f"جهت فعال‌سازی، دکمه زیر را لمس کنید:"
                )
                send_telegram(ADMIN_CHAT_ID, admin_text, get_admin_verify_keyboard(sender_id))

        elif sender_id == ADMIN_CHAT_ID and text.startswith("/verify"):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                target_id = int(parts[1])
                approved.add(target_id)
                if target_id in pending:
                    pending.remove(target_id)
                save_json(SUBSCRIBERS_FILE, list(approved))
                save_json(PENDING_FILE, list(pending))
                send_telegram(ADMIN_CHAT_ID, f"✅ *کاربر `{target_id}` با موفقیت تأیید شد.*")
                send_telegram(target_id, "🎉 *تبریک! حساب شما توسط ادمین تأیید شد.*", get_reply_keyboard(False))

        elif sender_id == ADMIN_CHAT_ID and text == "/admin":
            send_telegram(ADMIN_CHAT_ID, "🛡 *پنل مدیریت ادمین:*", get_admin_panel_keyboard())

    save_json(PROCESSED_UPDATES_FILE, list(processed_ids)[-100:])
    return approved

# ==============================================================================
# اسکن بازار و ارسال سیگنال‌ها (Market Scanner Engine)
# ==============================================================================
def send_signal_to_all(text: str):
    approved = get_approved_users()
    for cid in approved:
        send_telegram(cid, text)

def run_scan_internal(force_report=False):
    sent_signals = set(load_json(SENT_SIGNALS_FILE, []))
    new_signals_found = 0

    for item in SYMBOLS:
        prio = item["priority"]
        symbol = item["symbol"]
        name = item["name"]
        desc = item["desc"]
        candles = fetch_candles(symbol)
        if not candles or len(candles) < 60:
            continue
        
        for offset in range(LOOKBACK_CANDLES - 1, -1, -1):
            idx = len(candles) - 1 - offset
            sub_candles = candles[:idx+1]
            result = evaluate_gann_ichimoku_4h(sub_candles)
            if not result or not result[0]:
                continue
            
            signal = result[0]
            sig_key = f"{symbol}_{signal['type']}_{signal['candle_time']}"
            if sig_key in sent_signals:
                continue
            
            sent_signals.add(sig_key)
            new_signals_found += 1
            candle_dt = datetime.fromtimestamp(signal["candle_time"]).strftime("%Y-%m-%d %H:%M")
            msg = (
                f"{signal['action']}\n\n"
                f"⭐ *اولویت #{prio}:* {name}\n"
                f"🎯 *سابقه:* _{desc}_\n"
                f"⏱ *تایم‌فریم:* ۴ ساعته (4H)\n"
                f"📅 *زمان صدور کندل:* `{candle_dt} UTC`\n"
                f"💵 *نقطه ورود دقیق:* `{signal['price']}`\n"
                f"🛑 *حد ضرر محافظتی (SL):* `{round(signal['sl'], 4)}`\n"
                f"🎯 *تارگت اول (TP1):* `{round(signal['tp1'], 4)}`\n"
                f"🚀 *تارگت دوم (TP2):* `{round(signal['tp2'], 4)}`\n"
                f"⚖️ *نسبت سود به ریسک (R/R):* `{signal['rr']}`\n"
                f"📊 *شاخص RSI:* `{signal['rsi']}` ({signal['cloud']})\n\n"
                f"⚡️ _سیستم معاملاتی هوشمند Gann + Ichimoku v6.18_"
            )
            print(f"🚀 سیگنال {name} ارسال شد!")
            send_signal_to_all(msg)
            time.sleep(1)

    if new_signals_found > 0:
        save_json(SENT_SIGNALS_FILE, list(sent_signals)[-200:])
    elif force_report:
        send_telegram(ADMIN_CHAT_ID, "🔍 *اسکن دستی انجام شد:*\nدر حال حاضر سیگنال جدیدی در کندل‌های ۴ ساعته ایجاد نشده است.")

def run_scan():
    process_telegram_updates(poll_timeout=1)
    run_scan_internal()

def main():
    """
    حلقه مانیتورینگ زنده و فوق‌سریع:
    تلگرام را ثانیه به ثانیه بررسی می‌کند (پاسخ آنی زیر ۱ ثانیه)
    و بازار را هر ۲ دقیقه اسکن می‌کند.
    """
    print("🚀 مانیتورینگ بلادرنگ تلگرام و بازار آغاز شد...")
    start_time = time.time()
    last_market_scan = 0
    MARKET_SCAN_INTERVAL = 120  # هر ۲ دقیقه یک‌بار اسکن بازار

    # اجرای مداوم به مدت ۴۵ دقیقه در هر نوبت گیت‌هاب
    while time.time() - start_time < 2700:
        try:
            # بررسی سریع تلگرام (پاسخ فوری به کلیک‌ها)
            process_telegram_updates(poll_timeout=1)
            
            # بررسی منظم بازار
            now = time.time()
            if now - last_market_scan >= MARKET_SCAN_INTERVAL:
                run_scan_internal()
                last_market_scan = now
                
            time.sleep(1)
        except Exception as e:
            print(f"Error in live loop: {e}")
            time.sleep(2)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_scan()
    else:
        main()
