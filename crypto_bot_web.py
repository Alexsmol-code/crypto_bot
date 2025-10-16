# crypto_bot_web.py
import streamlit as st
import requests, feedparser, re, time, datetime as dt
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.linear_model import Ridge

# -------------------- Переводчик --------------------
try:
    from googletrans import Translator
    translator_available = True
    translator = Translator()
except ImportError:
    translator_available = False
    translator = None

# -------------------- Конфигурация --------------------
HEADERS = {"User-Agent": "Mozilla/5.0"}
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}"
COINTELEGRAPH_RSS = "https://cointelegraph.com/rss"
COINDESK_RSS = "https://www.coindesk.com/arc/outboundfeeds/rss/"
COINGECKO_URL = "https://api.coingecko.com/api/v3"

POPULAR_COINS = {
    "Bitcoin": "bitcoin",
    "Ethereum": "ethereum",
    "Ripple (XRP)": "ripple",
    "Cardano": "cardano",
    "Solana": "solana",
    "Dogecoin": "dogecoin",
    "Litecoin": "litecoin",
    "Polkadot": "polkadot",
    "Chainlink": "chainlink",
    "Avalanche": "avalanche-2",
    "Shiba Inu": "shiba-inu",
    "Uniswap": "uniswap",
    "Tron": "tron",
    "Stellar": "stellar",
    "Bitcoin Cash": "bitcoin-cash",
}

CHAINS = ["ethereum", "binance-smart-chain", "solana"]

