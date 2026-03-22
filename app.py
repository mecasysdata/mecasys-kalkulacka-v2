import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
import requests
from datetime import datetime

# --- 1. POMOCNÉ FUNKCIE ---
def safe_num(val):
    if pd.isna(val) or val == "": return 0.0
    try:
        s = str(val).replace(',', '').replace(' ', '').replace('€', '')
        return float(s)
    except: return 0.0

# --- 2. KONFIGURÁCIA A PAMÄŤ (SESSION STATE) ---
st.set_page_config(page_title="MECASYS AI - Ponukový Systém", layout="wide")

# Inicializácia košíka, ak ešte neexistuje
if 'kosik' not in st.session_state:
    st.session_state.kosik = []

# URL tvojho Google Apps Scriptu
WEBHOOK_URL = "SEM_VLOZ_SVOJU_URL_Z_APPS_SCRIPTU"

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
        m1 = xgb.Booster(); m1.load_model(f"{p}finalny_model.json")
        with open(f"{p}stlpce_modelu.pkl", 'rb') as f: assets["cols1"] = pickle.load(f)
        assets["m1"] = m1
        m2 = xgb.Booster(); m2.load_model(f"{p}xgb_model_cena.json")
        with open(f"{p}model_columns.pkl", 'rb') as f: assets["cols2"] = pickle.load(f)
        assets["m2"] = m2
    except: st.error("⚠️ AI modely nenájdené v MECASYS_APP/")
    return assets

# Načítanie dát
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
df_zakaznici = load_data(f"{URL_BASE}gid=324957857&single=true&output=csv")
df_mat = load_data(f"{URL_BASE}gid=1281008948&single=true&output=csv")
df_cennik = load_data(f"{URL_BASE}gid=901617097&single=true&output=csv")
df_koop = load_data(f"{URL_BASE}gid=1180392224&single=true&output=csv")
ai = load_ai_models()

# --- 3. HLAVIČKA PONUKY (Spoločná pre všetky položky) ---
st.title("📑 MECASYS: Generátor hromadnej ponuky")

h1, h2, h3 = st.columns(3)
with h1:
    cislo_cp = st.text_input("Číslo CP", value=datetime.now().strftime("%Y-%m") + "-001")
with h2:
    vyber_z = st.selectbox("Zákazník", sorted(df_zakaznici['zakaznik'].unique()) if not df_zakaznici.empty else ["---"])
with h3:
    datum_dnes = st.date_input("Dátum", datetime.now())

dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0] if not df_zakaznici.empty else {}
lojalita = safe_num(dz.get('lojalita', 0.5))
krajina = str(dz.get('krajina', 'SK'))

# --- 4. EDITOR POLOŽKY (Presne tvoja logika) ---
st.divider()
st.subheader("🛠️ Parametre novej položky")

e1, e2, e3 = st.columns(3)
with e1:
    item_nazov = st.text_input("Názov ITEM", value=f"Položka {len(st.session_state.kosik)+1}")
    material = st.selectbox("Materiál", sorted(df_mat['material'].unique()))
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique()))
with e2:
    d = st.number_input("Priemer d [mm]", value=20.0)
    l = st.number_input("Dĺžka l [mm]", value=50.0)
    pocet_kusov = st.number_input("Počet kusov", min_value=1, value=1)
with e3:
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")
    druhy_koop = ["Bez kooperácie"] + sorted(df_koop['druh'].unique().tolist())
    vybrana_koop = st.selectbox("Kooperácia", druhy_koop)

# --- LOGIKA VÝPOČTOV (Identická ako predtým) ---
hustota = 7900.0
if material == "NEREZ": hustota = 8000.0
elif material == "PLAST":
    p_match = df_f[df_f['akost'] == akost]
    hustota = safe_num(p_match['hustota'].iloc[0]) if not p_match.empty else 1200.0
    if hustota < 100: hustota = 1200.0

hmotnost = hustota * (math.pi/4) * (d/1000)**2 * (l/1000)
plocha_plasta = math.pi * d * l
plocha_prierezu = (math.pi * d**2) / 4

# --- MATERIÁL NÁKLAD ---
res_m = df_cennik[(df_cennik['material']==material)&(df_cennik['akost']==akost)&(df_cennik['d']>=d)].sort_values('d')
j_mat_m = safe_num(res_m.iloc[0]['cena']) if not res_m.empty else 0.0

