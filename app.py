import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
from datetime import date

# --- 1. POMOCNÉ FUNKCIE (Záchranná sieť) ---
def clean_num(val):
    """Prevedie akýkoľvek text z Excelu na číslo. Ak zlyhá, vráti 0.0."""
    if pd.isna(val) or val == "": return 0.0
    try:
        # Odstráni medzery, € a zmení čiarku na bodku
        s = str(val).replace(' ', '').replace('€', '').replace(',', '.')
        return float(s)
    except:
        return 0.0

# --- 2. KONFIGURÁCIA A NAČÍTANIE ---
st.set_page_config(page_title="MECASYS AI V10", layout="wide")

URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
SHEET_ZAKAZNICI = f"{URL_BASE}gid=324957857&single=true&output=csv"
SHEET_MATERIALY = f"{URL_BASE}gid=1281008948&single=true&output=csv"
SHEET_CENNIK    = f"{URL_BASE}gid=901617097&single=true&output=csv"
SHEET_KOOPERACIE= f"{URL_BASE}gid=1180392224&single=true&output=csv"

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip() # Odstráni medzery z názvov stĺpcov
        return df
    except: return pd.DataFrame()

@st.cache_resource
def load_ai_models():
    assets = {"m1": None, "cols1": None, "m2": None, "cols2": None}
    p = 'MECASYS_APP/' if os.path.exists('MECASYS_APP/') else ''
    try:
        if os.path.exists(f"{p}finalny_model.json"):
            m1 = xgb.Booster(); m1.load_model(f"{p}finalny_model.json")
            with open(f"{p}stlpce_modelu.pkl", 'rb') as f: assets["cols1"] = pickle.load(f)
            assets["m1"] = m1
        if os.path.exists(f"{p}xgb_model_cena.json"):
            m2 = xgb.Booster(); m2.load_model(f"{p}xgb_model_cena.json")
            with open(f"{p}model_columns.pkl", 'rb') as f: assets["cols2"] = pickle.load(f)
            assets["m2"] = m2
    except: pass
    return assets

df_zakaznici = load_data(SHEET_ZAKAZNICI)
df_mat = load_data(SHEET_MATERIALY)
df_cennik = load_data(SHEET_CENNIK)
df_koop_cennik = load_data(SHEET_KOOPERACIE)
ai = load_ai_models()

st.title("⚙️ Inteligentný kalkulačný systém V10")

# --- 3. VSTUPY (Zákazník a Materiál) ---
col1, col2 = st.columns(2)
with col1:
    item_name = st.text_input("Názov komponentu", "Nový diel")
    z_list = ["---"] + sorted(df_zakaznici['zakaznik'].dropna().unique().tolist()) if not df_zakaznici.empty else []
    vyber_z = st.selectbox("Zákazník", z_list)
    krajina, lojalita = "SK", 0.5
    if vyber_z != "---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        krajina = str(dz.get('krajina', 'SK'))
        lojalita = clean_num(dz.get('lojalita', 0.5))

with col2:
    m_list = sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else []
    material = st.selectbox("Materiál", m_list)
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique().tolist()) if not df_f.empty else [])

st.divider()

# --- 4. TECHNICKÉ PARAMETRE ---
t1, t2 = st.columns(2)
with t1:
    d = st.number_input("Priemer d [mm]", min_value=0.1, value=20.0)
    l = st.number_input("Dĺžka l [mm]", min_value=0.1, value=50.0)
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
with t2:
    narocnost = st.select_slider("Náročnosť", options=["1", "2", "3", "4", "5"], value="3")
    # Hustota
    hustota = 0.0
    if material == "NEREZ": hustota = 8000.0
    elif material == "OCEĽ": hustota = 7900.0
    elif material == "PLAST":
        try: hustota = clean_num(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
        except: hustota = 1200.0
    elif material == "FAREBNÉ KOVY":
        hustota = 4500.0 if str(akost).startswith("3.7") else (2900.0 if str(akost).startswith("3.") else 9000.0)
    st.metric("Hustota", f"{hustota} kg/m³")

# Výpočty
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)
plocha_plasta = math.pi * d * l
plocha_prierezu = (math.pi * (d**2)) / 4

st.divider()

# --- 5. EKONOMIKA (TU TO UŽ NESPADNE) ---
st.subheader("💰 Ekonomika")

