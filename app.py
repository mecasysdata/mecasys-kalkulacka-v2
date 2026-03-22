import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os

# --- 1. BEZPEČNÉ NAČÍTANIE (Ak spadne Google, aplikácia pôjde ďalej) ---
st.set_page_config(page_title="MECASYS FINAL", layout="wide")

def safe_float(val, default=0.0):
    try:
        if pd.isna(val): return default
        return float(str(val).replace(',', '.').replace(' ', '').replace('€', ''))
    except: return default

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

# Cesty k dátam
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
df_zakaznici = load_data(f"{URL_BASE}gid=324957857&single=true&output=csv")
df_mat = load_data(f"{URL_BASE}gid=1281008948&single=true&output=csv")
df_cennik = load_data(f"{URL_BASE}gid=901617097&single=true&output=csv")
df_koop = load_data(f"{URL_BASE}gid=1180392224&single=true&output=csv")

@st.cache_resource
def load_ai_models():
    assets = {"m1": None, "cols1": None, "m2": None, "cols2": None}
    p = 'MECASYS_APP/' if os.path.exists('MECASYS_APP/') else ''
    try:
        m1 = xgb.Booster(); m1.load_model(f"{p}finalny_model.json")
        with open(f"{p}stlpce_modelu.pkl", 'rb') as f: assets["cols1"] = pickle.load(f)
        assets["m1"] = m1
        m2 = xgb.Booster(); m2.load_model(f"{p}xgb_model_cena.json")
        with open(f"{p}model_columns.pkl", 'rb') as f: assets["cols2"] = pickle.load(f)
        assets["m2"] = m2
    except: pass
    return assets

ai = load_ai_models()

# --- 2. VSTUPY ---
st.title("🚀 MECASYS AI: Finálne odovzdanie")

c1, c2 = st.columns(2)
with c1:
    # Zákazník
    z_list = sorted(df_zakaznici['zakaznik'].unique()) if not df_zakaznici.empty else ["---"]
    vyber_z = st.selectbox("Zákazník", z_list)
    dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0] if not df_zakaznici.empty else {}
    lojalita = safe_float(dz.get('lojalita', 0.5))
    krajina = str(dz.get('krajina', 'SK'))

    # Materiál
    m_list = sorted(df_mat['material'].unique()) if not df_mat.empty else ["---"]
    material = st.selectbox("Materiál", m_list)
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique()))

with c2:
    d = st.number_input("Priemer d [mm]", value=20.0)
    l = st.number_input("Dĺžka l [mm]", value=50.0)
    pocet_kusov = st.number_input("Počet kusov", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")

# --- 3. OPRAVENÁ LOGIKA (PLASTY + GEOMETRIA) ---
hustota = 7900.0
if material == "NEREZ": hustota = 8000.0
elif material == "OCEĽ": hustota = 7850.0
elif material == "PLAST":
    # Tu bola chyba - fixujeme ju:
    try:
        h_row = df_f[df_f['akost'] == akost]
        hustota = safe_float(h_row['hustota'].iloc[0]) if not h_row.empty else 1200.0
        if hustota == 0: hustota = 1200.0 # Poistka pre prázdne bunky
    except: hustota = 1200.0
elif material == "FAREBNÉ KOVY":
    hustota = 4500.0 if "3.7" in str(akost) else 8500.0

hmotnost = hustota * (math.pi/4) * (d/1000)**2 * (l/1000)
plocha_plasta = math.pi * d * l
plocha_prierezu = (math.pi * d**2) / 4

# --- 4. EKONOMIKA (BEZPEČNÁ) ---
st.divider()
# Materiál
res_m = df_cennik[(df_cennik['material']==material)&(df_cennik['akost']==akost)&(df_cennik['d']>=d)].sort_values('d')
cena_mat = (safe_float(res_m.iloc[0]['cena']) * l) / 1000 if not res_m.empty else 0.0

# Kooperácia - Ošetrenie proti KeyError 'tarifa' / 'minimalna_zakazka'
cena_koop = 0.0
df_k_f = df_koop[df_koop['material'] == material]
if not df_k_f.empty:
    rk = df_k_f.iloc[0]
    # Používame .get() aby kód nezomrel ak stĺpec chýba
    t_val = safe_float(rk.get('tarifa', 0))
    m_val = safe_float(rk.get('minimalna_zakazka', 0))
    jednotka = str(rk.get('jednotka', 'kg')).lower()
    
    odhad_k = (t_val * hmotnost) if 'kg' in jednotka else (t_val * plocha_plasta / 10000)
    cena_koop = max(odhad_k, m_val / pocet_kusov)

vstupne_naklady = cena_mat + cena_koop
st.write(f"Vstupné náklady: **{vstupne_naklady:.4f} €/ks**")

# --- 5. AI (M1 -> M2) ---
if ai["m1"] and ai["m2"]:
    try:
        # Príprava pre ČAS (M1)
        v1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': plocha_prierezu, 
              'plocha_plasta': plocha_plasta, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
        for c in ai["cols1"]:
            if c not in v1: v1[c] = 0
            if c == f"material_{material}": v1[c] = 1
            if c == f"narocnost_{narocnost}": v1[c] = 1
        
        pred_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([v1])[ai["cols1"]]))[0]))

        # Príprava pre CENU (M2)
        v2 = {'cas': pred_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': plocha_prierezu}
        for c in ai["cols2"]:
            if c not in v2: v2[c] = 0
            if c == f"krajina_{krajina}": v2[c] = 1
        
        pred_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]]))[0]))

        st.success(f"✅ AI Predikcia: **{pred_cas:.2f} min** | **{pred_cena:.2f} €/ks**")
    except Exception as e:
        st.error(f"Chyba v AI: {e}")
