import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
from datetime import date

# --- 1. KONFIGURÁCIA A NAČÍTANIE DÁT ---
st.set_page_config(page_title="MECASYS Kalkulátor V4", layout="wide")

URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
SHEET_ZAKAZNICI = f"{URL_BASE}gid=324957857&single=true&output=csv"
SHEET_MATERIALY = f"{URL_BASE}gid=1281008948&single=true&output=csv"
SHEET_CENNIK    = f"{URL_BASE}gid=901617097&single=true&output=csv"
SHEET_KOOPERACIE= f"{URL_BASE}gid=1180392224&single=true&output=csv"

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

@st.cache_resource
def load_ai_assets():
    paths = ['', 'MECASYS_APP/']
    for p in paths:
        m_path, c_path = f"{p}finalny_model.json", f"{p}stlpce_modelu.pkl"
        if os.path.exists(m_path) and os.path.exists(c_path):
            try:
                bst = xgb.Booster()
                bst.load_model(m_path)
                with open(c_path, 'rb') as f:
                    cols = pickle.load(f)
                return bst, cols
            except: continue
    return None, None

df_zakaznici = load_data(SHEET_ZAKAZNICI)
df_mat = load_data(SHEET_MATERIALY)
df_cennik = load_data(SHEET_CENNIK)
df_koop_cennik = load_data(SHEET_KOOPERACIE)
model_ai, expected_columns = load_ai_assets()

# --- POMOCNÁ FUNKCIA NA ČISTENIE ČÍSIEL ---
def clean_number(val):
    if pd.isna(val): return 0.0
    try:
        # Odstráni čiarky (oddeľovače tisícov) a prevedie na float
        s = str(val).replace(',', '').strip()
        return float(s)
    except:
        return 0.0

st.title("⚙️ Komplexný kalkulačný systém")

# --- 2. IDENTIFIKÁCIA ---
col_id1, col_id2 = st.columns(2)
with col_id1:
    datum = st.date_input("Dátum vystavenia", value=date.today())
    ponuka = st.text_input("Označenie ponuky", placeholder="CP-2026-XXX")
    item = st.text_input("Názov komponentu (Item)")
with col_id2:
    list_z = ["--- Vyber ---", "Nový zákazník (manual)"]
    if not df_zakaznici.empty:
        list_z += sorted(df_zakaznici['zakaznik'].dropna().unique().tolist())
    vyber_z = st.selectbox("Zákazník", list_z)
    zakaznik, krajina, lojalita = "", "", 0.0
    if vyber_z == "Nový zákazník (manual)":
        zakaznik, lojalita = st.text_input("Meno"), 0.5
    elif vyber_z != "--- Vyber ---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik, lojalita = vyber_z, float(dz['lojalita'])

st.divider()

# --- 3. MATERIÁL A HUSTOTA ---
st.subheader("2. Materiálové parametre")
col_m1, col_m2 = st.columns(2)

with col_m1:
    list_mat = sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else []
    material = st.selectbox("Materiál", list_mat)
    df_f = df_mat[df_mat['material'] == material]
    list_ako = sorted(df_f['akost'].unique().tolist()) + ["Iná akosť (manual)"]
    vyber_ako = st.selectbox("Akosť", list_ako)

hustota, akost = 0.0, ""

with col_m2:
    if vyber_ako == "Iná akosť (manual)":
        akost = st.text_input("Názov akosti")
        hustota = st.number_input("Hustota", min_value=0.0)
    else:
        akost = vyber_ako
        if material == "NEREZ": hustota = 8000.0
        elif material == "OCEĽ": hustota = 7900.0
        elif material == "PLAST":
            # TU JE TA OPRAVA: Použijeme clean_number na hodnotu zo Sheetu
            raw_hustota = df_f[df_f['akost'] == akost]['hustota'].iloc[0]
            hustota = clean_number(raw_hustota)
        elif material == "FAREBNÉ KOVY":
            ako_s = str(akost)
            hustota = 4500.0 if ako_s.startswith("3.7") else (2900.0 if ako_s.startswith("3.") else 9000.0)
        
        st.metric("Hustota (kg/m³)", f"{hustota}")

st.divider()

# --- 4. ROZMERY A AI ---
st.subheader("3. Technické parametre")
col_p1, col_p2 = st.columns(2)
with col_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.0)
    l = st.number_input("Dĺžka l [mm]", min_value=0.0)
with col_p2:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť", options=["1", "2", "3", "4", "5"], value="3")

# Výpočty
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)
plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l

# --- 5. EKONOMIKA ---
res_mat = df_cennik[(df_cennik['material'] == material) & (df_cennik['akost'] == akost) & (df_cennik['d'] >= d)]
cena_material = (clean_number(res_mat.sort_values('d').iloc[0]['cena']) * l) / 1000 if not res_mat.empty else 0.0

# --- 6. AI PREDIKCIA ---
predikovany_cas_min = 0.0
if model_ai and expected_columns and d > 0 and l > 0:
    st.subheader("🤖 AI Odhad")
    row_dict = {
        'd': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov),
        'plocha_prierezu': plocha_prierezu, 'plocha_plasta': plocha_plasta,
        'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': cena_material
    }
    for col in expected_columns:
        if col not in row_dict: row_dict[col] = 0
    for c, v in [("material", material), ("akost", akost), ("narocnost", narocnost)]:
        k = f"{c}_{str(v).upper()}"
        if k in expected_columns: row_dict[k] = 1
    
    log_pred = model_ai.predict(xgb.DMatrix(pd.DataFrame([row_dict])[expected_columns]))[0]
    predikovany_cas_min = float(np.expm1(log_pred))
    st.info(f"AI Predikcia strojného času: {predikovany_cas_min:.2f} min/ks")

# --- 7. TABUĽKA ---
st.divider()
st.table(pd.DataFrame({
    "Premenná": ["Materiál", "Hustota", "Hmotnosť [kg]", "AI Čas [min]"],
    "Hodnota": [material, hustota, round(hmotnost, 4), round(predikovany_cas_min, 2)]
}))
