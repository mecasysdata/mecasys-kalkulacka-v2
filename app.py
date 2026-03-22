import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os

# --- 1. POMOCNÉ FUNKCIE ---
def safe_num(val):
    if pd.isna(val) or val == "": return 0.0
    try:
        # Odstráni čiarky (tisícky), medzery a symboly meny
        s = str(val).replace(',', '').replace(' ', '').replace('€', '')
        return float(s)
    except:
        return 0.0

# --- 2. KONFIGURÁCIA A NAČÍTANIE ---
st.set_page_config(page_title="MECASYS AI - Final", layout="wide")

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

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

# Linky na Google Sheets
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
df_zakaznici = load_data(f"{URL_BASE}gid=324957857&single=true&output=csv")
df_mat = load_data(f"{URL_BASE}gid=1281008948&single=true&output=csv")
df_cennik = load_data(f"{URL_BASE}gid=901617097&single=true&output=csv")
df_koop = load_data(f"{URL_BASE}gid=1180392224&single=true&output=csv")

ai = load_ai_models()

# --- 3. VSTUPY POUŽÍVATEĽA ---
st.title("⚙️ MECASYS AI - Produkčný systém")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Zákazník a Materiál")
    z_list = sorted(df_zakaznici['zakaznik'].unique()) if not df_zakaznici.empty else ["---"]
    vyber_z = st.selectbox("Zákazník", z_list)
    dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0] if not df_zakaznici.empty else {}
    lojalita = safe_num(dz.get('lojalita', 0.5))
    krajina = str(dz.get('krajina', 'SK'))

    m_list = sorted(df_mat['material'].unique()) if not df_mat.empty else []
    material = st.selectbox("Materiál", m_list)
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique()) if not df_f.empty else [])

with col2:
    st.subheader("Parametre dielu")
    d = st.number_input("Priemer d [mm]", value=20.0)
    l = st.number_input("Dĺžka l [mm]", value=50.0)
    pocet_kusov = st.number_input("Počet kusov", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")

# --- 4. LOGIKA HUSTOTY A GEOMETRIE ---
hustota = 7900.0
if material == "NEREZ": hustota = 8000.0
elif material == "OCEĽ": hustota = 7900.0
elif material == "PLAST":
    p_match = df_f[df_f['akost'] == akost]
    hustota = safe_num(p_match['hustota'].iloc[0]) if not p_match.empty else 1200.0
    if hustota < 100: hustota = 1200.0
elif material == "FAREBNÉ KOVY":
    ako_s = str(akost).upper()
    if "3.7" in ako_s: hustota = 4500.0
    elif "3." in ako_s: hustota = 2800.0
    else: hustota = 8500.0

hmotnost = hustota * (math.pi/4) * (d/1000)**2 * (l/1000)
plocha_plasta = math.pi * d * l  # v mm2
plocha_prierezu = (math.pi * d**2) / 4

# --- 5. EKONOMIKA: MATERIÁL ---
res_m = df_cennik[(df_cennik['material']==material)&(df_cennik['akost']==akost)&(df_cennik['d']>=d)].sort_values('d')
cena_mat_jednotka = safe_num(res_m.iloc[0]['cena']) if not res_m.empty else 0.0
cena_material = (cena_mat_jednotka * l) / 1000

# --- 6. EKONOMIKA: KOOPERÁCIA (NOVÁ LOGIKA) ---
st.divider()
st.subheader("Kooperácia")
druhy_koop = ["Bez kooperácie"] + sorted(df_koop['druh'].unique().tolist())
vybrana_koop = st.selectbox("Druh kooperácie", druhy_koop)

cena_kooperacia = 0.0

if vybrana_koop != "Bez kooperácie":
    # Hľadáme presnú zhodu Druh + Materiál
    match_k = df_koop[(df_koop['druh'] == vybrana_koop) & (df_koop['material'] == material)]
    
    if not match_k.empty:
        rk = match_k.iloc[0]
        tarifa = safe_num(rk.get('tarifa', 0))
        min_zakazka = safe_num(rk.get('minimalna_zakazka', 0))
        jednotka = str(rk.get('jednotka', 'kg')).lower()
        
        # Výpočet ceny podľa jednotky
        if 'kg' in jednotka:
            vypocet = tarifa * hmotnost
        elif 'dm2' in jednotka:
            vypocet = tarifa * (plocha_plasta / 10000)
        else:
            vypocet = tarifa # paušál na kus
            
        # Aplikácia minimálnej zákazky (rozpočítaná na 1 kus)
        cena_kooperacia = max(vypocet, min_zakazka / pocet_kusov)
        st.success(f"Kooperácia vypočítaná automaticky: {cena_kooperacia:.4f} €/ks")
    else:
        st.warning(f"Sadzba pre '{vybrana_koop}' a materiál '{material}' chýba v tabuľke.")
        cena_kooperacia = st.number_input("Zadajte cenu kooperácie manuálne [€/ks]", min_value=0.0, format="%.4f")

vstupne_naklady = cena_material + cena_kooperacia

# --- 7. AI PREDIKCIA ---
if ai["m1"] and ai["m2"]:
    try:
        # M1: ČAS
        v1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': plocha_prierezu, 
              'plocha_plasta': plocha_plasta, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
        for c in ai["cols1"]:
            if c not in v1: v1[c] = 0
            if c == f"material_{material}": v1[c] = 1
            if c == f"narocnost_{narocnost}": v1[c] = 1
        
        pred_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([v1])[ai["cols1"]]))[0]))

        # M2: CENA
        v2 = {'cas': pred_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': plocha_prierezu}
        for c in ai["cols2"]:
            if c not in v2: v2[c] = 0
            if c == f"krajina_{krajina}": v2[c] = 1
        
        pred_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]]))[0]))

        # Zobrazenie výsledkov
        c_res1, c_res2 = st.columns(2)
        c_res1.metric("Odhadovaný čas", f"{pred_cas:.2f} min")
        c_res2.metric("Finálna cena", f"{pred_cena:.2f} €/ks")
        
        st.info(f"Vstupné náklady (Mat + Koop): {vstupne_naklady:.3f} €")

    except Exception as e:
        st.error(f"Chyba AI: {e}")
else:
    st.error("Modely nenájdené v MECASYS_APP/.")
