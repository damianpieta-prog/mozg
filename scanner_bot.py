import pandas as pd
import yfinance as yf
import numpy as np
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SHEET_URL = "https://docs.google.com/spreadsheets/d/1zAE2mUbcVwBfI78f7v3_4K20Z5ffXymyrIcqcyadF4M/export?format=csv&gid=0"

def load_tickers():
    try:
        df = pd.read_csv(SHEET_URL)
        if df.empty: return []
        tickers = df.iloc[:, 0].dropna().astype(str).tolist()
        clean = []
        for t in tickers:
            t = t.strip()
            if t == "DAX": t = "^GDAXI"
            if t == "WIG20": t = "WIG20.WA"
            if t == "GOLD": t = "GLD"
            if t in ["BTC", "BITCOIN"]: t = "BTC-USD"
            if len(t) > 1: clean.append(t)
        return sorted(list(set(clean)))
    except: return []

def send_email(results):
    sender = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASSWORD")
    if not sender or not password: 
        print("Brak hasła w Secrets.")
        return

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = sender
    msg['Subject'] = f"⚡ BOSSA TIMING: {len(results)} świeżych sygnałów (CROSS)!"

    html = """
    <html><body>
    <h2>Raport - Świeże Przecięcia (True Cross)</h2>
    <p>Warunki: <b>EMA9 przebija EMA17 w górę</b> (Timing) + Trend wzrostowy.</p>
    <table border='1' style='border-collapse: collapse; width: 100%;'>
    <tr style='background-color: #f2f2f2;'><th>Ticker</th><th>Cena</th><th>RSI</th><th>Sygnał</th></tr>
    """
    for r in results:
        html += f"<tr><td style='padding:5px'><b>{r['Ticker']}</b></td><td style='padding:5px'>{r['Price']:.2f}</td><td style='padding:5px'>{r['RSI']:.1f}</td><td style='color:green; padding:5px'><b>CROSS UP 🚀</b></td></tr>"
    html += "</table></body></html>"
    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        print("✅ Mail wysłany.")
    except Exception as e: print(f"Błąd wysyłki: {e}")

def main():
    print("🚀 Start Robota (True Cross Logic)...")
    tickers = load_tickers()
    if not tickers: return

    try: 
        data = yf.download(tickers, period="2y", group_by='ticker', progress=False, threads=True)
    except: return

    results = []
    
    for t in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex): df = data[t].dropna()
            else: df = data.dropna()
            
            if len(df) < 200: continue
            
            # --- DANE ---
            c = df['Close']
            curr = c.iloc[-1]
            
            # Wskaźniki OBECNE (Indeks -1)
            e9_now = EMAIndicator(c, 9).ema_indicator().iloc[-1]
            e17_now = EMAIndicator(c, 17).ema_indicator().iloc[-1]
            e100_now = EMAIndicator(c, 100).ema_indicator().iloc[-1]
            e200_now = EMAIndicator(c, 200).ema_indicator().iloc[-1]
            rsi_now = RSIIndicator(c, 14).rsi().iloc[-1]

            # Wskaźniki POPRZEDNIE (Indeks -2) - Do wykrycia przecięcia
            e9_prev = EMAIndicator(c, 9).ema_indicator().iloc[-2]
            e17_prev = EMAIndicator(c, 17).ema_indicator().iloc[-2]
            
            # --- LOGIKA TRUE CROSS (TIMING) ---
            
            # 1. Trend (Stan - to musi trwać)
            cond_trend = (curr > e200_now) and (e100_now > e200_now)
            
            # 2. RSI (Filtr)
            cond_rsi = rsi_now >= 60 # Lekko obniżam próg, żeby łapać start ruchu
            
            # 3. KLUCZOWE: PRZECIĘCIE (Momentum Cross)
            # Wczoraj EMA9 była pod lub równa EMA17, a dzisiaj jest nad
            cond_cross_up = (e9_prev <= e17_prev) and (e9_now > e17_now)
            
            if cond_trend and cond_cross_up and cond_rsi:
                print(f"✅ FRESH SIGNAL: {t}")
                results.append({"Ticker": t, "Price": curr, "RSI": rsi_now})
                
        except: pass

    if results: 
        send_email(results)
    else:
        print("Brak świeżych przecięć dzisiaj.")

if __name__ == "__main__":
    main()
