import streamlit as st
import pandas as pd
import numpy as np
import pickle
import os
import math
from xgboost import XGBRegressor

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(page_title="Mecasys M2 - Striktný Test", layout="centered")

# --- 2. KONTROLA EXISTENCIE MODELU (AK CHÝBA, APP ZHASNE) ---
@st.cache_resource
def load_m2_core():
    folder = 'MECASYS_APP'
    model_path = os.path.join(folder, 'xgb_model_cena.json')
    cols_path = os.path.join(folder, 'model_columns.pkl')
    
    # Ak súbory neexistujú, aplikácia sa zastaví
    if not os.path.exists(model_path) or not os.path.exists(cols_path):
        st.error(f"❌ KRITICKÁ CHYBA: Súbory modelu v {folder} sa nenašli. Aplikácia zastavená.")
        st.stop()
    
    model = XGBRegressor()
    model.load_model(model_path)
    
    with open(cols_path, 'rb') as f:
        model_columns = pickle.load(f)
        
    return model, model_columns

# Načítanie "mozgu" aplikácie
m2_model, m2_cols = load_m2_core()

# --- 3. ROZHRANIE VSTUPOV (ČISTÉ POLIA) ---
st.header("🏭 Kalkulačka M2 - Predikcia Ceny")
st.write("Všetky polia sú povinné pre úspešný výpočet.")

col1, col2 = st.columns(2)

with col1:
    v_cas = st.number_input("Čas výroby [min]", step=0.1, value=0.0)
    v_lojalita = st.number_input("Lojalita (koeficient)", step=0.01, value=0.0, format="%.2f")
    v_krajina = st.text_input("Krajina (napr. SK, AT, DE)").strip().upper()

with col2:
    v_d = st.number_input("Priemer d [mm]", step=0.1, value=0.0)
    v_l = st.number_input("Dĺžka l [mm]", step=0.1, value=0.0)
    v_hustota = st.number_input("Hustota materiálu [kg/m3]", step=1.0, value=0.0)
    v_vstupy = st.number_input("Vstupné náklady (mat+koop) [€]", step=0.1, value=0.0)

# --- 4. LOGIKA OVERENIA A VÝPOČTU ---
if st.button("🚀 VYPOČÍTAŤ CENU", use_container_width=True):
    # Kontrola, či užívateľ vyplnil všetky polia
    chyby = []
    if v_cas <= 0: chyby.append("Čas výroby")
    if v_lojalita <= 0: chyby.append("Lojalita")
    if not v_krajina: chyby.append("Krajina")
    if v_d <= 0: chyby.append("Priemer (d)")
    if v_l <= 0: chyby.append("Dĺžka (l)")
    if v_hustota <= 0: chyby.append("Hustota")

    if chyby:
        st.error(f"⚠️ Chýbajúce údaje: {', '.join(chyby)}. Prosím, zadaj hodnoty väčšie ako 0.")
    else:
        try:
            # A. Príprava vstupného riadku (formát ošetrený podľa tréningu)
            input_row = pd.DataFrame(0.0, index=[0], columns=m2_cols)
            
            # B. Matematické vzťahy (vždy float)
            calc_hmotnost = float(v_hustota) * (math.pi / 4) * (float(v_d) / 1000)**2 * (float(v_l) / 1000)
            calc_plocha_prierezu = (math.pi * float(v_d)**2) / 4
            
            # C. Priradenie do DataFrame (iba ak stĺpce existujú v modeli)
            if 'cas' in input_row.columns:
                input_row['cas'] = float(v_cas)
            if 'hmotnost' in input_row.columns:
                input_row['hmotnost'] = calc_hmotnost
            if 'plocha_prierezu' in input_row.columns:
                input_row['plocha_prierezu'] = calc_plocha_prierezu
            if 'lojalita' in input_row.columns:
                input_row['lojalita'] = float(v_lojalita)
            if 'vstupne_naklady' in input_row.columns:
                input_row['vstupne_naklady'] = float(v_vstupy)
                
            # D. One-Hot Encoding pre krajinu
            col_krajina = f"krajina_{v_krajina}"
            if col_krajina in input_row.columns:
                input_row[col_krajina] = 1.0
                
            # E. Predikcia a spätná transformácia (z logaritmu na €)
            log_prediction = m2_model.predict(input_row)[0]
            final_price = np.expm1(log_prediction)
            
            # F. Zobrazenie výsledku
            st.divider()
            st.success(f"Navrhovaná jednotková cena: **{final_price:.2f} €**")
            
            with st.expander("🔍 Technické detaily (Hmotnosť a dáta)"):
                st.write(f"Vypočítaná hmotnosť: **{calc_hmotnost:.4f} kg**")
                st.write(f"Vypočítaná plocha prierezu: **{calc_plocha_prierezu:.2f} mm²**")
                st.dataframe(input_row)

        except Exception as e:
            st.error(f"Nastala technická chyba pri výpočte: {e}")

st.caption("Mecasys AI PRO | Modul M2 (Cena)")
