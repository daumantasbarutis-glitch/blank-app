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
    dabar = datetime.now(tz)
    # Rodome tik dabartines ir būsimas kainas
    df_ateitis = df[df['data_laikas'] >= dabar.replace(minute=0, second=0, microsecond=0)].copy()

    # --- NAVIGACIJA ---
    tab1, tab2, tab3 = st.tabs(["📊 Biržos Radaras", "🚗 EV & Prietaisai", "☀️ Saulės Generacija"])

    # 1. BIRŽOS RADARAS (Visualizacija)
    with tab1:
        if not df_ateitis.empty:
            dabartine = df_ateitis.iloc[0]['galutine_kaina']
            pigiausia = df_ateitis['galutine_kaina'].min()
            
            c1, c2 = st.columns(2)
            c1.metric("Dabartinė kaina", f"{dabartine:.2f} ct/kWh")
            c2.metric("Pigiausia šiandien", f"{pigiausia:.2f} ct/kWh", 
                      delta=f"{pigiausia - dabartine:.2f} ct", delta_color="inverse")

            fig = px.bar(df_ateitis, x='data_laikas', y='galutine_kaina', 
                         color='galutine_kaina', color_continuous_scale='RdYlGn_r',
                         labels={'data_laikas': 'Valanda', 'galutine_kaina': 'ct/kWh'})
            st.plotly_chart(fig, use_container_width=True)

    # 2. AUTOMATIZACIJA (EV & BOILERIS)
    with tab2:
        st.subheader("🎯 Auksinio Lango Paieška")
        valandos = st.slider("Kiek valandų krausis automobilis?", 1, 12, 4)
        
        # Surandame pigiausią nepertraukiamą laiko bloką
        df_ateitis['vidurkis'] = df_ateitis['galutine_kaina'].rolling(window=valandos).mean()
        geriausias_indeksas = df_ateitis['vidurkis'].idxmin()
        
        if pd.notna(geriausias_indeksas):
            pabaiga = df_ateitis.loc[geriausias_indeksas, 'data_laikas']
            pradzia = pabaiga - timedelta(hours=valandos-1)
            vidurkis = df_ateitis.loc[geriausias_indeksas, 'vidurkis']
            
            st.success(f"✅ Geriausia krauti: nuo **{pradzia.strftime('%H:%M')}** iki **{(pabaiga + timedelta(hours=1)).strftime('%H:%M')}**")
            st.info(f"Vidutinė kaina: **{vidurkis:.2f} ct/kWh**")
        
        st.divider()
        st.subheader("🎛️ Rankinis Valdymas")
        colA, colB = st.columns(2)
        colA.button("⚡ Pradėti EV krovimą dabar", use_container_width=True)
        colB.button("🔥 Įjungti Boilerį (Max)", use_container_width=True)

    # 3. SAULĖS ELEKTRINĖS (Nutolusiems parkams)
    with tab3:
        st.subheader("☀️ Nutolusio Saulės Parko Analitika")
        instaliuota_galia = st.number_input("Tavo parko galia (kW)", value=10.0)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.write("📈 Šios dienos generacija (prognozė)")
            st.info("Generuojama: **7.2 kW**")
            st.progress(0.72)
        with col_s2:
            st.write("💰 Sukauptas kreditas")
            st.metric("Likutis pas tiekėją", "1450 kWh", "+120 kWh šiandien")
        
        st.write("💡 *Blyksnio patarimas: Kaina dabar aukšta ({:.2f} ct), o tavo parkas gamina maksimaliai. Idealu parduoti į tinklą!*".format(dabartine))

else:
    st.warning("Laukiama duomenų iš biržos...")