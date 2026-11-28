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

# کاربران تأیید شده به صورت پیش‌فرض (همیشه دائمی)
DEFAULT_APPROVED_IDS = [1991886913, 234659465, 100238424]

SUBSCRIBERS_FILE = "subscribers.json"
PENDING_FILE = "pending_users.json"
SENT_SIGNALS_FILE = "sent_signals.json"
PROCESSED_UPDATES_FILE = ".processed_updates.json"

# ==============================================================================
# مدیریت فایل‌ها و دیتابیس کاربران
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
    merged = set(DEFAULT_APPROVED_IDS) | set(saved)
    return merged

def get_pending_users():
    return set(load_json(PENDING_FILE, []))

def send_telegram_to(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Error sending to {chat_id}: {e}")
        return None

# ==============================================================================
# مدیریت درخواست‌های کاربران و وریفای (تأییدیه فقط ۱ بار برای ادمین)
# ==============================================================================
def process_user_verifications():
    approved = get_approved_users()
    pending = get_pending_users()
    processed_ids = set(load_json(PROCESSED_UPDATES_FILE, []))

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset=-30"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            updates = json.loads(r.read().decode()).get("result", [])
    except Exception as e:
        print(f"Error fetching updates: {e}")
        return approved

    for update in updates:
        uid = update.get("update_id")
        if uid in processed_ids:
            continue
        processed_ids.add(uid)

        msg = update.get("message", {})
        sender = msg.get("from", {})
        sender_id = sender.get("id")
        first_name = sender.get("first_name", "کاربر")
        username = sender.get("username", "بدون آیدی")
        text = msg.get("text", "").strip()

        if not text or not sender_id:
            continue

        # ۱. دستور تایید توسط ادمین: /verify <chat_id>
        if sender_id == ADMIN_CHAT_ID and text.startswith("/verify"):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                target_id = int(parts[1])
                approved.add(target_id)
                if target_id in pending:
                    pending.remove(target_id)
                save_json(SUBSCRIBERS_FILE, list(approved))
                save_json(PENDING_FILE, list(pending))
                send_telegram_to(ADMIN_CHAT_ID, f"✅ *کاربر `{target_id}` با موفقیت تأیید شد و به لیست اضافه گردید.*")
                send_telegram_to(target_id, "🎉 *تبریک! حساب شما توسط ادمین تأیید شد.*\n\nاز این پس تمامی سیگنال‌های معاملاتی ۴ ساعته استراتژی گن + ایچیموکو به صورت لحظه‌ای برای شما ارسال خواهند شد.")

        # ۲. دستور لیست کاربران: /list
        elif sender_id == ADMIN_CHAT_ID and text == "/list":
            u_list = "\n".join([f"• `{uid}`" for uid in approved])
            p_list = "\n".join([f"• `{uid}`" for uid in pending]) if pending else "هیچ کاربری در صف نیست."
            send_telegram_to(
                ADMIN_CHAT_ID,
                f"📋 *وضعیت کاربران:*\n\n"
                f"✅ *تأییدشده‌ها ({len(approved)} نفر):*\n{u_list}\n\n"
                f"⏳ *در انتظار تأیید ({len(pending)} نفر):*\n{p_list}"
            )

        # ۳. دستور حذف کاربر: /remove <chat_id>
        elif sender_id == ADMIN_CHAT_ID and text.startswith("/remove"):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                target_id = int(parts[1])
                if target_id in approved:
                    approved.remove(target_id)
                if target_id in pending:
                    pending.remove(target_id)
                save_json(SUBSCRIBERS_FILE, list(approved))
                save_json(PENDING_FILE, list(pending))
                send_telegram_to(ADMIN_CHAT_ID, f"🚫 *کاربر `{target_id}` حذف شد.*")

        # ۴. کلیک روی /start توسط هر کاربری
        elif text == "/start":
            if sender_id in approved:
                # کاربر قبلاً تایید شده
                send_telegram_to(
                    sender_id,
                    f"سلام {first_name} عزیز! 👋\n\n✅ *حساب شما قبلاً تأیید شده و فعال است.*\nسیگنال‌های معاملاتی ۴ ساعته به محض صدور به صورت خودکار برای شما ارسال خواهند شد."
                )
            elif sender_id in pending:
                # کاربر قبلاً درخواست داده و منتظر تایید است (به ادمین پیام تکراری داده نمی‌شود!)
                send_telegram_to(
                    sender_id,
                    f"سلام {first_name} عزیز! 👋\n\n⏳ *درخواست عضویت شما قبلاً ثبت شده و در صف بررسی ادمین قرار دارد.*\nلطفاً صبور باشید، به محض تأیید ادمین اطلاع داده خواهد شد."
                )
            else:
                # کاربر کاملاً جدید است: دقیقاً ۱ بار به ادمین پیام می‌رود
                pending.add(sender_id)
                save_json(PENDING_FILE, list(pending))
                
                # پیام به کاربر
                send_telegram_to(
                    sender_id,
                    f"سلام {first_name} عزیز! 👋\n\n⏳ *درخواست عضویت شما دریافت شد.*\nبه دلیل ظرفیت محدود، حساب شما باید توسط مدیر تأیید شود. به محض تأیید به شما اطلاع داده خواهد شد."
                )
                
                # پیام هشدار به ادمین (فقط یک‌بار)
                admin_alert = (
                    f"👤 *درخواست عضویت کاربر جدید!*\n\n"
                    f"🔹 *نام:* {first_name}\n"
                    f"🔹 *نام کاربری:* @{username}\n"
                    f"🔹 *شناسه عددی (Chat ID):* `{sender_id}`\n\n"
                    f"جهت تأیید این کاربر، دستور زیر را ارسال کنید:\n"
                    f"`/verify {sender_id}`"
                )
                send_telegram_to(ADMIN_CHAT_ID, admin_alert)

    # ذخیره پیام‌های خوانده شده
    save_json(PROCESSED_UPDATES_FILE, list(processed_ids)[-100:])
    return approved

# ==============================================================================
# نمادها و استراتژی معاملاتی
# ==============================================================================
SYMBOLS = [
    {"priority": 1, "name": "سولانا (SOL)", "symbol": "SOL-USDT", "desc": "رتبه ۱ بازدهی و مومنتوم ۲ سال اخیر"},
    {"priority": 2, "name": "بیت‌کوین (BTC)", "symbol": "BTC-USDT", "desc": "رهبر بازار و ثبت سقف‌های تاریخی جدید"},
    {"priority": 3, "name": "دوج‌کوین (DOGE)", "symbol": "DOGE-USDT", "desc": "بیشترین جهش‌های شارپ صعودی"},
    {"priority": 4, "name": "انس طلای جهانی (Gold)", "symbol": "PAXG-USDT", "desc": "رکوردشکنی تاریخی با بالاترین پایداری"},
    {"priority": 5, "name": "بایننس کوین (BNB)", "symbol": "BNB-USDT", "desc": "سودآوری پایدار اکوسیستم بایننس"},
    {"priority": 6, "name": "اتریوم (ETH)", "symbol": "ETH-USDT", "desc": "دومین دارایی قدرتمند کریپتو"},
    {"priority": 7, "name": "ریپل (XRP)", "symbol": "XRP-USDT", "desc": "حجم معاملاتی بالا در شکست‌های تکنیکال"},
    {"priority": 8, "name": "کاردانو (ADA)", "symbol": "ADA-USDT", "desc": "روند حرکتی بلندمدت"}
]

TIMEFRAME = "4hour"
LOOKBACK_CANDLES = 4  # بررسی تا ۴ کندل اخیر (۱۶ ساعت گذشته) تا در صورت تأخیر گیت‌هاب هیچ سیگنالی نسوزد

def send_signal_to_all(text: str):
    approved = get_approved_users()
    for cid in approved:
        send_telegram_to(cid, text)

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

def run_scan():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now_str}] بررسی درخواست‌های کاربران و اسکن هوشمند بازار...")
    
    # اول: پردازش دقیق کاربران جدید و وریفای
    process_user_verifications()
    
    # دوم: بارگذاری تاریخچه سیگنال‌های ارسال‌شده
    sent_signals = set(load_json(SENT_SIGNALS_FILE, []))
    new_signals_sent = False

    # سوم: اسکن بازار با بررسی کندل‌های اخیر (Lookback) برای جلوگیری از سوختن سیگنال‌ها
    for item in SYMBOLS:
        prio = item["priority"]
        symbol = item["symbol"]
        name = item["name"]
        desc = item["desc"]
        candles = fetch_candles(symbol)
        if not candles or len(candles) < 60:
            continue
        
        # بررسی کندل‌های اخیر تا اگر گیت‌هاب با تاخیر اجرا شد سیگنالی از دست نرود
        for offset in range(LOOKBACK_CANDLES - 1, -1, -1):
            idx = len(candles) - 1 - offset
            sub_candles = candles[:idx+1]
            result = evaluate_gann_ichimoku_4h(sub_candles)
            if not result or not result[0]:
                continue
            
            signal = result[0]
            sig_key = f"{symbol}_{signal['type']}_{signal['candle_time']}"
            
            # اگر قبلاً ارسال شده، رد شو
            if sig_key in sent_signals:
                continue
            
            # سیگنال جدید پیدا شد! ثبت و ارسال
            sent_signals.add(sig_key)
            new_signals_sent = True
            
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
            print(f"🚀 سیگنال جدید {name} ({candle_dt}) برای تمام کاربران ارسال شد!")
            send_signal_to_all(msg)
            time.sleep(1)

    if new_signals_sent:
        save_json(SENT_SIGNALS_FILE, list(sent_signals)[-200:])

def main():
    """
    اجرای حلقه در هر بار بیداری گیت‌هاب (تا چند دقیقه فعال می‌ماند)
    """
    print("شروع اسکن هوشمند...")
    # هر ران ۵ دور با فاصله ۴۰ ثانیه اجرا می‌شود (حدود ۳.۵ دقیقه مانیتورینگ زنده)
    for _ in range(5):
        run_scan()
        time.sleep(40)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_scan()
    else:
        main()
