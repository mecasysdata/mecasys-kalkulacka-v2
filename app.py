import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
import requests
from datetime import date

# --- 1. KONFIGURÁCIA A NAČÍTANIE DÁT (Tvoja verzia) ---
st.set_page_config(page_title="MECASYS AI Kalkulátor", layout="wide")

if 'kosik' not in st.session_state:
    st.session_state.kosik = []

URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbwcpPJfA1R_ZQP4h6Uj-QNObxoTwO_9TxSLR_Ki75E-cZCvQ3XTlNN0wOzVZShWv1iKbQ/exec"
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

st.title("⚙️ Komplexný kalkulačný systém")

# --- 2. IDENTIFIKÁCIA A ZÁKAZNÍK (Tvoja verzia) ---
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
    zakaznik, krajina, lojalita = "", "", 0.0

    if vyber_z == "Nový zákazník (manual)":
        zakaznik = st.text_input("Meno nového zákazníka")
        krajina = st.text_input("Krajina")
        lojalita = 0.5
    elif vyber_z != "--- Vyber ---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik, krajina, lojalita = vyber_z, str(dz['krajina']), float(dz['lojalita'])
        st.info(f"✅ Zákazník: {krajina} | Lojalita: {lojalita}")

st.divider()

# --- 3. MATERIÁL A HUSTOTA (Tvoja verzia) ---
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
        akost = st.text_input("Zadaj názov novej akosti")
        hustota = st.number_input("Zadaj hustotu!", min_value=0.0)
    else:
        akost = vyber_ako
        if material == "NEREZ": hustota = 8000.0
        elif material == "OCEĽ": hustota = 7900.0
        elif material == "PLAST":
            try: hustota = float(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
            except: hustota = 0.0
        elif material == "FAREBNÉ KOVY":
            ako_s = str(akost)
            hustota = 4500.0 if ako_s.startswith("3.7") else (2900.0 if ako_s.startswith("3.") else 9000.0)
        st.metric("Hustota (kg/m³)", f"{hustota}")

st.divider()

# --- 4. ROZMERY A GEOMETRIA (Tvoja verzia) ---
st.subheader("3. Technické parametre")
col_p1, col_p2 = st.columns(2)
with col_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.1, value=20.0, format="%.2f")
    l = st.number_input("Dĺžka l [mm]", min_value=0.1, value=50.0, format="%.2f")
with col_p2:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

st.divider()

# --- 5. EKONOMIKA (Tvoja verzia) ---
st.subheader("4. Ekonomika")
cena_material = 0.0
res_mat = df_cennik[(df_cennik['material'] == material) & (df_cennik['akost'] == akost) & (df_cennik['d'] >= d)]
if not res_mat.empty:
    row_m = res_mat.sort_values('d').iloc[0]
    cena_material = (float(row_m['cena']) * l) / 1000
    st.success(f"✅ Materiál nájdený: {cena_material:.4f} €/ks")
else:
    cena_material = st.number_input("Zadaj cenu materiálu na 1ks manuálne [€]", min_value=0.0)

ma_koop = st.radio("Vyžaduje diel kooperáciu?", ["Nie", "Áno"], horizontal=True)
cena_kooperacia, vybrany_druh_koop = 0.0, "Žiadna"
if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
    list_k = sorted(df_k_f['druh'].unique().tolist()) if not df_k_f.empty else []
    if list_k:
        vybrany_druh_koop = st.selectbox("Druh kooperácie", list_k)
        rk = df_k_f[df_k_f['druh'] == vybrany_druh_koop].iloc[0]
        tarifa, min_zak = float(rk['tarifa']), float(rk['minimalna_zakazka'])
        jednotka_koop = str(rk['jednotka']).strip().lower()
        odhad = (tarifa * hmotnost) if jednotka_koop == 'kg' else (tarifa * plocha_plasta / 10000)
        cena_kooperacia = max(odhad, min_zak / pocet_kusov)
    else:
        cena_kooperacia = st.number_input("Zadaj cenu kooperácie na 1ks manuálne [€]", min_value=0.0)

vstupne_naklady = cena_material + cena_kooperacia

# --- 6. AI PREDIKCIA (OPRAVENÁ ČASŤ) ---
st.divider()
st.subheader("🤖 5. AI Predikcia")
pred_cas, pred_cena = 0.0, 0.0
model_ok = False

if ai["m1"] and ai["cols1"]:
    try:
        # Príprava pre M1 (Čas) - logaritmizácia vstupu pocet_kusov
        r1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': plocha_prierezu,
              'plocha_plasta': plocha_plasta, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
        for c in ai["cols1"]:
            if c not in r1: r1[c] = 0
            if c == f"material_{str(material).upper()}": r1[c] = 1
            if c == f"akost_{str(akost).upper()}": r1[c] = 1
            if c == f"narocnost_{narocnost}": r1[c] = 1
        
        # Predikcia Času (expm1)
        pred_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([r1])[ai["cols1"]]))[0]))

        if ai["m2"] and ai["cols2"] and pred_cas > 0:
            # Príprava pre M2 (Cena)
            r2 = {'cas': pred_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': plocha_prierezu}
            for c in ai["cols2"]:
                if c not in r2: r2[c] = 0
                if c == f"krajina_{str(krajina).upper()}": r2[c] = 1
            
            # Predikcia Ceny (expm1)
            pred_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([r2])[ai["cols2"]]))[0]))
            if pred_cena > 0.01: model_ok = True
    except: pass

if model_ok:
    st.success(f"AI odporúča: Čas: {pred_cas:.2f} min | Cena: {pred_cena:.2f} €/ks")
    finalna_cena = st.number_input("Upraviť cenu [€]", value=float(round(pred_cena, 2)))
else:
    st.error("⚠️ Model predikuje chybu - zadaj manuálne")
    finalna_cena = st.number_input("Manuálna predajná cena [€]", value=0.0)

# --- 7. KOŠÍK ---
if st.button("➕ PRIDAŤ DO PONUKY"):
    st.session_state.kosik.append({
        "Item": item, "Ks": pocet_kusov, "Cena/ks": round(finalna_cena, 2), "Celkom": round(finalna_cena * pocet_kusov, 2),
        "Čas": round(pred_cas, 2), "Vstup": round(vstupne_naklady, 4), "Zákazník": zakaznik
    })
    st.rerun()

if st.session_state.kosik:
    st.table(pd.DataFrame(st.session_state.kosik))