c_m1, c_m2 = st.columns(2)
with c_m1:
    j_mat_potvrdena = st.number_input("J. cena mat. [€/m]", value=j_mat_m, format="%.2f", key="jmat")
with c_m2:
    naklad_mat_ks = st.number_input("Náklad materiál/ks [€]", value=(j_mat_potvrdena * l / 1000), format="%.3f", key="nmat")

# --- KOOPERÁCIA NÁKLAD ---
vypocitana_koop_ks = 0.0
if vybrana_koop != "Bez kooperácie":
    match_k = df_koop[(df_koop['druh'] == vybrana_koop) & (df_koop['material'] == material)]
    if not match_k.empty:
        rk = match_k.iloc[0]; tar = safe_num(rk.get('tarifa', 0)); minz = safe_num(rk.get('minimalna_zakazka', 0)); jedn = str(rk.get('jednotka', 'kg')).lower()
        zaklad = (tar * hmotnost) if 'kg' in jedn else (tar * (plocha_plasta / 10000))
        vypocitana_koop_ks = max(zaklad, minz / pocet_kusov)

naklad_koop_ks = st.number_input("Náklad kooperácia/ks [€]", value=vypocitana_koop_ks, format="%.3f", key="nkoop")
vstupne_naklady = naklad_mat_ks + naklad_koop_ks

# --- AI PREDIKCIA ---
ai_cas, ai_cena = 0.0, 0.0
if ai["m1"] and ai["m2"]:
    v1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': plocha_prierezu, 'plocha_plasta': plocha_plasta, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
    for c in ai["cols1"]:
        if c not in v1: v1[c] = 0
        if c == f"material_{material}": v1[c] = 1
        if c == f"narocnost_{narocnost}": v1[c] = 1
    ai_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([v1])[ai["cols1"]]))[0]))
    
    v2 = {'cas': ai_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': plocha_prierezu}
    for c in ai["cols2"]:
        if c not in v2: v2[c] = 0
        if c == f"krajina_{krajina}": v2[c] = 1
    ai_cena = max(float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]]))[0])), vstupne_naklady * 1.2)

# --- TLAČIDLO PRIDANIA ---
if st.button("➕ Pridať túto položku do zoznamu", type="primary"):
    nova_polozka = {
        "datum": datum_dnes.strftime("%d.%m.%Y"), "ponuka": cislo_cp, "zakaznik": vyber_z, "krajina": krajina, "lojalita": lojalita, "item": item_nazov, "material": material, "akost": akost, "d": d, "l": l, "hustota": hustota, "hmotnost": hmotnost, "narocnost": narocnost, "jednotkova_mat": j_mat_potvrdena, "naklad_mat_celkom": naklad_mat_ks, "cena_kooperacia": naklad_koop_ks, "vstupne_naklady": vstupne_naklady, "ai_cas": ai_cas, "ai_cena": ai_cena, "pocet_kusov": pocet_kusov, "cena_polozky_spolu": ai_cena * pocet_kusov
    }
    st.session_state.kosik.append(nova_polozka)
    st.toast(f"Položka {item_nazov} bola pridaná do zoznamu.")

# --- 5. PREHĽAD "KOŠÍKA" A ODOSLANIE ---
if st.session_state.kosik:
    st.divider()
    st.subheader("📋 Položky v aktuálnej ponuke")
    df_prehlad = pd.DataFrame(st.session_state.kosik)
    st.dataframe(df_prehlad[["item", "material", "akost", "pocet_kusov", "ai_cena", "cena_polozky_spolu"]], use_container_width=True)
    
    st.write(f"**Celková hodnota CP: {df_prehlad['cena_polozky_spolu'].sum():.2f} €**")
    
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🗑️ Vymazať zoznam"):
            st.session_state.kosik = []
            st.rerun()
    with b2:
        if st.button("🚀 ODOVZDAŤ PONUKU (Nahrať do databázy)"):
            with st.spinner("Zapisujem položky..."):
                uspech = True
                for p in st.session_state.kosik:
                    r = requests.post(WEBHOOK_URL, json=p)
                    if r.status_code != 200: uspech = False
                if uspech:
                    st.success(f"Všetkých {len(st.session_state.kosik)} položiek bolo úspešne uložených!")
                    st.session_state.kosik = [] # Reset po odoslaní
                else:
                    st.error("Chyba pri nahrávaní. Skontrolujte pripojenie.")
