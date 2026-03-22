import streamlit as st
import pandas as pd
import numpy as np
import math
import pickle
import os
import requests
from io import StringIO
from xgboost import XGBRegressor

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(page_title="Mecasys AI Kalkulačka", layout="wide")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

# --- 2. FUNKCIE ---
@st.cache_data(ttl=600)
def load_sheet_data():
    try:
        response = requests.get(SHEET_CSV_URL)
        response.encoding = 'utf-8'
        df = pd.read_csv(StringIO(response.text))
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()
        return df
    except Exception as e:
        st.error(f"Chyba pri načítaní číselníka: {e}")
        return pd.DataFrame(columns=['material', 'akost'])

@st.cache_resource
def load_ai_model():
    model_path = os.path.join('MECASYS_APP', 'finalny_model.json')
    columns_path = os.path.join('MECASYS_APP', 'stlpce_modelu.pkl')
    model = XGBRegressor()
    model.load_model(model_path)
    with open(columns_path, 'rb') as f:
        model_columns = pickle.load(f)
    return model, model_columns

df_ciselnik = load_sheet_data()
model, model_columns = load_ai_model()

# --- 3. FRONTEND ---
st.title("🏭 Mecasys AI - Čistá Predikcia")
st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Materiál a Náročnosť")
    mat_options = sorted(df_ciselnik['material'].unique()) if not df_ciselnik.empty else ['OCEĽ', 'NEREZ', 'PLAST']
    v_mat = st.selectbox("Materiál", mat_options)
    
    akosti_pre_mat = sorted(df_ciselnik[df_ciselnik['material'] == v_mat]['akost'].unique())
    v_ako_vyber = st.selectbox("Akosť", ["-- RUČNE ZADAŤ --"] + akosti_pre_mat)
    
    v_ako_raw = st.text_input("Zadaj akosť") if v_ako_vyber == "-- RUČNE ZADAŤ --" else v_ako_vyber
    v_nar = st.select_slider("Náročnosť", options=['1', '2', '3', '4', '5'], value='1')

with c2:
    st.subheader("Geometria a Množstvo")
    v_d = st.number_input("Priemer (d) [mm]", value=50.0)
    v_l = st.number_input("Dĺžka (l) [mm]", value=100.0)
    v_ks = st.number_input("Počet kusov", value=1, min_value=1)

# --- 4. LOGIKA (BEZ POISTKY) ---
st.markdown("---")

if st.button("🚀 GENEROVAŤ PREDIKCIU", use_container_width=True):
    if not v_ako_raw:
        st.warning("Zadaj akosť.")
    else:
        try:
            v_ako_clean = v_ako_raw.replace(",", ".").strip().upper()
            input_df = pd.DataFrame(0.0, index=[0], columns=model_columns)
            
            # Vstupy
            input_df['d'] = float(v_d)
            input_df['l'] = float(v_l)
            input_df['plocha_prierezu'] = (math.pi * (v_d**2)) / 4
            input_df['plocha_plasta'] = math.pi * v_d * v_l
            input_df['pocet_kusov'] = np.log1p(float(v_ks)) # Logaritmizácia kusov
            
            target_cols = [f"material_{v_mat}", f"akost_{v_ako_clean}", f"narocnost_{v_nar}"]
            for col in target_cols:
                if col in input_df.columns:
                    input_df[col] = 1.0
            
            # Predikcia
            pred_log = model.predict(input_df)[0]
            pred_min_1ks = np.expm1(pred_log) # Spätná transformácia na minúty
            pred_min_celkom = pred_min_1ks * v_ks
            
            # Výsledky
            r1, r2, r3 = st.columns(3)
            with r1:
                st.metric("Čas na 1 kus", f"{pred_min_1ks:.2f} min")
            with r2:
                st.metric("Celkový čas", f"{pred_min_celkom:.2f} min")
                st.write(f"⏱️ **{pred_min_celkom/60:.2f} hod**")
            with r3:
                if f"akost_{v_ako_clean}" in model_columns:
                    st.success("✅ Akosť rozpoznaná")
                else:
                    st.error("⚠️ Neznáma akosť")

        except Exception as e:
            st.error(f"Chyba: {e}")
