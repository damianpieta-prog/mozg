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
    msg['Subject'] = f"🛡️ BOSSA ROBOT: {len(results)} okazji (True Cross)"

    html = """
    <html><body>
    <h2>Raport Automatyczny</h2>
    <p>Strategia: Trend (EMA100>200) + Timing (True Cross)</p>
    <table border='1' style='border-collapse: collapse; width: 100%;'>
    <tr style='background-color: #f2f2f2;'><th>Ticker</th><th>Cena</th><th>RSI</th><th>Sygnał</th></tr>
    """
    for r in results:
        html += f"<tr><td style='padding:5px'><b>{r['Ticker']}</b></td><td style='padding:5px'>{r['Price']:.2f}</td><td style='padding:5px'>{r['RSI']:.1f}</td><td style='color:green; padding:5px'>CROSS UP</td></tr>"
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
    print("🚀 Start Robota...")
    tickers = load_tickers()
    if not tickers: return

    try: 
        # BEZ SESJI - Czysty yfinance
        data = yf.download(tickers, period="2y", group_by='ticker', progress=False, threads=True)
    except Exception as e: 
        print(f"Błąd pobierania: {e}")
        return

    results = []
    
    for t in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex): df = data[t].dropna()
            else: df = data.dropna()
            
            if len(df) < 200: continue
            
            c = df['Close']
            cur = c.iloc[-1]
            
            e9_series = EMAIndicator(c, 9).ema_indicator()
            e17_series = EMAIndicator(c, 17).ema_indicator()
            
            e9 = e9_series.iloc[-1]; e9_prev = e9_series.iloc[-2]
            e17 = e17_series.iloc[-1]; e17_prev = e17_series.iloc[-2]
            
            e100 = EMAIndicator(c, 100).ema_indicator().iloc[-1]
            e200 = EMAIndicator(c, 200).ema_indicator().iloc[-1]
            rsi = RSIIndicator(c, 14).rsi().iloc[-1]
            
            # --- LOGIKA ---
            cond_trend = (cur > e200) and (e100 > e200)
            cond_cross_up = (e9_prev <= e17_prev) and (e9 > e17)
            
            if cond_trend and cond_cross_up and rsi >= 55:
                print(f"✅ SYGNAŁ: {t}")
                results.append({"Ticker": t, "Price": cur, "RSI": rsi})
                
        except: pass

    if results: 
        send_email(results)
    else:
        print("Brak sygnałów.")

if __name__ == "__main__":
    main()
