import json
import math
import os
import threading
import time
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==============================================================================
# Telegram Settings (تنظیمات ربات و ادمین)
# ==============================================================================
TELEGRAM_BOT_TOKEN = "9129289513:AAEYueiZOQOlmZ07iHP1mC5db0tKRPy-7o4"
ADMIN_CHAT_ID = 1991886913  # شناسه شما (محمود) به عنوان مدیر اصلی

# کاربران پیش‌فرضی که از قبل تایید شده‌اند
DEFAULT_APPROVED_IDS = [1991886913, 234659465]
SUBSCRIBERS_FILE = "subscribers.json"

# ==============================================================================
# مدیریت کاربران و وریفای (تایید صلاحیت)
# ==============================================================================
def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data)
        except Exception:
            pass
    return set(DEFAULT_APPROVED_IDS)

def save_subscribers(subs_set):
    try:
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(subs_set), f, indent=2)
    except Exception as e:
        print(f"Error saving subscribers: {e}")

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

def process_user_verifications():
    """
    بررسی پیام‌های دریافتی ربات برای ثبت‌نام و تایید ادمین:
    - اگر کاربر جدید /start زد: ارسال درخواست به ادمین
    - اگر ادمین /verify <id> فرستاد: تایید کاربر و اطلاع‌رسانی
    """
    approved = load_subscribers()
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset=-25"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            updates = json.loads(r.read().decode()).get("result", [])
    except Exception as e:
        print(f"Error fetching updates: {e}")
        return approved

    # فایل رهگیری آخرین پیام‌های پردازش‌شده
    processed_file = ".processed_updates.json"
    processed_ids = set()
    if os.path.exists(processed_file):
        try:
            with open(processed_file, "r") as f:
                processed_ids = set(json.load(f))
        except Exception:
            pass

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
                save_subscribers(approved)
                send_telegram_to(ADMIN_CHAT_ID, f"✅ *کاربر `{target_id}` با موفقیت تأیید شد و به لیست دریافت‌کنندگان سیگنال افزوده شد.*")
                send_telegram_to(target_id, "🎉 *تبریک! حساب شما توسط ادمین تأیید شد.*\n\nاز این پس تمامی سیگنال‌های معاملاتی استراتژی گن + ایچیموکو به صورت لحظه‌ای برای شما ارسال خواهند شد.")

        # ۲. دستور لیست کاربران تایید شده: /list
        elif sender_id == ADMIN_CHAT_ID and text == "/list":
            user_list = "\n".join([f"• `{uid}`" for uid in approved])
            send_telegram_to(ADMIN_CHAT_ID, f"📋 *لیست کاربران تأیید شده ({len(approved)} نفر):*\n\n{user_list}")

        # ۳. دستور حذف کاربر: /remove <chat_id>
        elif sender_id == ADMIN_CHAT_ID and text.startswith("/remove"):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                target_id = int(parts[1])
                if target_id in approved:
                    approved.remove(target_id)
                    save_subscribers(approved)
                    send_telegram_to(ADMIN_CHAT_ID, f"🚫 *کاربر `{target_id}` از لیست حذف شد.*")

        # ۴. کلیک روی /start توسط هر کاربری
        elif text == "/start":
            if sender_id in approved:
                send_telegram_to(sender_id, f"سلام {first_name} عزیز! 👋\n\n✅ *حساب شما قبلاً تأیید شده است.* ربات فعال بوده و سیگنال‌های ۴ ساعته جدید را به محض صدور دریافت خواهید کرد.")
            else:
                # پیام به کاربر
                send_telegram_to(sender_id, f"سلام {first_name} عزیز! 👋\n\n⏳ *درخواست عضویت شما دریافت شد.*\nبه دلیل محدودیت ظرفیت، حساب شما باید توسط مدیر تأیید شود. به محض تأیید ادمین، اطلاع داده خواهد شد.")
                # پیام هشدار به ادمین برای تایید
                admin_alert = (
                    f"👤 *درخواست عضویت کاربر جدید!*\n\n"
                    f"🔹 *نام:* {first_name}\n"
                    f"🔹 *نام کاربری:* @{username}\n"
                    f"🔹 *شناسه عددی (Chat ID):* `{sender_id}`\n\n"
                    f"جهت تأیید این کاربر، دستور زیر را ارسال کنید:\n"
                    f"`/verify {sender_id}`"
                )
                send_telegram_to(ADMIN_CHAT_ID, admin_alert)

    # ذخیره update_id های پردازش شده
    try:
        with open(processed_file, "w") as f:
            json.dump(list(processed_ids)[-100:], f)
    except Exception:
        pass

    return approved

# ==============================================================================
# نمادها و استراتژی
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
CHECK_INTERVAL = 120
sent_signals = {}

def send_signal_to_all(text: str):
    approved = load_subscribers()
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
    print(f"\n[{now_str}] بررسی کاربران جدید و اسکن بازار...")
    
    # اول: پردازش درخواست‌های عضویت و وریفای توسط ادمین
    process_user_verifications()
    
    # دوم: اسکن بازار برای تولید سیگنال
    for item in SYMBOLS:
        prio = item["priority"]
        symbol = item["symbol"]
        name = item["name"]
        desc = item["desc"]
        candles = fetch_candles(symbol)
        if not candles:
            continue
        result = evaluate_gann_ichimoku_4h(candles)
        if not result:
            continue
        signal, price, rsi, (tenkan, kijun) = result
        if signal:
            sig_key = f"{symbol}_{signal['type']}_{signal['candle_time']}"
            if sig_key in sent_signals:
                continue
            sent_signals[sig_key] = True
            msg = (
                f"{signal['action']}\n\n"
                f"⭐ *اولویت #{prio}:* {name}\n"
                f"🎯 *سابقه:* _{desc}_\n"
                f"⏱ *تایم‌فریم:* ۴ ساعته (4H)\n"
                f"💵 *نقطه ورود دقیق:* `{signal['price']}`\n"
                f"🛑 *حد ضرر محافظتی (SL):* `{round(signal['sl'], 4)}`\n"
                f"🎯 *تارگت اول (TP1):* `{round(signal['tp1'], 4)}`\n"
                f"🚀 *تارگت دوم (TP2):* `{round(signal['tp2'], 4)}`\n"
                f"⚖️ *نسبت سود به ریسک (R/R):* `{signal['rr']}`\n"
                f"📊 *شاخص RSI:* `{signal['rsi']}` ({signal['cloud']})\n\n"
                f"⚡️ _سیستم معاملاتی هوشمند Gann + Ichimoku v6.18_"
            )
            print(f"🚀 سیگنال {name} برای تمامی کاربران تأییدشده ارسال شد!")
            send_signal_to_all(msg)
            time.sleep(1)

def main():
    while True:
        try:
            run_scan()
        except Exception as e:
            print(f"خطا در اسکن: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run_scan()
