# crypto_bot_web.py — Cyberpunk UI:
# 1) Analysis Deck (новости, настроение, TP/SL, мини-график, калькулятор)
# 2) Pump.fun Scanner (created/trending без ключей) + простые фильтры, сигналы и калькулятор
# Диагностика сети/API, неоновый лоадер, ₿-бейдж, зачистка системных иконок

import streamlit as st
from streamlit.components.v1 import html as st_html
import requests, feedparser, re, time, math
import numpy as np
import pandas as pd
import altair as alt
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.linear_model import Ridge
from datetime import datetime, timezone

# ========= Переводчик =========
try:
    from deep_translator import GoogleTranslator
    translator_available = True
    translator = GoogleTranslator(source="auto", target="ru")
except Exception:
    translator_available = False
    translator = None

# ========= Конфигурация =========
st.set_page_config(page_title="Crypto Sentiment — Cyberpunk", layout="wide")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (CryptoSentimentBot/1.0)",
    "Accept": "application/json",
}
COINGECKO_URL = "https://api.coingecko.com/api/v3"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}"
COINTELEGRAPH_RSS = "https://cointelegraph.com/rss"
COINDESK_RSS = "https://www.coindesk.com/arc/outboundfeeds/rss/"

# --- Pump.fun (неофициальный фронтовой API, общедоступный) ---
PUMPFUN_API = "https://frontend-api.pump.fun"
# endpoints:
#   /coins/created?offset={offset}&limit={limit}
#   /coins/trending?offset={offset}&limit={limit}

POPULAR_COINS = {
    "Bitcoin": "bitcoin","Ethereum": "ethereum","Solana": "solana","BNB": "binancecoin",
    "Dogecoin": "dogecoin","Shiba Inu": "shiba-inu","Cardano": "cardano","Avalanche": "avalanche-2",
    "Polkadot": "polkadot","Chainlink": "chainlink","Tron": "tron","Litecoin": "litecoin",
    "Ripple (XRP)": "ripple","Uniswap": "uniswap","Stellar": "stellar",
}

