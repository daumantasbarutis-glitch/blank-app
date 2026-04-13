import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta

# --- KONFIGURACIJA ---
st.set_page_config(page_title="BLYKSNIS ULTRA", layout="wide")
MOKESCIAI, MARZA, PVM = 0.11106, 0.005, 1.21

@st.cache_data(ttl=3600)
def get_prices(start_dt, end_dt):
    try:
        url = f"https://dashboard.elering.ee/api/nps/price?start={start_dt.strftime('%Y-%m-%dT21:00:00Z')}&end={end_dt.strftime('%Y-%m-%dT23:00:00Z')}"
        res = requests.get(url, timeout=10).json()
        df = pd.DataFrame(res['data']['lt'])
        # Laiko fiksas zonų suderinimui
        df['Laikas'] = pd.to_datetime(df['timestamp'], unit='s') + timedelta(hours=2)
        df['Laikas'] = df['Laikas'].dt.tz_localize(None)
        df['Tik Biržos kaina'] = df['price'] / 1000
        df['Kaina su mokesčiais ir PVM'] = (df['Tik Biržos kaina'] + MARZA + MOKESCIAI) * PVM
        return df
    except Exception:
        return None

st.title("⚡ BLYKSNIS: Energijos Valdymo Skydas")

# 1. KAINŲ GRAFIKAS
now = datetime.now().replace(minute=0, second=0, microsecond=0)
prices_df = get_prices(now - timedelta(days=1), now + timedelta(days=2))

if prices_df is not None:
    st.sidebar.header("🕹️ Valdymo skydas")
    duration = st.sidebar.slider("Veikimo trukmė (val.):", 1, 12, 3)
    df_f = prices_df[prices_df['Laikas'] >= now].copy()
    valid_starts = df_f['Laikas'].tolist()[:-duration] if len(df_f) > duration else df_f['Laikas'].tolist()

    if valid_starts:
        chosen_start = st.sidebar.select_slider("Slinkite laiką:", options=valid_starts, format_func=lambda x: x.strftime("%m-%d %H:%M"))
        chosen_end = chosen_start + timedelta(hours=duration)
        mask = (prices_df['Laikas'] >= chosen_start) & (prices_df['Laikas'] < chosen_end)
        avg_p = prices_df.loc[mask, 'Kaina su mokesčiais ir PVM'].mean()

        c1, c2 = st.columns(2)
        c1.metric("Pasirinktas langas", f"{chosen_start.strftime('%H:%M')} - {chosen_end.strftime('%H:%M')}")
        c2.metric("Vidutinė kaina", f"{avg_p:.3f} €/kWh")

        # Dvigubas grafikas (Birža vs Galutinė)
        df_plot = prices_df[(prices_df['Laikas'] >= now - timedelta(hours=6)) & (prices_df['Laikas'] <= now + timedelta(hours=24))].melt(
            id_vars=['Laikas'], value_vars=['Tik Biržos kaina', 'Kaina su mokesčiais ir PVM'], var_name='Tipas', value_name='€'
        )
        fig = px.line(df_plot, x='Laikas', y='€', color='Tipas', color_discrete_map={'Tik Biržos kaina': '#3498db', 'Kaina su mokesčiais ir PVM': '#f1c40f'})
        fig.add_vrect(x0=chosen_start, x1=chosen_end, fillcolor="green", opacity=0.3)
        st.plotly_chart(fig, use_container_width=True)

# 2. ESO SKAIČIUOKLĖ SU 40% OPTIMIZACIJA
st.divider()
st.subheader("📊 ESO Analitika: Kiek galėjote sutaupyti?")
file = st.file_uploader("Įkelkite ESO CSV failą", type="csv")

if file:
    try:
        # Lankstus CSV skaitymas
        try: eso = pd.read_csv(file, sep=';', decimal=',', encoding='utf-8')
        except: eso = pd.read_csv(file, sep=',', decimal='.', encoding='utf-8')
        
        t_col = [c for c in eso.columns if 'data' in c.lower() or 'valand' in c.lower()][0]
        q_col = [c for c in eso.columns if 'kiekis' in c.lower() or 'kwh' in c.lower()][0]

        # Laiko suvienodinimas be zonų
        eso['Laikas'] = pd.to_datetime(eso[t_col], format='ISO8601', utc=True).dt.tz_convert('Europe/Vilnius').dt.tz_localize(None).dt.floor('h')
        eso[q_col] = pd.to_numeric(eso[q_col].astype(str).str.replace(',', '.'), errors='coerce')
        
        hist_p = get_prices(eso['Laikas'].min() - timedelta(days=1), eso['Laikas'].max() + timedelta(days=1))
        
        if hist_p is not None:
            m = pd.merge(eso, hist_p[['Laikas', 'Kaina su mokesčiais ir PVM']], on='Laikas')
            m['Eur_F'] = m[q_col] * m['Kaina su mokesčiais ir PVM']
            
            faktas = m['Eur_F'].sum()
            viso_kwh = m[q_col].sum()

            if faktas > 0:
                # 40% perkėlimo logika (Super skaičiuoklė)
                p_kiekis = viso_kwh * 0.40
                # Pigiausių 20% valandų vidurkis optimizacijai
                v_pigiausia = m.sort_values('Kaina su mokesčiais ir PVM').head(int(len(m)*0.2))['Kaina su mokesčiais ir PVM'].mean()
                teorine = (faktas * 0.60) + (p_kiekis * v_pigiausia)
                skirtumas = faktas - teorine

                st.success(f"✅ Apdorota {viso_kwh:.1f} kWh duomenų.")
                ca, cb, cc = st.columns(3)
                ca.metric("Sumokėta", f"{faktas:.2f} €")
                cb.metric("Su 40% optimizacija", f"{teorine:.2f} €", delta=f"-{skirtumas:.2f} €")
                cc.metric("Sutaupymas", f"{(skirtumas/faktas*100):.1f} %")
                
                st.write(f"💡 Perkėlus 40% suvartojimo į pigiausias valandas, sutaupytumėte **{skirtumas:.2f} €**.")
    except Exception as e:
        st.error(f"Klaida apdorojant failą: {e}")