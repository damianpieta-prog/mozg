import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import numpy as np
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# ==========================================
# KONFIGURACJA STRONY
# ==========================================
st.set_page_config(page_title="MÓZG TRADERA", layout="wide", page_icon="🧠")

# ==========================================
# 📥 FUNKCJE GLOBALNE
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zAE2mUbcVwBfI78f7v3_4K20Z5ffXymyrIcqcyadF4M/export?format=csv&gid=0"

@st.cache_data(ttl=900)
def load_tickers():
    try:
        df = pd.read_csv(SHEET_URL)
        if df.empty: return []
        tickers = df.iloc[:, 0].dropna().astype(str).tolist()
        clean = []
        for t in tickers:
            t = t.strip()
            # Mapowanie
            if t == "DAX": t = "^GDAXI"
            if t == "WIG20": t = "WIG20.WA"
            if t == "GOLD": t = "GLD"
            if t in ["BTC", "BITCOIN"]: t = "BTC-USD"
            if len(t) > 1: clean.append(t)
        return sorted(list(set(clean)))
    except: return []

@st.cache_data(ttl=900)
def get_bulk_data(tickers_list, period="2y"):
    if not tickers_list: return None
    try:
        # Pobieranie grupowe (szybkie)
        return yf.download(tickers_list, period=period, group_by='ticker', progress=False, threads=True)
    except: return None

def extract_ticker_data(bulk, ticker):
    try:
        if isinstance(bulk.columns, pd.MultiIndex): df = bulk[ticker].dropna()
        else: df = bulk.dropna()
        if len(df)<100: return None
        return df
    except: return None

# --- WYSYŁANIE MAILA Z POZIOMU APLIKACJI ---
def send_email_alert(signals_list):
    if "EMAIL_USER" not in st.secrets:
        st.error("❌ Brak konfiguracji maila w Secrets!")
        return
    
    sender = st.secrets["EMAIL_USER"]
    password = st.secrets["EMAIL_PASSWORD"]
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = sender
    msg['Subject'] = f"🚀 RAPORT RĘCZNY: {len(signals_list)} okazji (True Cross)"
    
    html = """
    <html><body>
    <h2>Skaner Ręczny - Świeże Sygnały</h2>
    <p>Strategia: Trend (EMA100>200) + Timing (EMA9 przebija EMA17)</p>
    <table border='1' style='border-collapse: collapse; width: 100%;'>
    <tr style='background-color: #f2f2f2;'><th>Ticker</th><th>Cena</th><th>RSI</th><th>Status</th></tr>
    """
    for s in signals_list:
        html += f"<tr><td>{s['Ticker']}</td><td>{s['Cena']:.2f}</td><td>{s['RSI']:.1f}</td><td>{s['Sygnał']}</td></tr>"
    html += "</table></body></html>"
    msg.attach(MIMEText(html, 'html'))
    
    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(sender, password)
        s.send_message(msg)
        s.quit()
        st.success("📧 Mail wysłany pomyślnie!")
    except Exception as e: st.error(f"Błąd: {e}")

# ==========================================
# 🎛️ MENU
# ==========================================
st.sidebar.title("🎛️ NAWIGACJA")
app_mode = st.sidebar.selectbox("Wybierz moduł:", 
    ["🔍 SZYBKI AUDYT (One-Pager)", "🚀 SKANER (True Cross)", "📊 BACKTESTER"]
)

# ==========================================
# MODUŁ 1: ONE PAGER
# ==========================================
if app_mode == "🔍 SZYBKI AUDYT (One-Pager)":
    st.title("🔍 SZYBKI AUDYT")
    tickers = load_tickers()
    sel = st.selectbox("Wybierz spółkę:", tickers)
    
    if st.button("Analizuj"):
        with st.spinner("Pobieram dane..."):
            df = yf.download(sel, period="2y", progress=False)
            if df is not None and len(df)>100:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
                c = df['Close']
                cur = c.iloc[-1]
                
                e9 = EMAIndicator(c, 9).ema_indicator()
                e17 = EMAIndicator(c, 17).ema_indicator()
                e100 = EMAIndicator(c, 100).ema_indicator().iloc[-1]
                e200 = EMAIndicator(c, 200).ema_indicator().iloc[-1]
                rsi = RSIIndicator(c, 14).rsi().iloc[-1]
                
                # --- LOGIKA ---
                trend_ok = (cur > e200) and (e100 > e200)
                cross_now = e9.iloc[-1] > e17.iloc[-1]
                
                st.divider()
                c1, c2, c3 = st.columns(3)
                c1.metric("Cena", f"{cur:.2f}")
                c2.metric("RSI", f"{rsi:.1f}")
                
                if trend_ok:
                    c3.success("✅ TREND WZROSTOWY (Silny)")
                elif cur > e200:
                    c3.warning("⚠️ TREND SŁABY (Średnie nieułożone)")
                else:
                    c3.error("🔴 BRAK TRENDU")

                # Wykres
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=c, name='Cena', line=dict(color='black')))
                fig.add_trace(go.Scatter(x=df.index, y=e9, name='EMA 9', line=dict(color='blue', width=1)))
                fig.add_trace(go.Scatter(x=df.index, y=e17, name='EMA 17', line=dict(color='orange', width=1)))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Brak danych.")