# 5.1 Materiál
cena_material = 0.0
res_mat = df_cennik[(df_cennik['material'] == material) & (df_cennik['akost'] == akost) & (df_cennik.get('d', d) >= d)]
if not res_mat.empty:
    row_m = res_mat.sort_values('d').iloc[0]
    cena_material = (clean_num(row_m.get('cena', 0)) * l) / 1000
    st.info(f"Materiál OK: {cena_material:.4f} €/ks")
else:
    cena_material = st.number_input("Manuálna cena materiálu/ks [€]", 0.0)

# 5.2 Kooperácia (Ošetrené proti KeyError)
ma_koop = st.radio("Kooperácia?", ["Nie", "Áno"], horizontal=True)
cena_kooperacia = 0.0
if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
    if not df_k_f.empty:
        vybrany_druh = st.selectbox("Druh kooperácie", sorted(df_k_f['druh'].unique()))
        rk = df_k_f[df_k_f['druh'] == vybrany_druh].iloc[0]
        
        # .get() vráti None ak stĺpec neexistuje, clean_num to potom zmení na 0.0
        tarifa = clean_num(rk.get('tarifa', 0))
        min_zak = clean_num(rk.get('minimalna_zakazka', 0))
        jednotka = str(rk.get('jednotka', 'kg')).lower()
        
        odhad = (tarifa * hmotnost) if 'kg' in jednotka else (tarifa * plocha_plasta / 10000)
        cena_kooperacia = max(odhad, min_zak / pocet_kusov)
        st.info(f"Kooperácia OK: {cena_kooperacia:.4f} €/ks")
    else:
        cena_kooperacia = st.number_input("Manuálna cena kooperácie/ks [€]", 0.0)

vstupne_naklady = cena_material + cena_kooperacia

# --- 6. AI PREDIKCIA (S logaritmicou opravou) ---
st.divider()
st.subheader("🤖 AI Výpočet")
pred_cas, pred_cena = 0.0, 0.0
model_ok = False

if ai["m1"] and ai["cols1"]:
    try:
        # Pripravíme dáta presne podľa tréningu
        vstup1 = {
            'd': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 
            'plocha_prierezu': plocha_prierezu, 'plocha_plasta': plocha_plasta,
            'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady
        }
        # One-hot encoding (materiál, akosť, náročnosť)
        for c in ai["cols1"]:
            if c not in vstup1: vstup1[c] = 0
            if c == f"material_{str(material).upper()}": vstup1[c] = 1
            if c == f"akost_{str(akost).upper()}": vstup1[c] = 1
            if c == f"narocnost_{narocnost}": vstup1[c] = 1
        
        # Predikcia Času
        df_vstup1 = pd.DataFrame([vstup1])[ai["cols1"]]
        pred_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(df_vstup1))[0]))

        # Predikcia Ceny (Model 2)
        if ai["m2"] and ai["cols2"] and pred_cas > 0:
            vstup2 = {
                'cas': pred_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 
                'hustota': hustota, 'plocha_prierezu': plocha_prierezu
            }
            for c in ai["cols2"]:
                if c not in vstup2: vstup2[c] = 0
                if c == f"krajina_{str(krajina).upper()}": vstup2[c] = 1
            
            df_vstup2 = pd.DataFrame([vstup2])[ai["cols2"]]
            pred_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(df_vstup2))[0]))
            if pred_cena > 0.01: model_ok = True
    except Exception as e:
        st.warning(f"AI narazilo na technický problém: {e}")

if model_ok:
    st.success(f"AI Výsledok: {pred_cas:.2f} min | {pred_cena:.2f} €/ks")
    finalna_cena = st.number_input("Potvrdiť predajnú cenu [€]", value=float(round(pred_cena, 2)))
else:
    st.error("⚠️ AI nevie predikovať (nedostatok dát) - zadaj cenu manuálne")
    finalna_cena = st.number_input("Manuálna predajná cena [€]", 0.0)

# --- 7. FINÁLNY PREHĽAD ---
st.divider()
st.subheader("📝 Prehľad kalkulácie")
st.table(pd.DataFrame({
    "Parameter": ["Diel", "Materiál", "Hmotnosť (kg)", "Vstupné náklady", "Odhadovaný čas", "Predajná cena"],
    "Hodnota": [item_name, material, round(hmotnost, 4), f"{vstupne_naklady:.4f} €", f"{pred_cas:.2f} min", f"{finalna_cena:.2f} €"]
}))
