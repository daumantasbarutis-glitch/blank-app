import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
import pytz

# --- KONFIGŪRACIJA ---
st.set_page_config(page_title="BLYKSNIS", page_icon="⚡", layout="wide")

# --- TIKSLAUS LAIKO IR DUOMENŲ FUNKCIJA ---
@st.cache_data(ttl=600) # Duomenis atnaujiname kas 10 minučių
def gauti_tikslias_kainas():
    tz_lt = pytz.timezone('Europe/Vilnius')
    dabar_lt = datetime.now(tz_lt)
    
    # Suformuojame laiko rėmus užklausai (nuo vakar iki rytoj pabaigos)
    start = (dabar_lt - timedelta(days=1)).replace(hour=0, minute=0).astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    end = (dabar_lt + timedelta(days=2)).replace(hour=23, minute=59).astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    url = "https://dashboard.elering.ee/api/nps/price/LT"
    params = {"start": start, "end": end}
    
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        res = r.json()
        
        if res.get('success'):
            raw_data = res['data']['lt']
            df = pd.DataFrame(raw_data)
            
            # Konvertuojame Unix timestamp į Lietuvos laiką
            df['Laikas'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert(tz_lt)
            df['Kaina_MWh'] = df['price']
            
            # Išvalome ir surūšiuojame
            df = df[['Laikas', 'Kaina_MWh']].sort_values('Laikas')
            return df
    except Exception as e:
        st.error(f"⚠️ Ryšio klaida su birža: {e}")
        return pd.DataFrame()

# --- PROGRAMĖLĖS VALDYMAS ---
st.title("⚡ BLYKSNIS: Energetinis Skydas")

# ŠONINĖ JUOSTA: Tavo tarifai
st.sidebar.header("📊 Tarifų skaičiuoklė")
st.sidebar.info("Įvesk savo sutarties duomenis tiksliam skaičiavimui.")

pvm = st.sidebar.selectbox("PVM Tarifas (%)", [21, 9, 0], index=0)
eso = st.sidebar.number_input("ESO persiuntimas (ct/kWh)", value=8.53, format="%.2f")
marza = st.sidebar.number_input("Tiekėjo marža (ct/kWh)", value=1.00, format="%.2f")

# Gauname duomenis
df = gauti_tikslias_kainas()

if not df.empty:
    # MATEMATIKA: MWh -> ct/kWh su mokesčiais
    # Formulė: ((Kaina_MWh / 10) + ESO + Marža) * PVM_koeficientas
    df['Galutinė Kaina (ct/kWh)'] = ((df['Kaina_MWh'] / 10) + eso + marza) * (1 + pvm/100)
    
    # Filtruojame tik tai, kas aktualu dabar ir į ateitį
    tz_lt = pytz.timezone('Europe/Vilnius')
    dabar = datetime.now(tz_lt).replace(minute=0, second=0, microsecond=0)
    df_rodyti = df[df['Laikas'] >= dabar].copy()

    # PAGRINDINIAI RODIKLIAI
    if not df_rodyti.empty:
        dabartine = df_rodyti.iloc[0]['Galutinė Kaina (ct/kWh)']
        kita = df_rodyti.iloc[1]['Galutinė Kaina (ct/kWh)'] if len(df_rodyti) > 1 else dabartine
        pokytis = kita - dabartine
        
        col1, col2 = st.columns(2)
        col1.metric("Kaina DABAR", f"{dabartine:.2f} ct", help="Galutinė kaina su visais tavo mokesčiais")
        col2.metric("Kaina KITĄ VALANDĄ", f"{kita:.2f} ct", delta=f"{pokytis:.2f} ct", delta_color="inverse")

        # GRAFIKAS
        st.subheader("📈 Biržos prognozė tavo piniginei")
        fig = px.bar(
            df_rodyti, 
            x='Laikas', 
            y='Galutinė Kaina (ct/kWh)',
            color='Galutinė Kaina (ct/kWh)',
            color_continuous_scale=['#228B22', '#F4D03F', '#C0392B'], # Žalia -> Geltona -> Raudona
            text_auto='.1f'
        )
        fig.update_layout(xaxis_title="", yaxis_title="ct / kWh", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # AUTOMATIKOS SKILTIS
        with st.expander("🚗 Išmanusis EV krovimas & Boileris"):
            trukme = st.select_slider("Kiek valandų reikia krovimui?", options=range(1, 13), value=4)
            
            # Ieškome pigiausio lango
            df_rodyti['Slenkantis_Vidurkis'] = df_rodyti['Galutinė Kaina (ct/kWh)'].rolling(window=trukme).mean()
            geriausias_idx = df_rodyti['Slenkantis_Vidurkis'].idxmin()
            
            if pd.notna(geriausias_idx):
                pabaiga = df_rodyti.loc[geriausias_idx, 'Laikas']
                pradzia = pabaiga - timedelta(hours=trukme-1)
                st.success(f"💎 Pigiausias {trukme} val. langas: nuo **{pradzia.strftime('%H:%M')}** iki **{(pabaiga + timedelta(hours=1)).strftime('%H:%M')}**")
                st.info(f"Vidutinė kaina šiuo metu bus: **{df_rodyti.loc[geriausias_idx, 'Slenkantis_Vidurkis']:.2f} ct/kWh**")

else:
    st.warning("⚠️ Biržos duomenys laikinai nepasiekiami. Pabandykite atnaujinti po minutės.")
    if st.button("🔄 Atnaujinti dabar"):
        st.cache_data.clear()
        st.rerun()