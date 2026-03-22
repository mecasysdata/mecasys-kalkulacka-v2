import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
import requests
from datetime import date

# --- 1. KONFIGURÁCIA A NAČÍTANIE DÁT ---
st.set_page_config(page_title="MECASYS AI Systém V9.5", layout="wide")

if 'kosik' not in st.session_state:
    st.session_state.kosik = []

# Prepojenia na Google Sheets
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbwcpPJfA1R_ZQP4h6Uj-QNObxoTwO_9TxSLR_Ki75E-cZCvQ3XTlNN0wOzVZShWv1iKbQ/exec"
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
SHEET_ZAKAZNICI = f"{URL_BASE}gid=324957857&single=true&output=csv"
SHEET_MATERIALY = f"{URL_BASE}gid=1281008948&single=true&output=csv"
SHEET_CENNIK    = f"{URL_BASE}gid=901617097&single=true&output=csv"
SHEET_KOOPERACIE= f"{URL_BASE}gid=1180392224&single=true&output=csv"

def safe_num(val):
    if pd.isna(val) or val == "": return 0.0
    try:
        s = str(val).replace(' ', '').replace('€', '').replace(',', '.')
        return float(s)
    except: return 0.0

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
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

st.title("⚙️ Komplexný kalkulačný systém V9.5")

# --- 2. IDENTIFIKÁCIA A ZÁKAZNÍK ---
st.subheader("1. Identifikácia a Zákazník")
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
    zakaznik, krajina, lojalita = "", "SK", 0.5
    if vyber_z != "--- Vyber ---" and vyber_z != "Nový zákazník (manual)":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik, krajina, lojalita = vyber_z, str(dz['krajina']).upper(), safe_num(dz['lojalita'])
        st.info(f"✅ {krajina} | Lojalita: {lojalita}")

st.divider()

# --- 3. TECHNICKÉ PARAMETRE ---
st.subheader("2. Materiál a rozmery")
t1, t2, t3 = st.columns(3)

with t1:
    material = st.selectbox("Materiál", sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else [])
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique().tolist()) if not df_f.empty else [])
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

with t2:
    d = st.number_input("Priemer d [mm]", min_value=0.1, value=20.0, format="%.2f")
    l = st.number_input("Dĺžka l [mm]", min_value=0.1, value=50.0, format="%.2f")
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)

