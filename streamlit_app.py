import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
import pytz

# --- NUSTATYMAI ---
st.set_page_config(page_title="BLYKSNIS: Energetinis Skydas", page_icon="⚡", layout="wide")

# --- DUOMENŲ GAVIMAS (Nord Pool LT per Elering API) ---
@st.cache_data(ttl=3600)
def gauti_kainas():
    tz = pytz.timezone('Europe/Vilnius')
    dabar = datetime.now(tz)
    pradzia = (dabar - timedelta(days=1)).strftime('%Y-%m-%dT22:00:00.000Z')
    pabaiga = (dabar + timedelta(days=2)).strftime('%Y-%m-%dT22:00:00.000Z')
    
    url = f"https://dashboard.elering.ee/api/nps/price/LT?start={pradzia}&end={pabaiga}"
    try:
        r = requests.get(url)
        duomenys = r.json()
        df = pd.DataFrame(duomenys['data']['lt'])
        df['data_laikas'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Europe/Vilnius')
        df['kaina_mwh'] = df['price']
        return df[['data_laikas', 'kaina_mwh']]
    except:
        st.error("⚠️ Nepavyko gauti biržos duomenų. Patikrinkite interneto ryšį.")
        return pd.DataFrame()

# --- UI (Vartotojo sąsaja) ---
st.title("⚡ BLYKSNIS: Energetinis Skydas")
st.markdown("Tavo asmeninis elektros kainų, saulės generacijos ir išmaniųjų namų valdymo centras.")

# --- ŠONINĖ JUOSTA (Nustatymai) ---
st.sidebar.header("⚙️ Tavo Nustatymai")
pvm = st.sidebar.selectbox("PVM Tarifas (%)", [21, 9, 0], index=0)
marza = st.sidebar.number_input("Tiekėjo marža (ct/kWh)", value=1.0, step=0.1)
eso_tarifas = st.sidebar.number_input("ESO persiuntimas (ct/kWh)", value=8.5, step=0.1)

# Skaičiavimai
df = gauti_kainas()

if not df.empty:
    # Apskaičiuojam galutinę kainą (ct/kWh)
    df['kaina_ct_kwh'] = df['kaina_mwh'] / 10 
    df['galutine_kaina'] = (df['kaina_ct_kwh'] + marza + eso_tarifas) * (1 + pvm/100)
    
    tz = pytz.timezone('Europe/Vilnius')
    dabar = datetime.now(tz)
    # Filtruojame tik tas valandas, kurios yra dabar arba ateityje
    df_ateitis = df[df['data_laikas'] >= dabar.replace(minute=0, second=0, microsecond=0)].copy()

    # --- TABAI (Puslapiai) ---
    tab1, tab2, tab3 = st.tabs(["📊 Biržos Radaras", "🚗 EV & Prietaisai", "☀️ Saulės Generacija"])

    # 1. BIRŽOS RADARAS
    with tab1:
        st.subheader("Elektros Kaina (Įskaičiavus ESO, Maržą ir PVM)")
        
        # Pagrindiniai rodikliai
        if not df_ateitis.empty:
            dabartine_kaina = df_ateitis.iloc[0]['galutine_kaina']
            pigiausia = df_ateitis['galutine_kaina'].min()
            brangiausia = df_ateitis['galutine_kaina'].max()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Dabartinė kaina", f"{dabartine_kaina:.2f} ct")
            col2.metric("Pigiausia paros", f"{pigiausia:.2f} ct")
            col3.metric("Brangiausia paros", f"{brangiausia:.2f} ct")

            # Grafikas
            fig = px.bar(df_ateitis, x='data_laikas', y='galutine_kaina', 
                         labels={'data_laikas': 'Laikas', 'galutine_kaina': 'Kaina (ct/kWh)'},
                         color='galutine_kaina', color_continuous_scale='RdYlGn_r',
                         text_auto='.1f')
            fig.update_layout(xaxis_title="", yaxis_title="ct / kWh", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # 2. ĮRENGINIŲ VALDYMAS
    with tab2:
        st.subheader("🎯 Auksinio Lango Paieška")
        st.write("Nurodyk, kiek valandų iš eilės reikia tavo elektromobiliui, šilumos siurbliui ar boileriui:")
        trukmė = st.slider("Reikalingas valandų kiekis", 1, 8, 3)
        
        # Algoritmas ieško pigiausio bloko
        df_ateitis['slenkantis_vidurkis'] = df_ateitis['galutine_kaina'].rolling(window=trukmė).mean()
        geriausias_pabaiga = df_ateitis.loc[df_ateitis['slenkantis_vidurkis'].idxmin()]
        
        if pd.notna(geriausias_pabaiga['slenkantis_vidurkis']):
            laikas_pabaiga = geriausias_pabaiga['data_laikas']
            laikas_pradzia = laikas_pabaiga - timedelta(hours=trukmė-1)
            
            st.success(f"✅ Pigiausias laikas jungti: nuo **{laikas_pradzia.strftime('%H:%M')}** iki **{(laikas_pabaiga + timedelta(hours=1)).strftime('%H:%M')}**")
            st.info(f"Vidutinė kaina šiuo periodu: **{geriausias_pabaiga['slenkantis_vidurkis']:.2f} ct/kWh**")
        
        st.divider()
        st.subheader("🎛️ Prietaisų Valdymo Pultas")
        st.caption("Čia bus prijungti tavo namų įrenginių API (Tuya, ESP, Tesla ir kt.)")
        col_a, col_b = st.columns(2)
        with col_a:
            st.button("🟢 Įjungti Šildymą / Boilerį", use_container_width=True)
            st.button("🔴 Išjungti Šildymą / Boilerį", use_container_width=True)
        with col_b:
            st.button("⚡ Pradėti EV Krovimą", use_container_width=True)
            st.button("⏸️ Stabdyti EV Krovimą", use_container_width=True)

    # 3. SAULĖS PARKAS
    with tab3:
        st.subheader("☀️ Nutolęs Saulės Parkas (Kreditų skaičiuoklė)")
        galia = st.number_input("Tavo elektrinės galia (kW)", min_value=1.0, value=10.0, step=0.5)
        st.write("Prognozuojama dienos generacija:")
        
        # Simuliacija (vėliau jungsime Forecast.Solar API)
        prognoze = galia * 4.2 
        st.info(f"Šiandien turėtum sugeneruoti apie **{prognoze:.1f} kWh**.")
        st.progress(70, text="Dienos planas įvykdytas 70%")
        st.write("💡 *Patarimas: Šiuo metu biržos kaina krenta, verta naudoti sukauptus kreditus.*")