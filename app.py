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
        s = str(val).replace(',', '').replace(' ', '').replace('€', '')
        return float(s)
    except:
        return 0.0

# --- 2. NAČÍTANIE ---
st.set_page_config(page_title="MECASYS AI - Fixed", layout="wide")

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
        m1 = xgb.Booster(); m1.load_model(f"{p}finalny_model.json")
        with open(f"{p}stlpce_modelu.pkl", 'rb') as f: assets["cols1"] = pickle.load(f)
        assets["m1"] = m1
        m2 = xgb.Booster(); m2.load_model(f"{p}xgb_model_cena.json")
        with open(f"{p}model_columns.pkl", 'rb') as f: assets["cols2"] = pickle.load(f)
        assets["m2"] = m2
    except: pass
    return assets

URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
df_zakaznici = load_data(f"{URL_BASE}gid=324957857&single=true&output=csv")
df_mat = load_data(f"{URL_BASE}gid=1281008948&single=true&output=csv")
df_cennik = load_data(f"{URL_BASE}gid=901617097&single=true&output=csv")
df_koop = load_data(f"{URL_BASE}gid=1180392224&single=true&output=csv")
ai = load_ai_models()

# --- 3. VSTUPY ---
st.title("⚙️ MECASYS AI")
col1, col2 = st.columns(2)

with col1:
    vyber_z = st.selectbox("Zákazník", sorted(df_zakaznici['zakaznik'].unique()))
    dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
    lojalita = safe_num(dz.get('lojalita', 0.5))
    krajina = str(dz.get('krajina', 'SK'))

    material = st.selectbox("Materiál", sorted(df_mat['material'].unique()))
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique()))

with col2:
    d = st.number_input("Priemer d [mm]", value=20.0)
    l = st.number_input("Dĺžka l [mm]", value=50.0)
    pocet_kusov = st.number_input("Počet kusov", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")

# --- 4. GEOMETRIA A MATERIÁL ---
hustota = 7900.0
if material == "NEREZ": hustota = 8000.0
elif material == "OCEĽ": hustota = 7900.0
elif material == "PLAST":
    p_match = df_f[df_f['akost'] == akost]
    hustota = safe_num(p_match['hustota'].iloc[0]) if not p_match.empty else 1200.0

hmotnost = hustota * (math.pi/4) * (d/1000)**2 * (l/1000)
plocha_plasta = math.pi * d * l
plocha_prierezu = (math.pi * d**2) / 4

res_m = df_cennik[(df_cennik['material']==material)&(df_cennik['akost']==akost)&(df_cennik['d']>=d)].sort_values('d')
cena_mat_ks = (safe_num(res_m.iloc[0]['cena']) * l / 1000) if not res_m.empty else 0.0

# --- 5. KOOPERÁCIA (OPRAVENÁ LOGIKA) ---
st.divider()
druhy_koop = ["Bez kooperácie"] + sorted(df_koop['druh'].unique().tolist())
vybrana_koop = st.selectbox("Druh kooperácie", druhy_koop)

cena_koop_ks = 0.0
if vybrana_koop != "Bez kooperácie":
    match_k = df_koop[(df_koop['druh'] == vybrana_koop) & (df_koop['material'] == material)]
    
    if not match_k.empty:
        rk = match_k.iloc[0]
        tarifa = safe_num(rk.get('tarifa', 0))
        min_zakazka = safe_num(rk.get('minimalna_zakazka', 0))
        jednotka = str(rk.get('jednotka', 'kg')).lower()
        
        # Vypočítame základnú cenu za kus podľa sadzby
        if 'kg' in jednotka:
            zakladna_cena = tarifa * hmotnost
        elif 'dm2' in jednotka:
            zakladna_cena = tarifa * (plocha_plasta / 10000)
        else:
            zakladna_cena = tarifa
            
        # KRITICKÝ BOD: Ak je (zakladna_cena * pocet_kusov) menej ako minimálna zákazka, 
        # celková cena za kooperáciu je min_zakazka. Na jeden kus je to teda min_zakazka / pocet_kusov.
        if (zakladna_cena * pocet_kusov) < min_zakazka:
            cena_koop_ks = min_zakazka / pocet_kusov
        else:
            cena_koop_ks = zakladna_cena
            
        st.success(f"Kooperácia: {cena_koop_ks:.4f} €/ks (Min. zákazka {min_zakazka} € zohľadnená)")
    else:
        cena_koop_ks = st.number_input("Manuálna cena kooperácie [€/ks]", value=0.0, format="%.4f")

vstupne_naklady = cena_mat_ks + cena_koop_ks

# --- 6. AI PREDIKCIA ---
if ai["m1"] and ai["m2"]:
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
    
    pred_ai_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]]))[0]))

    # FINÁLNA LOGIKA: AI cena nesmie byť nižšia ako reálne vstupné náklady!
    finalna_predajka = max(pred_ai_cena, vstupne_naklady * 1.2) # Pridaná marža 20% k nákladom ako dno

    st.subheader("Výsledok")
    res1, res2 = st.columns(2)
    res1.metric("Odhadovaný čas", f"{pred_cas:.2f} min")
    res2.metric("Odporúčaná cena", f"{finalna_predajka:.2f} €/ks")
    st.write(f"Detail nákladov: Materiál {cena_mat_ks:.3f}€ + Koop {cena_koop_ks:.3f}€ = {vstupne_naklady:.3f}€")
