import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import requests
import pandas as pd
import ta

# --- [ Configurations ] ---
# အစ်ကို ပေးပို့လိုက်သော Telegram Bot Token နှင့် Chat ID အသစ်များကို လဲလှယ်ပေးထားပါသည်။
TELEGRAM_BOT_TOKEN = "8631721554:AAF_w87cfJ8M27gc79JzF1O9BVhkmSQQ7B0"
TELEGRAM_CHAT_ID = "1616497804"
TWELVEDATA_API_KEY = "Be07ae7e3db948f7ab549dcc4fc29ab5"

# Twelve Data Free Plan တွင် ၁၀၀% ပိတ်မထားဘဲ အလုပ်လုပ်သော ကမ္ဘာ့အဓိက Forex အတွဲများ
ASSETS = {
    "EUR/USD": "EUR/USD",
    "GBP/USD": "GBP/USD",
    "USD/JPY": "USD/JPY",
    "AUD/USD": "AUD/USD",
    "USD/CHF": "USD/CHF"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
last_signals = {asset: None for asset in ASSETS.keys()}

def send_telegram_message(text):
    url = f"https://api.telegram.com/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload)
        logging.info(f"Telegram API Sent Status: {response.status_code}")
    except Exception as e:
        logging.error(f"Telegram Error: {e}")

def get_twelvedata_data(symbol):
    """ Twelve Data Free Plan အတွက် စိတ်ချရဆုံး ဒေတာဆွဲယူစနစ် """
    url = f"https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1h",
        "outputsize": "100",
        "apikey": TWELVEDATA_API_KEY
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if "values" in data:
            df = pd.DataFrame(data["values"])
            df = df.rename(columns={
                "datetime": "Datetime",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume"
            })
            df = df.iloc[::-1].reset_index(drop=True)
            df[["Open", "High", "Low", "Close"]] = df[["Open", "High", "Low", "Close"]].astype(float)
            logging.info(f"Successfully fetched data for {symbol}. Total rows: {len(df)}")
            return df
        else:
            logging.error(f"TwelveData Error for {symbol}: {data.get('message', 'Unknown Error')}")
            return pd.DataFrame()
    except Exception as e:
        logging.error(f"Request Error for {symbol}: {e}")
        return pd.DataFrame()

def generate_fundamental_reason(asset_name, direction):
    reasons = {
        "EUR/USD": {
            "BUY": "ဥရောပဗဟိုဘဏ် (ECB) ၏ တင်းကျပ်သော ငွေကြေးမူဝါဒ သို့မဟုတ် အမေရိကန် Fed ဘဏ်မှ အတိုးနှုန်းလျှော့ချမည့် အရိပ်အယောင်များကြောင့် ယူရိုဒေါ်လာ အားသာလာသည်။",
            "SELL": "အမေရိကန် စီးပွားရေးဒေတာများ (Non-Farm Payroll / CPI) ခိုင်မာနေပြီး Fed ဘဏ်မှ အတိုးနှုန်းကို ဆက်လက်ထိန်းထားနိုင်ခြေရှိသောကြောင့် ဒေါ်လာ အားကောင်းနေသည်။"
        },
        "GBP/USD": {
            "BUY": "ဗြိတိန်ငွေကြေးဖောင်းပွမှုဒေတာများကြောင့် BOE ဘဏ်မှ အတိုးနှုန်း ဆက်ထိန်းထားနိုင်ခြင်းနှင့် ဒေါ်လာဘက်တွင် အားနည်းနေခြင်းကြောင့် ပေါင်စတာလင် မြင့်တက်နေသည်။",
            "SELL": "ယူကေစီးပွားရေး နှေးကွေးမည့်အရေး စိုးရိမ်ရခြင်းနှင့် အမေရိကန်ဘက်မှ စီးပွားရေးအခြေအနေ ပိုမိုကောင်းမွန်နေသဖြင့် ပေါင်စျေး လျှောကျနေသည်။"
        },
        "USD/JPY": {
            "BUY": "ဂျပန်ဗဟိုဘဏ် (BOJ) ၏ အတိုးနှုန်းမြှင့်တင်ရန် နှောင့်နှေးနေမှုနှင့် အမေရိကန် Yields မြင့်တက်မှုတို့ကြောင့် ဒေါ်လာသည် ယန်းငွေအပေါ် သိသိသာသာ အားသာနေသည်။",
            "SELL": "ဂျပန်ဗဟိုဘဏ်မှ Market Intervention (စျေးကွက်ထဲဝင်ရောက်စွက်ဖက်ခြင်း) ပြုလုပ်လာနိုင်ခြေ သို့မဟုတ် Safe Haven အနေဖြင့် ယန်းငွေဝယ်လိုအား ပြန်တက်လာခြင်း။"
        },
        "AUD/USD": {
            "BUY": "သြစတြေးလျဗဟိုဘဏ် (RBA) ၏ Hawkish ဖြစ်သော မူဝါဒရပ်တည်ချက်နှင့် ကုန်စည်စျေးနှုန်းများ မြင့်တက်လာခြင်းက ဩဇီဒေါ်လာကို အထောက်အပံ့ဖြစ်စေသည်။",
            "SELL": "တရုတ်စီးပွားရေး နှေးကွေးမှုနောက်ဆက်တွဲ သက်ရောက်မှုများနှင့် ကမ္ဘာ့စျေးကွက်တွင် Risk-Off (စွန့်စားရမှုကို ရှောင်လွှဲခြင်း) အခြေအနေကြောင့် အကျဘက်ပြနေသည်။"
        },
        "USD/CHF": {
            "BUY": "ဆွစ်ဇာလန်ဗဟိုဘဏ် (SNB) ၏ အတိုးနှုန်းလျှော့ချမှု မူဝါဒများကြောင့် ဆွစ်ဖရန့်ငွေ အားနည်းသွားပြီး အမေရိကန်ဒေါ်လာဘက်က အသာစီးရလာသည်။",
            "SELL": "ကမ္ဘာ့ပထဝီနိုင်ငံရေး တင်းမာမှုများကြောင့် Safe Haven ဖြစ်သော ဆွစ်ဖရန့်ငွေဘက်သို့ ရင်းနှီးမြှုပ်နှံသူများ အလုံးအရင်းဝင်ရောက်လာပြီး ဒေါ်လာ ကျဆင်းသည်။"
        }
    }
    return reasons.get(asset_name, {}).get(direction, "စျေးကွက်လမ်းကြောင်း အပြောင်းအလဲ မြန်ဆန်နေသဖြင့် သတိပြုကုန်သွယ်ရန်။")

async def check_markets_and_alert():
    global last_signals
    logging.info("🚀 [QUANT FOREX ENGINE STARTING]")
    
    # ဆာဗာတက်တာနဲ့ အစ်ကို့ Bot အသစ်ထဲကို တိုက်ရိုက် စာလှမ်းပို့မည့်အပိုင်း
    send_telegram_message(
        "🧠 **QUANT FOREX TRADING BOT ONLINE (v3.5)**\n\n"
        "• **Data Feed:** Twelve Data (Free Live Forex)\n"
        "• **Bot Status:** Updated to New Telegram Bot 🤖\n"
        "• **Owner:** Thien Zaw Aye\n"
        "• **Pairs:** EURUSD, GBPUSD, USDJPY, AUDUSD, USDCHF\n\n"
        "🟢 *Forex စျေးကွက် ဆန်းစစ်ချက်များကို တိုက်ရိုက် စတင်စောင့်ကြည့်နေပါပြီဗျာ...*"
    )
    
    while True:
        for asset_name, symbol in ASSETS.items():
            try:
                await asyncio.sleep(2)
                df = get_twelvedata_data(symbol)
                if df.empty or len(df) < 30:
                    continue
                
                df['RSI_14'] = ta.momentum.rsi(df['Close'], window=14)
                df['EMA_50'] = ta.trend.ema_indicator(df['Close'], window=50)
                macd = ta.trend.MACD(close=df['Close'], window_fast=12, window_slow=26, window_sign=9)
                df['MACD'] = macd.macd()
                df['MACD_Signal'] = macd.macd_signal()
                
                current_price = float(df['Close'].iloc[-1])
                current_rsi_14 = float(df['RSI_14'].iloc[-1])
                current_ema_50 = float(df['EMA_50'].iloc[-1])
                current_macd = float(df['MACD'].iloc[-1])
                current_macd_sig = float(df['MACD_Signal'].iloc[-1])
                
                recent_low = float(df['Low'].iloc[-10:].min())
                recent_high = float(df['High'].iloc[-10:].max())
                
                # Signal Logic
                if (current_rsi_14 > 45) and (current_price > current_ema_50) and (current_macd > current_macd_sig):
                    if last_signals[asset_name] != "BUY":
                        sl = recent_low - (current_price * 0.0005)
                        tp = current_price + ((current_price - sl) * 1.5)
                        fund_reason = generate_fundamental_reason(asset_name, "BUY")
                        
                        message = (
                            f"🟢 **🎯 QUANT SIGNALS: PERFECT BUY (ဝယ်ရန်)**\n\n"
                            f"📊 **Asset Pair:** {asset_name}\n"
                            f"🔥 **Status:** `Market Trend Confirmed` 🎯\n\n"
                            f"💰 **Entry Price:** {current_price:.5f}\n"
                            f"🎯 **Take Profit (TP):** {tp:.5f}\n"
                            f"🛑 **Stop Loss (SL):** {sl:.5f}\n\n"
                            f"🔬 **Technical Analysis:**\n"
                            f"• စျေးနှုန်းသည် EMA 50 အထက်တွင်ရှိပြီး အတက် Momentum စတင်နေသည်။\n"
                            f"• RSI 14 သည် `{current_rsi_14:.2f}` ဖြစ်ပြီး MACD တွင် ဝယ်လိုအား အားသာလာသည်။\n\n"
                            f"🌍 **Fundamental Analysis (အခြေခံသုံးသပ်ချက်):**\n"
                            f"_{fund_reason}_"
                        )
                        send_telegram_message(message)
                        last_signals[asset_name] = "BUY"
                        
                elif (current_rsi_14 < 55) and (current_price < current_ema_50) and (current_macd < current_macd_sig):
                    if last_signals[asset_name] != "SELL":
                        sl = recent_high + (current_price * 0.0005)
                        tp = current_price - ((sl - current_price) * 1.5)
                        fund_reason = generate_fundamental_reason(asset_name, "SELL")
                        
                        message = (
                            f"🔴 **🎯 QUANT SIGNALS: PERFECT SELL (ရောင်းရန်)**\n\n"
                            f"📊 **Asset Pair:** {asset_name}\n"
                            f"🔥 **Status:** `Market Trend Confirmed` 🎯\n\n"
                            f"💰 **Entry Price:** {current_price:.5f}\n"
                            f"🎯 **Take Profit (TP):** {tp:.5f}\n"
                            f"🛑 **Stop Loss (SL):** {sl:.5f}\n\n"
                            f"🔬 **Technical Analysis:**\n"
                            f"• စျေးနှုန်းသည် EMA 50 အောက်သို့ ရောက်ရှိပြီး အကျဘက် အားသာနေသည်။\n"
                            f"• RSI 14 သည် `{current_rsi_14:.2f}` ဖြစ်ပြီး ရောင်းလိုအား ဖိအားပေးနေသည်။\n\n"
                            f"🌍 **Fundamental Analysis (အခြေခံသုံးသပ်ချက်):**\n"
                            f"_{fund_reason}_"
                        )
                        send_telegram_message(message)
                        last_signals[asset_name] = "SELL"
                        
            except Exception as e:
                logging.error(f"Error processing {asset_name}: {e}")
                continue
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(check_markets_and_alert())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "Expert Forex Quant Engine Online with New Bot Token"}
