import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
import pytz
import numpy as np

st.set_page_config(page_title="BLYKSNIS", page_icon="⚡", layout="wide")

def gauti_pavyzdinius_duomenis():
    tz = pytz.timezone('Europe/Vilnius')
    dabar = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    laikai = [dabar + timedelta(hours=i) for i in range(24)]
    kainos = [10, 8, 5, 4, 3, 2, 4, 12, 25, 30, 20, 15, 12, 10, 15, 22, 45, 50, 40, 30, 20, 15, 10, 8]
    return pd.DataFrame({'data_laikas': laikai, 'kaina_mwh': kainos})

@st.cache_data(ttl=60)
def gauti_kainas():
    tz = pytz.timezone('Europe/Vilnius')
    dabar_utc = datetime.now(pytz.utc)
    pradzia = (dabar_utc - timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    pabaiga = (dabar_utc + timedelta(days=1)).strftime('%Y-%m-%dT23:59:59.999Z')
    url = "https://dashboard.elering.ee/api/nps/price/LT"
    try:
        r = requests.get(url, params={"start": pradzia, "end": pabaiga}, timeout=5)
        if r.status_code == 200:
            duomenys = r.json()
            df = pd.DataFrame(duomenys['data']['lt'])
            df['data_laikas'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Europe/Vilnius')
            df['kaina_mwh'] = df['price']
            return df[['data_laikas', 'kaina_mwh']]
    except:
        pass
    return gauti_pavyzdinius_duomenis()

# --- UI ---
st.title("⚡ BLYKSNIS")
st.sidebar.header("⚙️ Nustatymai")
pvm = st.sidebar.selectbox("PVM (%)", [21, 9, 0])
marza = st.sidebar.number_input("Marža (ct)", value=1.0)
eso = st.sidebar.number_input("ESO (ct)", value=8.5)

df = gauti_kainas()
df['galutine_kaina'] = (df['kaina_mwh'] / 10 + marza + eso) * (1 + pvm/100)

t1, t2 = st.tabs(["📊 Radaras", "🚗 Automatika"])

with t1:
    st.metric("Dabartinė kaina", f"{df.iloc[0]['galutine_kaina']:.2f} ct/kWh")
    fig = px.bar(df, x='data_laikas', y='galutine_kaina', color='galutine_kaina', color_continuous_scale='RdYlGn_r')
    st.plotly_chart(fig, use_container_width=True)

with t2:
    st.subheader("🎯 EV Auksinis Langas")
    val = st.slider("Valandos", 1, 12, 4)
    st.button("⚡ Pradėti krovimą", use_container_width=True)
    st.button("🔥 Įjungti Tuya įrenginį", use_container_width=True)