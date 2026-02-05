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
    if not sender or not password: return

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = sender
    msg['Subject'] = f"🤖 BOSSA BOT: Znaleziono {len(results)} okazji!"

    html = "<html><body><h2>Raport Dzienny</h2><table border='1'>"
    html += "<tr><th>Ticker</th><th>Cena</th><th>RSI</th><th>SL</th></tr>"
    for r in results:
        html += f"<tr><td>{r['Ticker']}</td><td>{r['Price']:.2f}</td><td>{r['RSI']:.1f}</td><td style='color:red'>{r['SL']:.2f}</td></tr>"
    html += "</table></body></html>"
    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        print("Mail wysłany.")
    except Exception as e: print(e)

def main():
    tickers = load_tickers()
    if not tickers: return
    try: data = yf.download(tickers, period="2y", group_by='ticker', progress=False, threads=True)
    except: return
    results = []
    for t in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex): df = data[t].dropna()
            else: df = data.dropna()
            if len(df)<200: continue
            c=df['Close']; curr=c.iloc[-1]
            e9=EMAIndicator(c,9).ema_indicator().iloc[-1]
            e17=EMAIndicator(c,17).ema_indicator().iloc[-1]
            e100=EMAIndicator(c,100).ema_indicator().iloc[-1]
            e200=EMAIndicator(c,200).ema_indicator().iloc[-1]
            rsi=RSIIndicator(c,14).rsi().iloc[-1]
            if (curr>e100 and curr>e200) and (e9>e17) and (rsi>=65):
                results.append({"Ticker":t, "Price":curr, "SL":curr*0.985, "RSI":rsi})
        except: pass
    if results: send_email(results)

if __name__ == "__main__":
    main()