# ==========================================
# MODUŁ 2: SKANER (TRUE CROSS)
# ==========================================
elif app_mode == "🚀 SKANER (True Cross)":
    st.title("🚀 SKANER SYGNAŁÓW")
    st.info("Logika: Cena > EMA200 + EMA100 > EMA200 (Trend) + EMA9 przecina EMA17 (Timing)")
    
    tickers = load_tickers()
    
    if st.button("🚀 SKANUJ RYNEK"):
        bulk = get_bulk_data(tickers)
        results = []
        
        if bulk is not None:
            prog = st.progress(0)
            status_txt = st.empty()
            
            for i, t in enumerate(tickers):
                prog.progress((i+1)/len(tickers))
                df = extract_ticker_data(bulk, t)
                if df is not None:
                    try:
                        c = df['Close']
                        if len(c) < 200: continue
                        
                        # Serie danych
                        e9_series = EMAIndicator(c, 9).ema_indicator()
                        e17_series = EMAIndicator(c, 17).ema_indicator()
                        
                        # Wartości TERAZ (-1) i WCZORAJ (-2)
                        e9 = e9_series.iloc[-1]; e9_prev = e9_series.iloc[-2]
                        e17 = e17_series.iloc[-1]; e17_prev = e17_series.iloc[-2]
                        
                        cur = c.iloc[-1]
                        e100 = EMAIndicator(c, 100).ema_indicator().iloc[-1]
                        e200 = EMAIndicator(c, 200).ema_indicator().iloc[-1]
                        rsi = RSIIndicator(c, 14).rsi().iloc[-1]
                        
                        # --- WARUNKI ---
                        # 1. Trend (Ścisły)
                        cond_trend = (cur > e200) and (e100 > e200)
                        
                        # 2. Timing (Przecięcie w górę)
                        cond_cross_up = (e9_prev <= e17_prev) and (e9 > e17)
                        
                        # 3. Hold (Kontynuacja)
                        cond_hold = (e9 > e17) and not cond_cross_up

                        sygnal = ""
                        
                        # Szukamy świeżych wejść
                        if cond_trend and cond_cross_up and rsi >= 55:
                            sygnal = "🔥 BUY (NOWY SYGNAŁ)"
                            results.append({"Ticker": t, "Cena": cur, "RSI": rsi, "Sygnał": sygnal})
                        
                        # Opcjonalnie: Pokaż też silne trzymanie (możesz zakomentować jeśli chcesz tylko nowe)
                        elif cond_trend and cond_hold and rsi >= 60:
                            sygnal = "🟢 HOLD (Kontynuacja)"
                            # results.append({"Ticker": t, "Cena": cur, "RSI": rsi, "Sygnał": sygnal})

                    except: pass
            
            prog.empty()
            status_txt.empty()
            
            if results:
                st.success(f"Znaleziono {len(results)} okazji!")
                st.dataframe(pd.DataFrame(results))
                
                if st.button("📧 Wyślij Raport na Maila"):
                    send_email_alert(results)
            else:
                st.warning("Brak nowych sygnałów wejścia (Cross Up) w silnym trendzie.")

# ==========================================
# MODUŁ 3: BACKTESTER
# ==========================================
elif app_mode == "📊 BACKTESTER":
    st.title("📊 Symulator Strategii")
    tickers = load_tickers()
    sel = st.selectbox("Testuj spółkę:", tickers)
    capital = st.number_input("Kapitał:", 10000)
    
    if st.button("Uruchom Symulację"):
        df = yf.download(sel, period="5y", progress=False)
        if df is not None and len(df)>200:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            c=df['Close']; l=df['Low']
            e9=EMAIndicator(c,9).ema_indicator()
            e17=EMAIndicator(c,17).ema_indicator()
            e100=EMAIndicator(c,100).ema_indicator()
            e200=EMAIndicator(c,200).ema_indicator()
            rsi=RSIIndicator(c,14).rsi()
            
            in_pos=False; bal=capital; shares=0; entry=0; trades=[]
            equity = []
            
            for i in range(200, len(df)):
                idx = df.index[i]
                
                # Warunki z historii
                cur_price = c.iloc[i]
                trend_ok = (cur_price > e100.iloc[i]) and (e100.iloc[i] > e200.iloc[i])
                cross_up = (e9.iloc[i-1] <= e17.iloc[i-1]) and (e9.iloc[i] > e17.iloc[i])
                cross_down = (e9.iloc[i-1] >= e17.iloc[i-1]) and (e9.iloc[i] < e17.iloc[i])
                mom_ok = rsi.iloc[i] >= 60
                
                # Logika handlu
                if in_pos:
                    # Wyjście (Cross Down lub SL)
                    if cross_down: # Exit Signal
                        bal = shares * cur_price
                        trades.append({"Data": idx, "Typ": "EXIT", "Cena": cur_price, "Wynik": bal - (shares*entry)})
                        in_pos = False
                
                if not in_pos:
                    # Wejście
                    if trend_ok and cross_up and mom_ok:
                        entry = cur_price
                        shares = bal / entry
                        in_pos = True
                        trades.append({"Data": idx, "Typ": "BUY", "Cena": entry, "Wynik": 0})
                
                curr_val = bal if not in_pos else shares * cur_price
                equity.append({"Data": idx, "Kapitał": curr_val})
            
            eq_df = pd.DataFrame(equity).set_index("Data")
            st.line_chart(eq_df)
            st.dataframe(pd.DataFrame(trades))
            
            final_ret = ((eq_df['Kapitał'].iloc[-1] - capital)/capital)*100
            st.metric("Wynik całkowity", f"{final_ret:.2f}%")