# -------------------- Утилиты --------------------
def clean_html(text):
    if not text: return ""
    text = re.sub(r'<.*?>', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def shorten(text, max_len=220):
    if not text: return ""
    if len(text) <= max_len: return text
    cut = text[:max_len].rsplit('.',1)[0]
    return (cut.strip() + "...") if cut else text[:max_len].strip()+"..."

# -------------------- Источники --------------------
def fetch_rss(url, source_name, max_items=10):
    try:
        d = feedparser.parse(url)
        out=[]
        for e in d.entries[:max_items]:
            title = clean_html(e.get("title",""))
            summary = clean_html(e.get("summary",""))
            short = shorten(title+" — "+summary)
            out.append((f"[{source_name}]", title, short))
        return out
    except: return []

def fetch_google_news(query):
    return fetch_rss(GOOGLE_NEWS_RSS.format(query=requests.utils.quote(query)),"GoogleNews",12)

def collect_news(query, max_total=80):
    items=[]
    items += fetch_google_news(query)
    items += fetch_rss(COINTELEGRAPH_RSS,"Cointelegraph",6)
    items += fetch_rss(COINDESK_RSS,"Coindesk",6)
    # фильтр по имени монеты
    qlow = query.lower()
    filtered=[]
    seen=set()
    for src, title, short in items:
        combined = (title+" "+short).lower()
        if qlow in combined and len(short)>30:
            k=short.lower()
            if k not in seen:
                filtered.append((src,title,short))
                seen.add(k)
            if len(filtered)>=max_total: break
    return filtered

def translate_items(items):
    if not translator_available: return items
    out=[]
    for src,title,short in items:
        combined = f"{title}. {short}"
        try:
            tr = translator.translate(combined,dest="ru").text
            if "." in tr:
                first, rest = tr.split(".",1)
                tr_title=first.strip()
                tr_short=(rest.strip()[:300]+"...") if rest.strip() else tr_title
            else: tr_title=tr.strip(); tr_short=tr_title
            out.append((src,tr_title,tr_short))
        except: out.append((src,title,short))
        time.sleep(0.1)
    return out

# -------------------- Price & Sentiment --------------------
def fetch_price(coin_id="bitcoin"):
    try:
        r=requests.get(f"{COINGECKO_URL}/simple/price", params={"ids":coin_id,"vs_currencies":"usd"},timeout=10).json()
        return r.get(coin_id,{}).get("usd",None)
    except: return None

def sentiment_score(texts):
    if not texts: return 0.0
    analyzer=SentimentIntensityAnalyzer()
    return float(np.mean([analyzer.polarity_scores(t)["compound"] for t in texts]))

def simple_predict(sentiment):
    model=Ridge(alpha=0.5)
    X=np.array([[s] for s in np.linspace(-1,1,11)])
    y=X.flatten()*2.0
    model.fit(X,y)
    pred=model.predict([[sentiment]])[0]
    direction="up" if pred>0.05 else "down" if pred<-0.05 else "flat"
    return direction,float(pred)

def trading_signal(price,direction,change,user_lev=None):
    lev = max(1,min(5,int(abs(change)*10))) if user_lev is None else max(1,min(10,int(user_lev)))
    if direction=="up" and change>0.05:
        target = price*(1+change*lev)
        stop = price*(1-0.02*lev)
        return f"LONG x{lev} | TP: ${target:.2f} | SL: ${stop:.2f}","green",lev
    elif direction=="down" and change<-0.05:
        target = price*(1+change*lev)
        stop = price*(1+0.02*lev)
        return f"SHORT x{lev} | TP: ${target:.2f} | SL: ${stop:.2f}","red",lev
    else:
        return "HOLD","gray",1

# -------------------- Streamlit UI --------------------
st.set_page_config(page_title="Crypto Sentiment Bot", layout="wide")
st.title("📊 Crypto Sentiment Bot — новости + краткий перевод")

col1,col2 = st.columns([2,1])
with col1:
    # Список популярных монет
    popular = list(POPULAR_COINS.keys())
    selected = st.selectbox("Популярные монеты:", ["(выбрать)"]+popular)
    # Одна строка поиска
    search_input = st.text_input("Или введите coin id / Contract Address (CA):","")

    coin_display, coin_id = "Bitcoin","bitcoin"
    # Популярная монета
    if selected!="(выбрать)":
        coin_display=selected
        coin_id=POPULAR_COINS[selected]
    # Пользовательский ввод
    elif search_input.strip():
        inp = search_input.strip()
        # Если похоже на CA (0x...), пробуем найти по сетям
        if inp.startswith("0x") and len(inp)>20:
            found=False
            for ch in CHAINS:
                try:
                    r = requests.get(f"https://api.coingecko.com/api/v3/coins/{ch}/contract/{inp}", timeout=5).json()
                    if "id" in r:
                        coin_id = r["id"]
                        coin_display = r.get("name", inp)
                        found=True
                        break
                except: continue
            if not found:
                st.warning("Не удалось определить токен по CA. Используется адрес как coin_id.")
                coin_id=inp
                coin_display=inp
        else:
            # Иначе используем как coin id
            coin_id=inp
            coin_display=inp

    auto_lev=st.checkbox("Авто-плечо",value=True)
    lev=None if auto_lev else st.slider("Плечо (x):",1,10,2)
    analyze=st.button("🔍 Запустить анализ")

with col2:
    if translator_available:
        st.success("Переводчик: включён")
    else:
        st.warning("Переводчик: отсутствует (установите googletrans==4.0.0-rc1)")

st.markdown("---")

if analyze:
    st.info(f"Анализ для **{coin_display}**...")
    t0=time.time()
    items = collect_news(coin_id)
    items_tr = translate_items(items)

    st.markdown("### 🔽 Краткая лента новостей (RU) — можно редактировать")
    editable_news=[]
    for src, t_title, t_short in items_tr[:30]:
        text_area = st.text_area(label=f"{src} {t_title}", value=t_short, height=80)
        editable_news.append((src,t_title,text_area))

    texts=[t_short for _,_,t_short in editable_news]
    sent=sentiment_score(texts)
    dirc, ch=simple_predict(sent)
    price=fetch_price(coin_id)
    if price is None:
        st.error("Не удалось получить цену.")
    else:
        sig,color,used_lev = trading_signal(price,dirc,ch,lev)
        ts = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        st.subheader(f"{coin_display} — сигнал и новости")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Цена (USD)",f"${price:.4f}")
        c2.metric("Новостей",len(items_tr))
        c3.metric("Настроение",f"{sent:+.3f}")
        c4.metric("Прогноз %",f"{ch:+.3f}")
        st.markdown(f"**Сигнал:** <span style='color:{color};font-weight:bold'>{sig}</span>",unsafe_allow_html=True)
        st.caption(f"Плечо: x{used_lev}. Время: {ts}")
        st.caption(f"Время анализа: {time.time()-t0:.1f} сек.")
