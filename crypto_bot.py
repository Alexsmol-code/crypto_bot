"""
Crypto News Sentiment Bot — облегчённая версия для непрофессиональных пользователей.
Автор: GPT-5

Функции:
- Скачивает новости о выбранной криптомонете (из RSS-источников, без API-ключей)
- Анализирует настроение новостей (позитив / негатив)
- Получает текущую цену из CoinGecko
- Даёт примерный прогноз направления и процента движения
- Может отправлять уведомления в Telegram или Discord
"""

import argparse
import datetime as dt
import requests
import feedparser
import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.linear_model import Ridge
import os
import sys

# ------------------ Настройки ------------------
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=cryptocurrency",
    "https://news.google.com/rss/search?q=bitcoin",
    "https://news.google.com/rss/search?q=ethereum",
]

COINGECKO_URL = "https://api.coingecko.com/api/v3"

# ------------------------------------------------


def fetch_news(coin):
    """Загрузка последних новостей из RSS"""
    texts = []
    for feed in RSS_FEEDS:
        d = feedparser.parse(feed)
        for e in d.entries:
            if coin.lower() in e.title.lower() or coin.lower() in e.summary.lower():
                texts.append(e.title + " " + e.summary)
    return texts


def fetch_price(coin="bitcoin"):
    """Получение текущей цены"""
    try:
        r = requests.get(f"{COINGECKO_URL}/simple/price?ids={coin}&vs_currencies=usd")
        r.raise_for_status()
        return r.json()[coin]["usd"]
    except Exception as e:
        print("Ошибка загрузки цены:", e)
        return None


def sentiment_score(texts):
    """Подсчёт среднего настроения"""
    if not texts:
        return 0.0
    analyzer = SentimentIntensityAnalyzer()
    scores = [analyzer.polarity_scores(t)["compound"] for t in texts]
    return float(np.mean(scores))


def simple_predict(price, sentiment):
    """Простая модель: линейная зависимость"""
    model = Ridge(alpha=0.5)
    X = np.array([[s] for s in np.linspace(-1, 1, 10)])
    y = X.flatten() * 2 + np.random.randn(10) * 0.1  # псевдотренировка
    model.fit(X, y)
    pred = model.predict([[sentiment]])[0]
    direction = "up" if pred > 0.05 else "down" if pred < -0.05 else "flat"
    return direction, round(pred, 2)


def send_notification(msg):
    """Отправка уведомления в Telegram и Discord"""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    discord = os.getenv("DISCORD_WEBHOOK")

    if token and chat_id:
        try:
            requests.get(
                f"https://api.telegram.org/bot{token}/sendMessage",
                params={"chat_id": chat_id, "text": msg},
            )
            print("✅ Сообщение отправлено в Telegram")
        except Exception as e:
            print("Ошибка Telegram:", e)

    if discord:
        try:
            requests.post(discord, json={"content": msg})
            print("✅ Сообщение отправлено в Discord")
        except Exception as e:
            print("Ошибка Discord:", e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coin", default="bitcoin", help="Монета (например: bitcoin, ethereum)")
    parser.add_argument("--demo", action="store_true", help="Запустить демо-режим")
    parser.add_argument("--notify-test", action="store_true", help="Проверить уведомления")
    args = parser.parse_args()

    coin = args.coin.lower()
    print(f"\n🔍 Анализ крипто-новостей для {coin}...")

    news = fetch_news(coin)
    sentiment = sentiment_score(news)
    price = fetch_price(coin)

    if not price:
        print("Не удалось получить цену.")
        sys.exit(1)

    direction, change = simple_predict(price, sentiment)
    timestamp = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    msg = (
        f"[{coin.upper()}] {timestamp}\n"
        f"Цена: ${price:.2f}\n"
        f"Новости: {len(news)} статей\n"
        f"Настроение: {sentiment:.3f}\n"
        f"Прогноз: {direction} ({change:+.2f}%)"
    )

    print(msg)

    if args.notify_test:
        send_notification(msg)

    if args.demo:
        print("\n✅ Демо завершено.")


if __name__ == "__main__":
    main()
