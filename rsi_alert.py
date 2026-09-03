import json
import os
import requests
from datetime import datetime, timezone

STATE_FILE = "state.json"


def load_prev_signal() -> str:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f).get("signal", "neutral")
    return "neutral"


def save_signal(signal: str):
    with open(STATE_FILE, "w") as f:
        json.dump({"signal": signal}, f)

SYMBOL = "AUD/NZD"
INTERVAL = "8h"
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30


def get_rsi():
    url = "https://api.twelvedata.com/rsi"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "time_period": RSI_PERIOD,
        "apikey": os.environ["TWELVEDATA_API_KEY"],
        "outputsize": 1,
        "format": "JSON",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") == "error":
        raise RuntimeError(f"Twelvedata API error: {data.get('message')}")

    latest = data["values"][0]
    return float(latest["rsi"]), latest["datetime"]


def get_price():
    url = "https://api.twelvedata.com/price"
    params = {
        "symbol": SYMBOL,
        "apikey": os.environ["TWELVEDATA_API_KEY"],
        "format": "JSON",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") == "error":
        raise RuntimeError(f"Twelvedata API error: {data.get('message')}")

    return float(data["price"])


def send_discord(rsi_value: float, price: float, candle_time: str, signal: str):
    if signal == "overbought":
        color = 0xE74C3C  # red
        label = "買われすぎ (RSI > 70)"
        advice = "売りシグナルを確認してください"
    else:
        color = 0x2ECC71  # green
        label = "売られすぎ (RSI < 30)"
        advice = "買いシグナルを確認してください"

    now_utc = datetime.now(timezone.utc).isoformat()

    embed = {
        "title": f"AUD/NZD 8時間足 RSIアラート — {label}",
        "color": color,
        "fields": [
            {"name": "通貨ペア", "value": SYMBOL, "inline": True},
            {"name": "時間足", "value": "8H", "inline": True},
            {"name": "RSI (14)", "value": f"{rsi_value:.2f}", "inline": True},
            {"name": "現在価格", "value": f"{price:.5f}", "inline": True},
            {"name": "確定足時刻 (UTC)", "value": candle_time, "inline": True},
            {"name": "判断", "value": advice, "inline": False},
        ],
        "footer": {"text": "Twelvedata | 裁量取引アラート"},
        "timestamp": now_utc,
    }

    payload = {"embeds": [embed]}
    resp = requests.post(
        os.environ["DISCORD_WEBHOOK_URL"], json=payload, timeout=15
    )
    resp.raise_for_status()
    print(f"Discord通知送信完了: {signal}")


def main():
    rsi_value, candle_time = get_rsi()
    price = get_price()

    print(f"AUD/NZD RSI(14) 8H: {rsi_value:.2f}  確定時刻: {candle_time}  価格: {price:.5f}")

    if rsi_value > RSI_OVERBOUGHT:
        current_signal = "overbought"
    elif rsi_value < RSI_OVERSOLD:
        current_signal = "oversold"
    else:
        current_signal = "neutral"

    prev_signal = load_prev_signal()

    if current_signal != "neutral" and current_signal != prev_signal:
        send_discord(rsi_value, price, candle_time, current_signal)
    elif current_signal == "neutral":
        print(f"RSIはニュートラルゾーン ({RSI_OVERSOLD} ≤ {rsi_value:.2f} ≤ {RSI_OVERBOUGHT}) — 通知なし")
    else:
        print(f"シグナル継続中 ({current_signal}) — 重複通知スキップ")

    save_signal(current_signal)


if __name__ == "__main__":
    main()
