import json
import math
import os
import threading
import time
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==============================================================================
# Telegram Settings (تنظیمات ربات تلگرام)
# ==============================================================================
TELEGRAM_BOT_TOKEN = "9129289513:AAEYueiZOQOlmZ07iHP1mC5db0tKRPy-7o4"
TELEGRAM_CHAT_ID = "1991886913"

# ==============================================================================
# اولویت‌بندی نمادها بر اساس بیشترین سودآوری و مومنتوم ۲ سال اخیر (تایم‌فریم ۴ ساعته)
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

TIMEFRAME = "4hour"       # تایم‌فریم ۴ ساعته
CHECK_INTERVAL = 120      # بررسی کندل‌ها هر ۲ دقیقه یک‌بار

sent_signals = {}

# ==============================================================================
# وب‌سرور داخلی مخصوص Render.com (برای زنده ماندن ۲۴ ساعته در پلن رایگان)
# ==============================================================================
class RenderHealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("🤖 ربات سیگنال‌دهی گن + ایچیموکو فعال و آنلاین است!".encode("utf-8"))

    def log_message(self, format, *args):
        return  # خاموش کردن لاگ‌های اضافه وب‌سرور

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), RenderHealthServer)
    print(f"🌐 وب‌سرور فعال‌ساز Render روی پورت {port} آغاز به کار کرد.")
    server.serve_forever()

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
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
        print(f"❌ خطا در ارسال تلگرام: {e}")
        return None

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
        print(f"❌ خطا در دریافت کندل‌های {symbol}: {e}")
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
    
    def donchian(start, end):
        return (max(highs[start:end+1]) + min(lows[start:end+1])) / 2.0
    
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
    print(f"\n[{now_str}] در حال اسکن بازار ۴ ساعته...")
    
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
        print(f"#{prio} {name:<20} | {price:<10} | RSI: {rsi:<4.1f} | Tenkan: {tenkan:<8.2f} | Kijun: {kijun:<8.2f}")
        
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
            print(f"🚀 سیگنال {name} به تلگرام شلیک شد!")
            send_telegram(msg)
            time.sleep(1)

def main():
    print("=" * 60)
    print("🤖 شروع به کار ربات گن + ایچیموکو ویژه Render.com")
    print("=" * 60)
    
    # اجرای وب‌سرور در یک ترد مستقل برای زنده نگه داشتن سرویس در Render
    web_thread = threading.Thread(target=start_health_check_server, daemon=True)
    web_thread.start()
    
    # پیام اولیه شروع به کار برای تلگرام
    send_telegram("🚀 *ربات معاملاتی روی سرور ۲۴ ساعته با موفقیت راه‌اندازی شد!*\n\n⏱ تایم‌فریم: ۴ ساعته (4H)\n📊 نمادها: ۶ ارز برتر + دوج‌کوین + انس طلا")
    
    # حلقه دائم اسکن بازار
    while True:
        try:
            run_scan()
        except Exception as e:
            print(f"خطا در اسکن: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
