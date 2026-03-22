import streamlit as st
import pandas as pd
import numpy as np
import math
import pickle
import os
from xgboost import XGBRegressor

# --- KONFIGURÁCIA STRÁNKY ---
st.set_page_config(page_title="Mecasys Kalkulačka v2", layout="wide")

# --- 1. NAČÍTANIE MODELU A MAPY STĹPCOV ---
@st.cache_resource
def load_assets():
    # Cesty k súborom v tvojom priečinku
    model_path = os.path.join('MECASYS_APP', 'finalny_model.json')
    columns_path = os.path.join('MECASYS_APP', 'stlpce_modelu.pkl')
    
    model = XGBRegressor()
    model.load_model(model_path)
    with open(columns_path, 'rb') as f:
        model_columns = pickle.load(f)
    return model, model_columns

try:
    model, model_columns = load_assets()
except Exception as e:
    st.error(f"❌ CHYBA: Nepodarilo sa načítať model! ({e})")
    st.stop()

# --- 2. TVORBA ROZHRANIA ---
st.title("🏭 Mecasys - AI Kalkulačka Výroby")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📦 Parametre dielu")
    v_mat = st.selectbox("Materiál", ['OCEĽ', 'NEREZ', 'FAREBNÉ KOVY', 'PLAST'])
    v_ako = st.text_input("Akosť (text)", value="1.0577").strip().upper()
    v_nar = st.selectbox("Náročnosť (1-5)", ['1', '2', '3', '4', '5'])

with col2:
    st.subheader("📏 Geometria a množstvo")
    v_d = st.number_input("Priemer (d) mm", value=50.0, step=0.1)
    v_l = st.number_input("Dĺžka (l) mm", value=100.0, step=0.1)
    v_ks = st.number_input("Počet kusov", value=1, min_value=1)

# --- 3. JADRO PREDIKCIE (Prebraté z Colabu) ---
if st.button("🚀 VYPOČÍTAŤ ČASY VÝROBY", use_container_width=True):
    try:
        # A. Príprava dát
        p_prierez = (math.pi * v_d**2) / 4
        p_plast = math.pi * v_d * v_l
        log_ks = np.log1p(v_ks)
        
        # B. Vstupný riadok (presne podľa model_columns)
        input_df = pd.DataFrame(0.0, index=[0], columns=model_columns)
        
        # C. Numerické hodnoty
        input_df['d'] = float(v_d)
        input_df['l'] = float(v_l)
        input_df['pocet_kusov'] = float(log_ks)
        input_df['plocha_prierezu'] = float(p_prierez)
        input_df['plocha_plasta'] = float(p_plast)
        
        # D. Príprava názvov stĺpcov pre kategórie
        col_mat = f"material_{v_mat}"
        col_ako = f"akost_{v_ako}"
        col_nar = f"narocnost_{v_nar}"
        
        # E. Kontrola a nastavenie dummy premenných (ako v Colabe)
        pozná_mat = col_mat in input_df.columns
        pozná_ako = col_ako in input_df.columns
        
        if pozná_mat: input_df[col_mat] = 1.0
        if pozná_ako: input_df[col_ako] = 1.0
        if col_nar in input_df.columns: input_df[col_nar] = 1.0
        
        # F. Predikcia
        pred_log = model.predict(input_df)[0]
        pred_min_kus = np.expm1(pred_log)
        pred_min_celkovo = pred_min_kus * v_ks
        
        # G. Zobrazenie výsledkov (Štýlovanie)
        st.markdown("---")
        color = "#2e7d32" if pozná_ako else "#f57c00"
        
        c1, c2 = st.columns(2)
        c1.metric("Čas na 1 komponent", f"{pred_min_kus:.2f} min")
        c2.metric("CELKOVÝ ČAS", f"{pred_min_celkovo:.2f} min", delta=f"{pred_min_celkovo/60:.2f} hod", delta_color="normal")

        if not pozná_ako:
            st.warning(f"⚠️ Akosť '{v_ako}' nebola v tréningu, model použil priemer pre materiál {v_mat}.")
            
        # Zobrazenie pre debug
        with st.expander("🔍 Technický detail vstupu"):
            st.dataframe(input_df)

    except Exception as e:
        st.error(f"❌ Chyba výpočtu: {e}")
