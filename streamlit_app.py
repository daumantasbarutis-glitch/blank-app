import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
import pytz

# --- KONFIGŪRACIJA ---
st.set_page_config(page_title="BLYKSNIS: Energetinis Skydas", page_icon="⚡", layout="wide")

# --- PATIKIMAS DUOMENŲ GAVIMAS (Elering API) ---
@st.cache_data(ttl=3600)
def gauti_kainas():
    # Elering serveriams geriausia pateikti užklausą UTC laiku
    dabar_utc = datetime.utcnow()
    pradzia = (dabar_utc - timedelta(days=1)).strftime('%Y-%m-%dT00:00Z')
    pabaiga = (dabar_utc + timedelta(days=2)).strftime('%Y-%m-%dT23:59Z')
    
    url = "https://dashboard.elering.ee/api/nps/price/LT"
    params = {"start": pradzia, "end": pabaiga}
    headers = {"User-Agent": "Mozilla/5.0 (BlyksnisApp/1.0)"}
    
    try:
        r = requests.get(url, params=params, headers=headers)
        r.raise_for_status()
        duomenys = r.json()
        
        df = pd.DataFrame(duomenys['data']['lt'])
        # Konvertuojame į Lietuvos laiko juostą
        df['data_laikas'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Europe/Vilnius')
        df['kaina_mwh'] = df['price']
        return df[['data_laikas', 'kaina_mwh']]
    except Exception as e:
        st.error(f"⚠️ Klaida jungiantis prie biržos: {e}")
        return pd.DataFrame()

# --- PAGRINDINIS PUSLAPIS ---
st.title("⚡ BLYKSNIS: Energetinis Skydas")
st.markdown("Tavo asmeninis elektros kainų, saulės generacijos ir išmaniųjų namų valdymo centras.")

# --- ŠONINĖ JUOSTA (Nustatymai vartotojui) ---
st.sidebar.header("⚙️ Tavo Nustatymai")
pvm = st.sidebar.selectbox("PVM Tarifas (%)", [21, 9, 0], index=0)
marza = st.sidebar.number_input("Tiekėjo marža (ct/kWh)", value=1.0, step=0.1)
eso_tarifas = st.sidebar.number_input("ESO persiuntimas (ct/kWh)", value=8.5, step=0.1)

# Duomenų apdorojimas
df = gauti_kainas()

if not df.empty:
    # Skaičiuojame galutinę kainą su mokesčiais
    df['kaina_ct_kwh'] = df['kaina_mwh'] / 10 
    df['galutine_kaina'] = (df['kaina_ct_kwh'] + marza + eso_tarifas) * (1 + pvm/100)
    
    tz = pytz.timezone('Europe/Vilnius')
    dabar = datetime