import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
import pytz

# --- KONFIGŪRACIJA ---
st.set_page_config(page_title="BLYKSNIS: Energetinis Skydas", page_icon="⚡", layout="wide")

# --- PATIKIMAS DUOMENŲ GAVIMAS ---
@st.cache_data(ttl=300) # Kas 5 min bandom iš naujo, jei buvo klaida
def gauti_kainas():
    # Naudojame paprastesnį laiko formatą, kurį Elering tikrai mėgsta
    dabar_utc = datetime.now(pytz.utc)
    pradzia = (dabar_utc - timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    pabaiga = (dabar_utc + timedelta(days=1)).strftime('%Y-%m-%dT23:59:59.999Z')
    
    url = "https://dashboard.elering.ee/api/nps/price/LT"
    params = {"start": pradzia, "end": pabaiga}
    
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 500:
            st.warning("🔄 Biržos serveris (Elering) laikinai nepasiekiamas. Bandome dar kartą...")
            return pd.DataFrame()
        
        r.raise_for_status()
        duomenys = r.json()
        
        if not duomenys['success']:
            st.error("❌ Biržos duomenų tiekėjas pranešė apie klaidą.")
            return pd.DataFrame()

        df = pd.DataFrame(duomenys['data']['lt'])
        df['data_laikas'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Europe/Vilnius')
        df['kaina_mwh'] = df['price']
        return df[['data_laikas', 'kaina_mwh']]
        
    except Exception as e:
        st.error(f"⚠️ Nepavyko prisijungti prie biržos. Galbūt serveris profilaktiškai tvarkomas?")
        return pd.DataFrame()

# --- UI PRADŽIA ---
st.title("⚡ BLYKSNIS: Energetinis Skydas")

# --- ŠONINĖ JUOSTA ---
st.sidebar.header("⚙️ Nustatymai")
pvm = st.sidebar.selectbox("PVM (%)", [21, 9, 0], index=0)
marza = st.sidebar.number_input("Tiekėjo marža (ct/kWh)", value=1.0)
eso = st.sidebar.number_input("ESO (ct/kWh)", value=8.5)

df = gauti_kainas()

if not df.empty:
    # Skaičiavimai
    df['galutine_kaina'] = (df['kaina_mwh'] / 10 + marza + eso) * (1 + pvm/100)
    tz = pytz.timezone('Europe/Vilnius')
    dabar = datetime.now(tz)
    df_ateitis = df[df['data_laikas'] >= dabar.replace(minute=0, second=0, microsecond=0)].copy()

    # TABS
    t1, t2, t3 = st.tabs(["📊 Radaras", "🚗 Automatika", "☀️ Saulė"])

    with t1:
        c1, c2 = st.columns(2)
        dabartine = df_ateitis.iloc[0]['galutine_kaina']
        c1.metric("Dabartinė kaina", f"{dabartine:.2f} ct")
        
        fig = px.bar(df_ateitis, x='data_laikas', y='galutine_kaina', color='galutine_kaina', 
                     color_continuous_scale='RdYlGn_r')
        st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.subheader("🎯 EV Auksinis Langas")
        val = st.slider("Krovimo trukmė (val.)", 1, 10, 4)
        df_ateitis['vid'] = df_ateitis['galutine_kaina'].rolling(window=val).mean()
        best_idx = df_ateitis['vid'].idxmin()
        best_time = df_ateitis.loc[best_idx, 'data_laikas'] - timedelta(hours=val-1)
        st.success(f"Pigiausia krauti nuo: **{best_time.strftime('%H:%M')}**")
        
        st.divider()
        st.button("⚡ Priverstinis EV krovimas (Manual)", use_container_width=True)

    with t3:
        st.info("☀️ Saulės parko modulis bus aktyvuotas, kai biržos serveriai stabilizuosis.")
else:
    st.info("🕒 Laukiama, kol biržos serveris atsigaus... Galite pabandyti perkrauti puslapį po minutės.")
    if st.button("🔄 Bandyti dabar"):
        st.cache_data.clear()
        st.rerun()