import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
from datetime import date

# --- 1. ZÁKLADNÉ NAČÍTANIE ---
st.set_page_config(page_title="MECASYS AI - Pôvodná Logika", layout="wide")

@st.cache_data
def load_data(url):
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    return df

@st.cache_resource
def load_ai_models():
    assets = {"m1": None, "cols1": None, "m2": None, "cols2": None}
    p = 'MECASYS_APP/' if os.path.exists('MECASYS_APP/') else ''
    try:
        # Model 1: ČAS
        m1 = xgb.Booster(); m1.load_model(f"{p}finalny_model.json")
        with open(f"{p}stlpce_modelu.pkl", 'rb') as f: assets["cols1"] = pickle.load(f)
        assets["m1"] = m1
        # Model 2: CENA
        m2 = xgb.Booster(); m2.load_model(f"{p}xgb_model_cena.json")
        with open(f"{p}model_columns.pkl", 'rb') as f: assets["cols2"] = pickle.load(f)
        assets["m2"] = m2
    except: pass
    return assets

# URL adresy tvojich tabuliek
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
df_zakaznici = load_data(f"{URL_BASE}gid=324957857&single=true&output=csv")
df_mat = load_data(f"{URL_BASE}gid=1281008948&single=true&output=csv")
df_cennik = load_data(f"{URL_BASE}gid=901617097&single=true&output=csv")
df_koop = load_data(f"{URL_BASE}gid=1180392224&single=true&output=csv")
ai = load_ai_models()

# --- 2. VSTUPY (Presne ako na začiatku) ---
st.title("⚙️ MECASYS AI - Reštart")

col1, col2 = st.columns(2)
with col1:
    vyber_z = st.selectbox("Zákazník", sorted(df_zakaznici['zakaznik'].unique()))
    dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
    lojalita = float(dz['lojalita'])
    krajina = str(dz['krajina'])

    material = st.selectbox("Materiál", sorted(df_mat['material'].unique()))
    akost = st.selectbox("Akosť", sorted(df_mat[df_mat['material'] == material]['akost'].unique()))

with col2:
    d = st.number_input("Priemer d [mm]", value=20.0)
    l = st.number_input("Dĺžka l [mm]", value=50.0)
    pocet_kusov = st.number_input("Počet kusov", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")

# --- 3. VÝPOČTY (Technické & Ekonomické) ---
# Hustota
hustota = 7900.0 # Default
if material == "NEREZ": hustota = 8000.0
elif material == "PLAST": hustota = float(df_mat[(df_mat['material']==material)&(df_mat['akost']==akost)]['hustota'].iloc[0])

hmotnost = hustota * (math.pi/4) * (d/1000)**2 * (l/1000)
plocha_plasta = math.pi * d * l
plocha_prierezu = (math.pi * d**2) / 4

# Cena materiálu a kooperácie (Tvoja V8 logika)
res_m = df_cennik[(df_cennik['material']==material)&(df_cennik['akost']==akost)&(df_cennik['d']>=d)].sort_values('d')
cena_mat = (float(res_m.iloc[0]['cena']) * l) / 1000 if not res_m.empty else 0.0

# Kooperácia
row_k = df_koop[df_koop['material']==material].iloc[0]
odhad_k = (float(row_k['tarifa']) * hmotnost) if str(row_k['jednotka']).lower()=='kg' else (float(row_k['tarifa']) * plocha_plasta / 10000)
cena_koop = max(odhad_k, float(row_k['minimalna_zakazka']) / pocet_kusov)

vstupne_naklady = cena_mat + cena_koop

# --- 4. PREPOJENIE MODELOV (To dôležité) ---
st.divider()
if ai["m1"] and ai["m2"]:
    # MODEL 1: PREDPOVEĎ ČASU
    v1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': plocha_prierezu, 
          'plocha_plasta': plocha_plasta, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
    for c in ai["cols1"]:
        if c not in v1: v1[c] = 0
        if c == f"material_{material}": v1[c] = 1
        if c == f"narocnost_{narocnost}": v1[c] = 1
    
    pred_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([v1])[ai["cols1"]]))[0]))

    # MODEL 2: PREDPOVEĎ CENY (Vstupuje pred_cas z Modelu 1)
    v2 = {'cas': pred_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': plocha_prierezu}
    for c in ai["cols2"]:
        if c not in v2: v2[c] = 0
        if c == f"krajina_{krajina}": v2[c] = 1
    
    pred_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]]))[0]))

    st.subheader(f"AI Výsledok: {pred_cas:.2f} min | {pred_cena:.2f} €/ks")
