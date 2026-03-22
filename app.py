import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
from datetime import date

# --- 1. KONFIGURÁCIA ---
st.set_page_config(page_title="MECASYS AI Kalkulátor", layout="wide")

# Inicializácia, aby nič nehádzalo NameError
ponuka, item, zakaznik, lojalita = "", "", "", 0.0
material, akost, hustota = "OCEĽ", "", 0.0
d, l, pocet_kusov, narocnost = 0.0, 0.0, 1, "3"
cena_material, cena_kooperacia, predikovany_cas_min = 0.0, 0.0, 0.0

URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
SHEET_MATERIALY = f"{URL_BASE}gid=1281008948&single=true&output=csv"
# ... ostatné URL ponechaj ako máš ...

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        # Očistíme hlavičky a texty (ZÁKLAD PRE PLASTY)
        df.columns = df.columns.str.strip()
        if not df.empty:
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str).str.strip()
        return df
    except: return pd.DataFrame()

@st.cache_resource
def load_ai_assets():
    # Hľadá model v MECASYS_APP aj v koreni
    for p in ['', 'MECASYS_APP/']:
        m, c = f"{p}finalny_model.json", f"{p}stlpce_modelu.pkl"
        if os.path.exists(m) and os.path.exists(c):
            try:
                bst = xgb.Booster(); bst.load_model(m)
                with open(c, 'rb') as f: cols = pickle.load(f)
                return bst, cols
            except: continue
    return None, None

# Načítanie
df_mat = load_data(SHEET_MATERIALY)
model_ai, expected_columns = load_ai_assets()

st.title("⚙️ MECASYS AI Kalkulátor")

# --- 2. MATERIÁL (OPRAVENÁ LOGIKA) ---
st.subheader("Materiálové parametre")
c1, c2 = st.columns(2)

with c1:
    list_mat = sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else ["PLAST"]
    material = st.selectbox("Materiál", list_mat)
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique().tolist()))

with c2:
    # 1. PEVNÉ HODNOTY
    if material == "NEREZ": hustota = 8000.0
    elif material == "OCEĽ": hustota = 7900.0
    elif material == "FAREBNÉ KOVY":
        hustota = 4500.0 if akost.startswith("3.7") else (2900.0 if akost.startswith("3.") else 9000.0)
    
    # 2. DYNAMICKÉ PRE PLASTY (Ťaháme zo stĺpca 'hustota')
    else:
        try:
            # Tu kód hľadá presnú zhodu akosti
            riadok = df_f[df_f['akost'] == akost]
            if not riadok.empty:
                # Skúsime vybrať stĺpec hustota (akokoľvek je napísaný)
                h_col = [c for c in df_mat.columns if 'hustota' in c.lower()][0]
                hustota = float(str(riadok[h_col].iloc[0]).replace(',', '.'))
            else:
                hustota = 0.0
        except Exception as e:
            hustota = 0.0
            st.error(f"Chyba pri hľadaní hustoty: {e}")

    st.metric("Hustota (kg/m³)", f"{hustota}")

# --- 3. ROZMERY A AI (S OCHRANOU) ---
st.divider()
c_p1, c_p2 = st.columns(2)
with c_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.0)
    l = st.number_input("Dĺžka l [mm]", min_value=0.0)
with c_p2:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1)
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")

# PRED PREDIKCIOU SKONTROLUJEME, ČI MÁME ROZMERY
if d > 0 and l > 0 and model_ai:
    # ... tu prebehne výpočet AI (vstupne_naklady, hmotnost atď.) ...
    
    # Príprava pre model
    row_dict = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 
                'plocha_prierezu': (math.pi*d**2)/4, 'plocha_plasta': math.pi*d*l,
                'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': 0.0} # dopln naklady ak treba
    
    for col in expected_columns:
        if col not in row_dict: row_dict[col] = 0
    # One-hot
    for c, v in [("material", material), ("akost", akost), ("narocnost", narocnost)]:
        k = f"{c}_{str(v).upper()}"
        if k in expected_columns: row_dict[k] = 1
        
    log_pred = model_ai.predict(xgb.DMatrix(pd.DataFrame([row_dict])[expected_columns]))[0]
    predikovany_cas_min = float(np.expm1(log_pred))
    
    st.success(f"🤖 AI Predikcia: {predikovany_cas_min:.2f} min/ks")
else:
    st.warning("Zadajte rozmery (d, l) pre výpočet AI času.")

# --- 4. TABUĽKA NA KONCI ---
st.divider()
st.table(pd.DataFrame({
    "Premenná": ["Materiál", "Akosť", "Hustota", "Priemer", "Dĺžka", "AI Čas [min]"],
    "Hodnota": [material, akost, hustota, d, l, round(predikovany_cas_min, 2)]
}))