# ========= CSS =========
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@400;600;800&display=swap');
:root{
  --bg1:#04040a; --bg2:#0a0a13; --grid:#2a2a3b33; --glass:#0e0e1bcc; --stroke:#2e2e44;
  --neon:#8c3bff; --neon2:#00eaff;
  --txt:#B1B5CC; --txt-strong:#E9ECFF; --muted:#7D81A0;
  --ok:#19ffb0; --bad:#ff4b6b; --warn:#ffc857;
}
html, body, .main { background: radial-gradient(1000px 600px at 40% -10%, #120b2a 0%, #04040a 50%, #010105 100%) !important; }
* { font-family:'Exo 2',sans-serif; color:var(--txt); }
h1,h2,h3,h4{
  text-transform:uppercase; letter-spacing:1.2px; font-weight:800; color:#E9ECFF;
  -webkit-text-stroke:.4px #0b0c16; text-shadow:0 0 4px #8c3bff55;
}
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
label, small, .stCaption { color:#A4A8C2 !important; }
.stApp header, .viewerBadge_container__1QSob, #MainMenu,
div[data-testid="stToolbar"], div[data-testid="stStatusWidget"], div.stDeployButton,
div[title="Accessibility"], img[alt="Accessibility"], button[title="Accessibility"],
svg[aria-label="Accessibility"] { display:none !important; visibility:hidden !important; }
.cy-grid{ position:relative; overflow:hidden; border-radius:18px; border:1px solid var(--stroke);
  background:linear-gradient(160deg,#0a0a17dd,#080812cc);
  box-shadow:0 0 0 1px #272741, 0 8px 40px #00000080, inset 0 0 40px #00000055; }
.cy-grid:before{ content:""; position:absolute; inset:0;
  background:linear-gradient(var(--grid) 1px,transparent 1px) 0 0/28px 28px,
             linear-gradient(90deg,var(--grid) 1px,transparent 1px) 0 0/28px 28px;
  opacity:.22; pointer-events:none; }
.glow{ box-shadow:0 0 25px #8c3bff33, 0 0 80px #00eaff22, inset 0 0 30px #8c3bff22; }
input, textarea, .stTextInput>div>div>input, .stTextArea textarea, .stNumberInput input{
  background:#0b0c18 !important; border:1px solid #363a68 !important; color:#D6DAEE !important;
  border-radius:12px !important; box-shadow:inset 0 0 10px #00000055;
}
.stSlider > div > div > div{ background:linear-gradient(90deg,var(--neon),var(--neon2)) !important; box-shadow:0 0 8px #8c3bff55; }
.stExpander{ border:1px solid #363a68; border-radius:14px; background:#0c0c1cbb; }
hr{ border:none; border-top:1px solid #2a2d3a; margin:12px 0 16px; }
.cy-loader{ position:fixed; top:16px; right:18px; z-index:9999; display:flex; align-items:center; gap:10px; padding:8px 12px;
  background:linear-gradient(180deg,#18132d,#0f1020); border:1px solid #3b3570; border-radius:12px;
  box-shadow:0 0 18px #8c3bff55, inset 0 0 14px #06071a; color:#dfe2ff; font-weight:600; letter-spacing:.6px; }
.cy-dot{width:8px; height:8px; border-radius:50%; background:var(--neon); box-shadow:0 0 10px var(--neon); animation:pulse 1s infinite ease-in-out;}
.cy-bar{position:relative; width:120px; height:6px; border-radius:999px; background:#1a1c32; overflow:hidden; border:1px solid #3b3570;}
.cy-bar:before{content:""; position:absolute; inset:0; background:linear-gradient(90deg,transparent,var(--neon),var(--neon2),transparent);
  width:60px; animation:scan 1.2s infinite linear;}
@keyframes scan{0%{left:-60px} 100%{left:120px}}
@keyframes pulse{0%,100%{transform:scale(1); opacity:1} 50%{transform:scale(1.25); opacity:.6}}
.btc-badge{ position:fixed; top:16px; right:18px; z-index:9998; display:flex; align-items:center; gap:8px; padding:6px 10px;
  background:#0e0f1f; border:1px solid #383c66; border-radius:12px; color:#F2C94C; font-weight:700;
  box-shadow:0 0 14px #f2c94c33, inset 0 0 10px #00000066; }
.btc-badge .dot{ width:8px; height:8px; border-radius:50%; background:#F2C94C; box-shadow:0 0 10px #F2C94C; }
</style>
""", unsafe_allow_html=True)

# Зачистка системной иконки
st_html("""
<script>
(function clean(){
  function kill(){
    const qs = [
      '[data-testid="stStatusWidget"]','div[title="Accessibility"]','img[alt="Accessibility"]',
      'button[title="Accessibility"]','svg[aria-label="Accessibility"]'
    ];
    qs.forEach(sel => document.querySelectorAll(sel).forEach(n => n.remove()));
  }
  kill();
  let tries = 0;
  const t = setInterval(()=>{ kill(); tries++; if(tries>20) clearInterval(t); }, 100);
})();
</script>
""", height=0, width=0)

# ₿-бейдж
st.markdown("""<div class="btc-badge"><span class="dot"></span>₿</div>""", unsafe_allow_html=True)

def show_neon_loader(text="Analyzing…"):
    st.markdown(f"""
        <div class="cy-loader">
          <div class="cy-dot"></div>
          <div class="cy-bar"></div>
          <div>{text}</div>
        </div>""", unsafe_allow_html=True)

# ========= Утилиты =========
def clean_html(t: str) -> str: return re.sub(r"<.*?>", "", t or "").strip()
def shorten(t: str, n=300) -> str: return (t[:n] + "...") if t and len(t) > n else (t or "")
def human_time(ts_ms):
    try:
        dt = datetime.fromtimestamp(int(ts_ms)/1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except: return "—"

# -------------------- Новости/тон --------------------
def fetch_rss(url, src, n=10, timeout=6):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout); r.raise_for_status()
        d = feedparser.parse(r.content); out=[]
        for e in d.entries[:n]:
            title = clean_html(e.get("title","")); s = clean_html(e.get("summary",""))
            out.append((f"[{src}]", title, shorten(title+" — "+s, 300)))
        return out
    except Exception:
        return []

def fetch_google_news(q, n=12, timeout=6):
    return fetch_rss(GOOGLE_NEWS_RSS.format(query=requests.utils.quote(q)), "GoogleNews", n, timeout)

def collect_news(q):
    items = fetch_google_news(q, 15) + fetch_rss(COINTELEGRAPH_RSS, "Cointelegraph", 8) + fetch_rss(COINDESK_RSS, "CoinDesk", 8)
    ql = q.lower(); filtered, seen_short = [], set()
    for s,t,sh in items:
        combined = (t+" "+sh).lower()
        if ql in combined and len(sh)>30 and sh.lower() not in seen_short:
            filtered.append((s,t,sh)); seen_short.add(sh.lower())
        if len(filtered)>=80: break
    return filtered

@st.cache_data(ttl=60)
def fetch_price(cid):
    try:
        r = requests.get(f"{COINGECKO_URL}/simple/price", params={"ids": cid, "vs_currencies": "usd"}, timeout=8).json()
        return r.get(cid, {}).get("usd", None)
    except Exception: return None

def sentiment_score(texts):
    a = SentimentIntensityAnalyzer()
    return float(np.mean([a.polarity_scores(t)["compound"] for t in texts])) if texts else 0.0

def simple_predict(s):
    m = Ridge(alpha=0.5); X = np.array([[x] for x in np.linspace(-1, 1, 11)])
    m.fit(X, X.flatten()*2.0); p = m.predict([[s]])[0]
    return ("up" if p>0.05 else "down" if p<-0.05 else "flat"), float(p)

def trading_signal(p, d, c, lev=None):
    lv = max(1, min(5, int(abs(c)*10))) if lev is None else max(1, min(10, int(lev)))
    if d=="up" and c>0.05:
        t=p*(1+c*lv); s=p*(1-0.02*lv); return f"LONG x{lv} | TP: ${t:.2f} | SL: ${s:.2f}", "var(--ok)", lv
    if d=="down" and c<-0.05:
        t=p*(1+c*lv); s=p*(1+0.02*lv); return f"SHORT x{lv} | TP: ${t:.2f} | SL: ${s:.2f}", "var(--bad)", lv
    return "HOLD", "var(--warn)", 1

def cg_search_id(query: str):
    try:
        r = requests.get(f"{COINGECKO_URL}/search", params={"query": query}, timeout=8); r.raise_for_status()
        data = r.json().get("coins", []);  ql=query.lower().strip()
        if not data: return None
        exact = [c for c in data if c.get("id")==ql or c.get("name","").lower()==ql or c.get("symbol","").lower()==ql]
        pick = exact[0] if exact else data[0];  return pick.get("id")
    except Exception: return None

def resolve_coin_input(inp: str):
    s = (inp or "").strip()
    if not s: return ("id","bitcoin")
    if s.startswith("0x") and len(s)>20: return ("contract",("ethereum",s))
    if len(s)>=32 and not s.startswith("0x") and s.isalnum(): return ("contract",("solana",s))
    return ("id", s)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_market_series_smart(user_input: str, days=7, interval="hourly"):
    def df_from_prices(prices):
        if not prices: return pd.DataFrame(columns=["date","price"])
        df = pd.DataFrame(prices, columns=["ts","price"]); df["date"]=pd.to_datetime(df["ts"], unit="ms")
        return df[["date","price"]]
    kind, val = resolve_coin_input(user_input)
    if kind=="contract":
        maybe_id = cg_search_id(val[1]);  user_input = maybe_id or user_input
        if maybe_id is None: return pd.DataFrame(columns=["date","price"])
    coin_id=str(user_input).strip().lower()
    if " " in coin_id or any(c.isupper() for c in str(user_input)) or len(coin_id)<=4:
        maybe=cg_search_id(user_input);  coin_id=maybe or coin_id
    try:
        url=f"{COINGECKO_URL}/coins/{coin_id}/market_chart"
        for params in (
            {"vs_currency":"usd","days":days,"interval":interval},
            {"vs_currency":"usd","days":3,"interval":interval},
            {"vs_currency":"usd","days":1,"interval":interval},
            {"vs_currency":"usd","days":days,"interval":"daily"},
        ):
            r=requests.get(url, params=params, timeout=8)
            if r.status_code==200:
                df=df_from_prices(r.json().get("prices", []))
                if not df.empty: return df
    except Exception: pass
    return pd.DataFrame(columns=["date","price"])

def estimate_atr_pct_from_series(df: pd.DataFrame):
    if df.empty or len(df)<5: return 0.6
    p=df["price"].values; diffs=np.diff(p)
    return float(np.median(np.abs(diffs/p[:-1])*100))

def build_trade_plan(price, side, atr, strength):
    abs_ch=abs(strength)
    risk=1 if abs_ch<0.2 else 2 if abs_ch<0.5 else 3 if abs_ch<0.9 else 4 if abs_ch<1.3 else 5
    m=1.2+0.3*(risk-1)+0.2*abs_ch
    tp1p,tp2p,tp3p=atr*(2*m), atr*(3.5*m), atr*(5*m)
    slp=max(atr*(1.5*m),0.5)
    sgn=1 if side=="LONG" else -1
    tp1,tp2,tp3=[price*(1+sgn*p/100) for p in (tp1p,tp2p,tp3p)]
    sl=price*(1 - sgn*slp/100)
    vol=max(0.2,atr); h1,h2,h3=(tp1p/vol*1.2, tp2p/vol*1.3, tp3p/vol*1.4)
    def hor(h): return "скальпинг" if h<=2 else "интрадей" if h<=8 else "свинг" if h<=36 else "позиционно"
    horizons={"TP1":f"{hor(h1)} ~{h1:.1f}ч","TP2":f"{hor(h2)} ~{h2:.1f}ч","TP3":f"{hor(h3)} ~{h3:.1f}ч"}
    levels=[{"L":"TP1","P":tp1,"M":tp1p},{"L":"TP2","P":tp2,"M":tp2p},{"L":"TP3","P":tp3,"M":tp3p},{"L":"SL","P":sl,"M":slp}]
    return levels,horizons,atr

# ========= Диагностика =========
def _probe(url, params=None, timeout=10):
    try:
        r = requests.get(url, params=params or {}, headers=HEADERS, timeout=timeout)
        return {"ok": r.status_code==200, "status": r.status_code, "len": len(r.text), "url": r.url}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}

# ========= Pump.fun API =========
@st.cache_data(ttl=15)
def pump_fetch_created(offset=0, limit=50):
    url = f"{PUMPFUN_API}/coins/created"
    r = requests.get(url, params={"offset": offset, "limit": limit}, headers=HEADERS, timeout=15)
    if r.status_code != 200: return [], {"ok": False, "status": r.status_code, "url": r.url}
    data = r.json() or []
    return data, {"ok": True, "status": 200, "url": r.url, "count": len(data)}

@st.cache_data(ttl=30)
def pump_fetch_trending(offset=0, limit=50):
    url = f"{PUMPFUN_API}/coins/trending"
    r = requests.get(url, params={"offset": offset, "limit": limit}, headers=HEADERS, timeout=15)
    if r.status_code != 200: return [], {"ok": False, "status": r.status_code, "url": r.url}
    data = r.json() or []
    return data, {"ok": True, "status": 200, "url": r.url, "count": len(data)}

def pump_norm(item: dict):
    # Поля Pump.fun часто меняются; защищаемся дефолтами
    symbol = (item.get("symbol") or item.get("token_symbol") or "").upper()
    name   = item.get("name") or item.get("token_name") or symbol or "UNKNOWN"
    addr   = item.get("mint") or item.get("address") or item.get("token_address") or ""
    price  = item.get("usd_market_cap")  # иногда приходит mc, иногда price — нормализуем
    if price and price > 0 and item.get("supply"):
        est_price = float(price)/float(item.get("supply"))
    else:
        est_price = float(item.get("price_usd") or item.get("usd_price") or 0.0)
    created = item.get("created_timestamp") or item.get("createdAt") or item.get("created_at")
    # активность (эвристики; у Pump.fun разные поля)
    tx5m = item.get("txns_5m") or item.get("tx_5m") or item.get("txn_5m") or 0
    vol5 = item.get("volume_5m") or item.get("vol_5m") or 0.0
    liq  = item.get("liquidity_usd") or item.get("liquidity") or 0.0
    mc   = item.get("usd_market_cap") or item.get("market_cap_usd") or 0.0
    chg5 = item.get("price_change_5m") or item.get("chg_5m") or 0.0
    return {
        "name": name, "symbol": symbol, "address": addr, "price_usd": float(est_price or 0.0),
        "liquidity_usd": float(liq or 0.0), "marketcap_usd": float(mc or 0.0),
        "txns_5m": int(tx5m or 0), "volume_5m": float(vol5 or 0.0), "change_5m": float(chg5 or 0.0),
        "created": created
    }

def meme_score(row):
    liq = float(row.get("liquidity_usd", 0))
    vol5 = float(row.get("volume_5m", 0))
    tx5  = int(row.get("txns_5m", 0))
    liq_score = min(100.0, liq/20000*100.0)
    vol_score = min(100.0, vol5/5000*100.0)
    tx_score  = min(100.0, tx5/50*100.0)
    return round(0.25*liq_score + 0.35*vol_score + 0.40*tx_score, 1)

def meme_signal(row):
    price = row.get("price_usd", 0.0) or 0.0
    chg5  = row.get("change_5m", 0.0) or 0.0
    side  = "LONG" if chg5 >= 0 and row.get("txns_5m",0)>0 else ("SHORT" if chg5 < 0 else "HOLD")
    # быстрая вола по активности/ликвидности
    liq = max(1.0, row.get("liquidity_usd", 0.0))
    vol5 = max(0.0, row.get("volume_5m", 0.0))
    activity = max(0.0, min(1.0, row.get("txns_5m",0)/60.0))
    base = (vol5/liq)*100.0
    atrp = float(min(max(base*(1+0.7*activity), 0.4), 12.0))
    if side == "HOLD" or price<=0:
        return {"side":"HOLD","tp1":price,"tp2":price,"sl":price,"atrp":atrp}
    sgn = 1 if side=="LONG" else -1
    tp1p,tp2p,slp = atrp*0.6, atrp*1.2, max(atrp*0.5, 0.5)
    return {
        "side": side,
        "tp1": price*(1+sgn*tp1p/100), "tp2": price*(1+sgn*tp2p/100),
        "sl": price*(1-sgn*slp/100), "atrp": atrp,
        "tp1p": tp1p, "tp2p": tp2p, "slp": slp
    }

# ========= Session =========
st.session_state.setdefault("watchlist", {})
st.session_state.setdefault("analyze", False)

# ========= Header =========
st.markdown('<div class="cy-grid glow" style="padding:18px 20px; margin-bottom:16px">', unsafe_allow_html=True)
st.markdown("<h1>CRYPTO SENTIMENT — DΞCK</h1>", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ========= Tabs =========
tab_deck, tab_pump = st.tabs(["📊 Analysis Deck", "🚀 Pump.fun Scanner"])

# ===================== Pump.fun Scanner =====================
with tab_pump:
    st.markdown('<div class="cy-grid glow" style="padding:14px">', unsafe_allow_html=True)

    left, right = st.columns([2,1])
    with left:
        mode = st.radio("Лента", ["Созданные (новые)", "Трендовые"], horizontal=True)
        pages = st.slider("Страниц (по 50)", 1, 5, 2)
        min_liq = st.number_input("Мин. ликвидность, $", min_value=0.0, value=0.0, step=500.0)
        min_score = st.slider("Мин. скор (0–100)", 0, 100, 0, step=5)
        max_items = st.slider("Сколько карточек показать", 10, 100, 30, step=5)
        force_show = st.checkbox("Всегда что-то показывать (ослабить фильтры при пустом результате)", value=True)
        st.caption("Совет: начни с 0 порогов — должен показать поток.")
    with right:
        if st.button("🔄 Обновить"):
            st.cache_data.clear()

    # Диагностика API
    with st.expander("🧪 Диагностика API (Pump.fun)"):
        if st.button("Проверить доступность"):
            pr1 = _probe(f"{PUMPFUN_API}/coins/created", {"offset":0,"limit":5})
            pr2 = _probe(f"{PUMPFUN_API}/coins/trending", {"offset":0,"limit":5})
            st.write("created →", pr1)
            st.write("trending →", pr2)

    # Загрузка
    all_items = []
    diag = []
    for pg in range(pages):
        if mode.startswith("Создан"):
            chunk, info = pump_fetch_created(offset=pg*50, limit=50)
        else:
            chunk, info = pump_fetch_trending(offset=pg*50, limit=50)
        diag.append(info)
        all_items += [pump_norm(x) for x in (chunk or [])]

    with st.expander("📊 Поток (сколько пришло)"):
        st.write(diag)

    df = pd.DataFrame(all_items)
    # Классические мягкие фильтры
    if not df.empty:
        df = df[df["price_usd"].fillna(0) > 0]
        if min_liq>0:
            df = df[df["liquidity_usd"].fillna(0) >= min_liq]
        # эвристический скоринг
        df["score"] = df.apply(meme_score, axis=1)
        if min_score>0:
            df = df[df["score"] >= min_score]
        # активность первична
        df = df.sort_values(by=["txns_5m","volume_5m","score","liquidity_usd"], ascending=[False,False,False,False])

    if df.empty and force_show and len(all_items)>0:
        tmp = pd.DataFrame(all_items)
        tmp = tmp[tmp["price_usd"].fillna(0) > 0]
        tmp["score"] = tmp.apply(meme_score, axis=1)
        df = tmp.sort_values(by=["txns_5m","volume_5m","score"], ascending=False)

    raw_toggle = st.checkbox("Показать RAW-таблицу", value=False)
    if raw_toggle:
        st.dataframe(df.head(200) if not df.empty else pd.DataFrame(all_items).head(200))

    rows = df.head(max_items).to_dict(orient="records") if not df.empty else []
    if not rows:
        st.info("Поток пуст. Попробуй «Созданные (новые)», pages=3–5, пороги = 0.")
    else:
        for i, p in enumerate(rows, 1):
            sig = meme_signal(p)
            side = sig["side"]
            c1, c2, c3, c4 = st.columns([3,3,3,2])

            with c1:
                st.markdown(f"**{i}. {p.get('symbol') or 'UNKNOWN'} — {p.get('name','')}**")
                st.caption(f"Mint: `{(p.get('address','')[:10])}…` · {human_time(p.get('created'))}")
                st.write(f"Цена: **${p.get('price_usd',0):.10f}**  |  Ликв.: ~${p.get('liquidity_usd',0):,.0f}  |  "
                         f"5м сделки: {p.get('txns_5m',0)}  |  5м объём: ~${p.get('volume_5m',0):,.0f}")

            with c2:
                st.markdown("**Сигнал (скальп)**")
                if side == "HOLD":
                    st.write("HOLD — активности/дисбаланса мало.")
                else:
                    st.write(f"{'🟢 LONG' if side=='LONG' else '🔴 SHORT'}  | локальная вола ≈ {sig['atrp']:.2f}%")
                    st.write(f"TP1: ${sig['tp1']:.8f} (~{sig['tp1p']:.2f}%)")
                    st.write(f"TP2: ${sig['tp2']:.8f} (~{sig['tp2p']:.2f}%)")
                    st.write(f"SL:  ${sig['sl']:.8f}  (~{sig['slp']:.2f}%)")

            with c3:
                st.markdown("**Калькулятор P/L (быстрый)**")
                amt = st.number_input(f"Маржа USD · #{i}", min_value=0.0, value=50.0, step=10.0, key=f"pf_amt_{i}")
                lev = st.number_input(f"Плечо x · #{i}", min_value=1.0, value=5.0, step=1.0, key=f"pf_lev_{i}")
                side_sel = st.radio(f"Side · #{i}", ["LONG","SHORT"], index=0 if side!="SHORT" else 1, horizontal=True, key=f"pf_side_{i}")
                target_mode = st.radio(f"Цель · #{i}", ["Цена монеты (USD)", "Стоимость позиции (USD)"], index=0, horizontal=True, key=f"pf_mode_{i}")

                target_price=None
                if target_mode=="Цена монеты (USD)":
                    tp_in = st.number_input(f"Цель, $ · #{i}", min_value=0.0, value=float(sig["tp1"]) if side!="HOLD" else 0.0, step=0.000001, key=f"pf_tp_{i}")
                    if tp_in>0: target_price=float(tp_in)
                else:
                    tv_in = st.number_input(f"Цель позиции, $ · #{i}", min_value=0.0, value=0.0, step=10.0, key=f"pf_tv_{i}")
                    notional = amt*lev
                    if tv_in>0 and notional>0 and p.get("price_usd",0)>0:
                        qty = notional / max(p["price_usd"], 1e-12)
                        target_price = float(tv_in/qty)

                if amt>0 and lev>=1 and target_price and target_price>0 and p.get("price_usd",0)>0:
                    notional = amt*lev
                    sgn = 1 if side_sel=="LONG" else -1
                    pl = ((target_price - p["price_usd"]) / p["price_usd"]) * notional * sgn
                    pct = (target_price - p["price_usd"]) / p["price_usd"] * 100
                    st.success(f"P/L: {pl:+.2f} USD ({pct:+.2f}%) @ {target_price:.8f}")
                else:
                    st.caption("Задай маржу/плечо/цель — и увидишь P/L.")

            with c4:
                if st.button("В watchlist", key=f"pf_add_{p.get('address','')}{i}"):
                    st.session_state["watchlist"][p.get("address", f"k{i}")] = p
                    st.success("Добавлено")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="cy-grid" style="padding:14px; margin-top:12px">', unsafe_allow_html=True)
    st.markdown("### ⭐ Watchlist")
    if not st.session_state["watchlist"]:
        st.caption("Пусто. Добавь из списка выше.")
    else:
        for key, info in list(st.session_state["watchlist"].items()):
            cols = st.columns([3,2,2,2,1])
            with cols[0]:
                st.markdown(f"**{info.get('symbol','UNK')} — {info.get('name','')}**  \n`{(info.get('address','')[:10])}…`")
            with cols[1]:
                st.write(f"Цена: ${info.get('price_usd',0):.10f}")
            with cols[2]:
                st.write(f"Ликв.: ~${info.get('liquidity_usd',0):,.0f}")
            with cols[3]:
                st.write(f"5м объём: ~${info.get('volume_5m',0):,.0f}")
            with cols[4]:
                if st.button("✖", key=f"pf_del_{key}"):
                    del st.session_state["watchlist"][key]
                    st.experimental_rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ===================== Analysis Deck =====================
with tab_deck:
    with st.container():
        c1, c2 = st.columns([2,1])
        with c1:
            st.markdown('<div class="cy-grid glow" style="padding:14px">', unsafe_allow_html=True)
            sel = st.selectbox("Популярные монеты", ["(выбрать)"] + list(POPULAR_COINS.keys()))
            inp = st.text_input("Или Coin ID / контракт (CA)")
            if sel != "(выбрать)":
                coin_name, cid = sel, POPULAR_COINS[sel]
            elif (inp or "").strip():
                coin_name, cid = inp.strip(), inp.strip()
            else:
                coin_name, cid = "Bitcoin", "bitcoin"

            auto_lev = st.checkbox("Авто-плечо", value=True)
            lev = None if auto_lev else st.slider("Плечо (x)", 1, 10, 2)
            if st.button("🔍 Запустить анализ", type="primary"): st.session_state["analyze"] = True
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="cy-grid" style="padding:14px; height:100%">', unsafe_allow_html=True)
            st.markdown("### Состояние")
            st.markdown(f"- Переводчик: **{'включён' if translator_available else 'нет'}**")
            st.markdown("- Источники: GoogleNews, CoinDesk, Cointelegraph")
            st.markdown("- Цены/график: CoinGecko API")
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    if st.session_state.get("analyze"):
        loader_placeholder = st.empty()
        with loader_placeholder: show_neon_loader("Analyzing news & price…")

        st.markdown('<div class="cy-grid glow" style="padding:16px">', unsafe_allow_html=True)
        st.markdown(f"## {coin_name} — сводка и уровни")

        # Новости + перевод
        news = collect_news(coin_name)
        def translate_items(items):
            if not translator_available: return items
            out=[]
            for s,t,sh in items:
                try:
                    tr = translator.translate(f"{t}. {sh}")
                    if "." in tr:
                        a,b = tr.split(".",1); out.append((s, a.strip(), shorten(b.strip(), 300)))
                    else:
                        out.append((s, tr.strip(), tr.strip()))
                except Exception:
                    out.append((s,t,sh))
                time.sleep(0.02)
            return out
        news_tr = translate_items(news)

        texts = [x[2] for x in news_tr]; sent = sentiment_score(texts)
        direction, change = simple_predict(sent)
        price = fetch_price(str(cid).lower())

        if price is None:
            st.error("Не удалось получить цену. Проверь ID/контракт или попробуй позже.")
        else:
            sigtxt, color, lv = trading_signal(price, direction, change, lev)
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("Цена", f"${price:.8f}"); m2.metric("Новостей", len(news_tr))
            m3.metric("Настроение", f"{sent:+.3f}"); m4.metric("Прогноз %", f"{change:+.3f}")
            st.markdown(f"<div style='font-weight:700'>Сигнал: <span style='color:{color}'>{sigtxt}</span></div>", unsafe_allow_html=True)

            series = fetch_market_series_smart(cid, days=7, interval="hourly")
            atr_pct = estimate_atr_pct_from_series(series)
            default_side = "LONG" if direction=="up" else "SHORT" if direction=="down" else "LONG"
            levels, horizons, atr = build_trade_plan(price, default_side, atr_pct, change)

            L,R = st.columns([3,2])
            with L:
                st.markdown("### 🎯 Уровни сделки")
                for r in levels: st.markdown(f"- **{r['L']}**: `${r['P']:.6f}`  _(Δ{r['M']:.2f}% )_")
            with R:
                st.markdown("### ⏳ Горизонт удержания")
                for k,v in horizons.items(): st.markdown(f"- {k}: {v}")
                st.caption(f"Волатильность (≈ATR): ~{atr:.2f}%/ч")

            st.markdown("### 📈 Мини-график (7д, почасовой)")
            try:
                st.caption(f"Точек данных: {len(series)}")
                if not series.empty:
                    series = series.dropna().copy()
                    series["date"] = pd.to_datetime(series["date"], errors="coerce")
                    series["price"] = pd.to_numeric(series["price"], errors="coerce")
                    series = series.dropna()
                    try: alt.data_transformers.disable_max_rows()
                    except Exception: pass
                    base = alt.Chart(series).mark_line().encode(
                        x=alt.X('date:T', title=''), y=alt.Y('price:Q', title='USD')
                    ).properties(height=260)
                    lines_df = pd.DataFrame({"label":[r["L"] for r in levels], "y":[r["P"] for r in levels]})
                    rules  = alt.Chart(lines_df).mark_rule(strokeDash=[4,4]).encode(y='y:Q')
                    labels = alt.Chart(lines_df).mark_text(align='left', dx=5, dy=-6).encode(y='y:Q', text='label:N')
                    st.altair_chart(base + rules + labels, use_container_width=True)
                else:
                    st.caption("Нет данных для графика (токен может быть слишком новым).")
            except Exception as e:
                st.warning(f"Altair не отрисовал график: {e}. Фолбэк.")
                try:
                    if not series.empty:
                        st.line_chart(series.rename(columns={"date":"index"}).set_index("index")["price"])
                    else:
                        st.caption("Нет данных.")
                except Exception as e2:
                    st.error(f"График недоступен: {e2}")

            # Калькулятор P/L
            st.markdown("### 💰 Калькулятор P/L")
            amount = st.number_input("Сумма позиции (маржа, USD)", min_value=0.0, value=100.0, step=10.0, key="calc_amount",
                                     help="Это маржа. Объём позиции = маржа × плечо.")
            leverage_default = float(max(1, lv or 1))
            leverage = st.number_input("Плечо (x)", min_value=1.0, value=leverage_default, step=1.0, key="calc_lev")
            calc_side = st.radio("Сторона сделки для расчёта", ["LONG", "SHORT"], index=0 if default_side=="LONG" else 1, horizontal=True)
            target_mode = st.radio("Тип цели", ["Цена монеты (USD)", "Стоимость позиции (USD)"], index=0, horizontal=True)

            target_price = None
            if target_mode == "Цена монеты (USD)":
                tp_input = st.number_input("Своя цель цены (USD)", min_value=0.0, value=0.0, step=0.000001, key="calc_target_price")
                if tp_input > 0: target_price = float(tp_input)
            else:
                tv_input = st.number_input("Желаемая стоимость позиции (USD)", min_value=0.0, value=0.0, step=10.0, key="calc_target_value")
                notional = amount * leverage
                if tv_input > 0 and notional > 0:
                    qty = notional / max(price, 1e-12)
                    target_price = float(tv_input / qty)

            if amount <= 0:
                st.info("Введите положительную **Сумму позиции (маржу)**.")
            elif leverage < 1:
                st.warning("Плечо должно быть ≥ 1.")
            else:
                notional = amount * leverage
                st.caption(f"Текущий объём позиции (notional): ≈ **${notional:,.2f}**")

                st.markdown("**Результаты по уровням TP/SL:**")
                sign = 1 if calc_side == "LONG" else -1
                for r in levels:
                    pl = ((r["P"] - price) / price) * notional * sign
                    lbl = "✅" if r["L"].startswith("TP") else "❌"
                    st.write(f"{lbl} {r['L']}: {pl:+.2f} USD — цель {r['P']:.6f} (от входа {((r['P']-price)/price*100):+.2f}%)")

                st.markdown("**Результат по твоей цели:**")
                if target_price is None or target_price <= 0:
                    st.caption("Задай положительную цель — либо цену монеты, либо стоимость позиции.")
                else:
                    pl_custom = ((target_price - price) / price) * notional * (1 if calc_side=="LONG" else -1)
                    pct = (target_price - price) / price * 100
                    outcome = "прибыль" if pl_custom >= 0 else "убыток"
                    st.success(f"{outcome.capitalize()}: {pl_custom:+.2f} USD ({pct:+.2f}%) при цели цены {target_price:.6f} USD.")

        st.markdown('</div>', unsafe_allow_html=True)
        loader_placeholder.empty()
