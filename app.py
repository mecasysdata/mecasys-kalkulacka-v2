import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
import requests
from datetime import date

# --- 1. NAČÍTANIE DÁT (Tvoja overená verzia) ---
st.set_page_config(page_title="Kalkulačný systém", layout="wide")

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
    except: return pd.DataFrame()

# Načítanie modelov (beží na pozadí)
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

# --- 3. MATERIÁL A ROZMERY (Tvoja verzia) ---
col_m1, col_m2 = st.columns(2)
with col_m1:
    material = st.selectbox("Materiál", sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else [])
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique().tolist()) if not df_f.empty else [])
    d = st.number_input("Priemer d [mm]", min_value=0.1, value=20.0)
    l = st.number_input("Dĺžka l [mm]", min_value=0.1, value=50.0)

with col_m2:
    hustota = 0.0
    if material == "NEREZ": hustota = 8000.0
    elif material == "OCEĽ": hustota = 7900.0
    elif material == "PLAST":
        try: hustota = float(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
        except: hustota = 0.0
    elif material == "FAREBNÉ KOVY":
        ako_s = str(akost)
        hustota = 4500.0 if ako_s.startswith("3.7") else (2900.0 if ako_s.startswith("3.") else 9000.0)
    st.metric("Hustota (kg/m³)", f"{hustota}")
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

# Geometria
plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

# --- 4. EKONOMIKA (Tvoja verzia - opravená) ---
st.divider()
cena_material = 0.0
res_mat = df_cennik[(df_cennik['material'] == material) & (df_cennik['akost'] == akost) & (df_cennik['d'] >= d)]
if not res_mat.empty:
    row_m = res_mat.sort_values('d').iloc[0]
    cena_material = (float(row_m['cena']) * l) / 1000
    st.success(f"✅ Materiál OK: {cena_material:.4f} €/ks")
else:
    cena_material = st.number_input("Cena materiálu manuálne", 0.0)

ma_koop = st.radio("Kooperácia?", ["Nie", "Áno"], horizontal=True)
cena_kooperacia = 0.0
if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
    if not df_k_f.empty:
        vybrany_druh = st.selectbox("Druh kooperácie", sorted(df_k_f['druh'].unique()))
        rk = df_k_f[df_k_f['druh'] == vybrany_druh].iloc[0]
        # Tu používam presne tvoj názov stĺpca 'minimalna_zakazka'
        tarifa = float(rk['tarifa'])
        min_zak = float(rk['minimalna_zakazka'])
        jednotka = str(rk['jednotka']).strip().lower()
        odhad = (tarifa * hmotnost) if jednotka == 'kg' else (tarifa * plocha_plasta / 10000)
        cena_kooperacia = max(odhad, min_zak / pocet_kusov)
    else:
        cena_kooperacia = st.number_input("Cena kooperácie manuálne", 0.0)

vstupne_naklady = cena_material + cena_kooperacia

# --- 5. AI PREDIKCIA (Vložená časť) ---
st.divider()
st.subheader("🤖 AI Výpočet")
pred_cas, pred_cena = 0.0, 0.0
model_ok = False

if ai["m1"] and ai["cols1"]:
    try:
        # Príprava dát pre Model 1
        r1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': plocha_prierezu,
              'plocha_plasta': plocha_plasta, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
        for c in ai["cols1"]:
            if c not in r1: r1[c] = 0
            if c == f"material_{str(material).upper()}": r1[c] = 1
            if c == f"akost_{str(akost).upper()}": r1[c] = 1
            if c == f"narocnost_{narocnost}": r1[c] = 1
        
        # Predikcia Času
        pred_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([r1])[ai["cols1"]]))[0]))

        # Predikcia Ceny
        if ai["m2"] and ai["cols2"] and pred_cas > 0:
            r2 = {'cas': pred_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': plocha_prierezu}
            for c in ai["cols2"]:
                if c not in r2: r2[c] = 0
                if c == f"krajina_{str(krajina).upper()}": r2[c] = 1
            pred_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([r2])[ai["cols2"]]))[0]))
            if pred_cena > 0.01: model_ok = True
    except: pass

if model_ok:
    st.success(f"AI: {pred_cas:.2f} min | {pred_cena:.2f} €/ks")
    final_cena = st.number_input("Konečná cena [€]", value=float(round(pred_cena, 2)))
else:
    st.error("⚠️ Model predikuje chybu")
    final_cena = st.number_input("Zadaj cenu manuálne [€]", 0.0)

# --- 6. TABUĽKA (Tvoja požiadavka) ---
st.table(pd.DataFrame({
    "Premenná": ["Materiál", "Hustota", "Hmotnosť [kg]", "Vstupné náklady [€/ks]", "AI Čas [min]", "AI Cena [€/ks]"],
    "Hodnota": [material, hustota, round(hmotnost, 4), round(vstupne_naklady, 4), round(pred_cas, 2), round(final_cena, 2)]
}))