with t3:
    # Logika hustoty
    hustota = 0.0
    if material == "NEREZ": hustota = 8000.0
    elif material == "OCEĽ": hustota = 7900.0
    elif material == "PLAST":
        try: hustota = safe_num(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
        except: hustota = 0.0
    elif material == "FAREBNÉ KOVY":
        ako_s = str(akost)
        if ako_s.startswith("3.7"): hustota = 4500.0
        elif ako_s.startswith("3."): hustota = 2900.0
        else: hustota = 9000.0
    
    st.metric("Hustota", f"{hustota} kg/m³")
    plocha_prierezu = (math.pi * (d**2)) / 4
    plocha_plasta = math.pi * d * l
    hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

st.divider()

# --- 4. EKONOMIKA (VSTUPNÉ NÁKLADY) ---
st.subheader("3. Ekonomika")
e1, e2 = st.columns(2)

with e1:
    cena_material = 0.0
    if not df_cennik.empty:
        df_c_temp = df_cennik.copy()
        df_c_temp['d_n'] = df_c_temp['d'].apply(safe_num)
        res_mat = df_c_temp[(df_c_temp['material'] == material) & (df_c_temp['akost'] == akost) & (df_c_temp['d_n'] >= d)]
        if not res_mat.empty:
            row_m = res_mat.sort_values('d_n').iloc[0]
            cena_material = (safe_num(row_m['cena']) * l) / 1000
            st.success(f"Materiál OK: {cena_material:.4f} €/ks")
        else:
            cena_material = st.number_input("Manuálna cena materiálu [€/ks]", 0.0, format="%.4f")

with e2:
    ma_koop = st.radio("Kooperácia?", ["Nie", "Áno"], horizontal=True)
    cena_kooperacia = 0.0
    if ma_koop == "Áno":
        df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
        if not df_k_f.empty:
            vybrany_druh = st.selectbox("Druh kooperácie", sorted(df_k_f['druh'].unique()))
            rk = df_k_f[df_k_f['druh'] == vybrany_druh].iloc[0]
            tarifa = safe_num(rk.get('tarifa', 0))
            min_zak = 0.0
            for col in rk.index:
                if 'min' in col.lower(): min_zak = safe_num(rk[col])
            
            jednotka = str(rk.get('jednotka', 'kg')).lower()
            odhad = (tarifa * hmotnost) if 'kg' in jednotka else (tarifa * plocha_plasta / 10000)
            cena_kooperacia = max(odhad, min_zak / pocet_kusov)
        else:
            cena_kooperacia = st.number_input("Manuálna cena kooperácie [€/ks]", 0.0, format="%.4f")

vstupne_naklady = cena_material + cena_kooperacia

st.divider()

# --- 5. AI PREDIKCIA (MATEMATICKY SYNCHRONIZOVANÁ) ---
st.subheader("🤖 4. AI Výpočet ceny a času")
pred_cas, pred_cena = 0.0, 0.0
model_uspesny = False

if ai["m1"] and ai["cols1"]:
    try:
        # MODEL 1 (ČAS) - Logaritmizácia vstupu aj výstupu
        r1 = {
            'd': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 
            'plocha_prierezu': plocha_prierezu, 'plocha_plasta': plocha_plasta, 
            'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady
        }
        for c in ai["cols1"]:
            if c not in r1: r1[c] = 0
            if c == f"material_{str(material).upper()}": r1[c] = 1
            if c == f"akost_{str(akost).upper()}": r1[c] = 1
            if c == f"narocnost_{narocnost}": r1[c] = 1
        
        dmat1 = xgb.DMatrix(pd.DataFrame([r1])[ai["cols1"]])
        pred_cas = float(np.expm1(ai["m1"].predict(dmat1)[0]))

        # MODEL 2 (CENA) - Logaritmizácia výstupu
        if ai["m2"] and ai["cols2"] and pred_cas > 0:
            r2 = {
                'cas': pred_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 
                'hustota': hustota, 'plocha_prierezu': plocha_prierezu
            }
            for c in ai["cols2"]:
                if c not in r2: r2[c] = 0
                if c == f"krajina_{str(krajina).upper()}": r2[c] = 1
            
            dmat2 = xgb.DMatrix(pd.DataFrame([r2])[ai["cols2"]])
            pred_cena = float(np.expm1(ai["m2"].predict(dmat2)[0]))
            
            if pred_cena > 0.01: model_uspesny = True
    except:
        model_uspesny = False

if model_uspesny:
    st.success(f"AI odporúča: Čas: {pred_cas:.2f} min | Cena: {pred_cena:.2f} €/ks")
    final_cena = st.number_input("Finálna cena na kus [€]", value=float(round(pred_cena, 2)))
else:
    st.error("⚠️ Model predikuje chybu")
    final_cena = st.number_input("Zadaj cenu manuálne [€]", value=0.0)

# --- 6. KOŠÍK A SUMÁR ---
if st.button("➕ PRIDAŤ DO PONUKY"):
    st.session_state.kosik.append({
        "Položka": item, "Materiál": material, "Akosť": akost, "Ks": pocet_kusov,
        "Čas [min]": round(pred_cas, 2), "Cena/ks [€]": round(final_cena, 2),
        "Celkom [€]": round(final_cena * pocet_kusov, 2),
        "Vstup/ks": round(vstupne_naklady, 4), "Hmotnosť": round(hmotnost, 4),
        "Ponuka": ponuka, "Zákazník": zakaznik, "Dátum": str(datum)
    })
    st.rerun()

if st.session_state.kosik:
    st.divider()
    st.subheader("📋 Rozpracovaná ponuka")
    df_k = pd.DataFrame(st.session_state.kosik)
    st.table(df_k[["Položka", "Materiál", "Ks", "Čas [min]", "Cena/ks [€]", "Celkom [€]"]])
    
    col_send1, col_send2 = st.columns(2)
    with col_send1:
        if st.button("💾 ODOŠLAŤ DO GOOGLE SHEETU"):
            for p in st.session_state.kosik:
                requests.post(URL_APPS_SCRIPT, json=p)
            st.success("Dáta úspešne odoslané!")
            st.session_state.kosik = []
            st.rerun()
    with col_send2:
        if st.button("🗑️ VYMAZAŤ"):
            st.session_state.kosik = []
            st.rerun()
