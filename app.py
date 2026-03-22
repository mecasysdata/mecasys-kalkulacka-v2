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

# --- 2. KONFIGURÁCIA ---
st.set_page_config(page_title="MECASYS AI - FINÁLNA VERZIA", layout="wide")

# SEM VLOŽ SVOJU URL PO NASADENÍ (DEPLOY) APPS SCRIPTU
WEBHOOK_URL = "SEM_VLOZ_TVOJU_URL_Z_APPS_SCRIPTU"

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
    except: st.error("POZOR: AI modely nenájdené v priečinku MECASYS_APP/")
    return assets

# Google Sheets linky
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
df_zakaznici = load_data(f"{URL_BASE}gid=324957857&single=true&output=csv")
df_mat = load_data(f"{URL_BASE}gid=1281008948&single=true&output=csv")
df_cennik = load_data(f"{URL_BASE}gid=901617097&single=true&output=csv")
df_koop = load_data(f"{URL_BASE}gid=1180392224&single=true&output=csv")
ai = load_ai_models()

# --- 3. VSTUPY: ADMINISTRATÍVA ---
st.title("🚀 MECASYS AI: Profesionálna Kalkulácia")

c0, c1, c2 = st.columns([1, 2, 2])
with c0:
    cislo_cp = st.text_input("Číslo CP", value="2024-001")
with c1:
    vyber_z = st.selectbox("Zákazník", sorted(df_zakaznici['zakaznik'].unique()) if not df_zakaznici.empty else ["---"])
    item_nazov = st.text_input("Názov ITEM (Súčiastka)", value="Hriadeľ")
with c2:
    material = st.selectbox("Materiál", sorted(df_mat['material'].unique()))
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique()))

# Dáta o zákazníkovi pre AI
dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0] if not df_zakaznici.empty else {}
lojalita = safe_num(dz.get('lojalita', 0.5))
krajina = str(dz.get('krajina', 'SK'))

# --- 4. VSTUPY: TECHNICKÉ PARAMETRE ---
st.divider()
t1, t2, t3, t4 = st.columns(4)
with t1:
    d = st.number_input("Priemer d [mm]", value=20.0)
with t2:
    l = st.number_input("Dĺžka l [mm]", value=50.0)
with t3:
    pocet_kusov = st.number_input("Počet kusov", min_value=1, value=1)
with t4:
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")

# --- 5. HUSTOTA A GEOMETRIA ---
hustota = 7900.0
if material == "NEREZ": hustota = 8000.0
elif material == "OCEĽ": hustota = 7900.0
elif material == "PLAST":
    p_match = df_f[df_f['akost'] == akost]
    hustota = safe_num(p_match['hustota'].iloc[0]) if not p_match.empty else 1200.0
    if hustota < 100: hustota = 1200.0

hmotnost = hustota * (math.pi/4) * (d/1000)**2 * (l/1000)
plocha_plasta = math.pi * d * l
plocha_prierezu = (math.pi * d**2) / 4

# --- 6. EKONOMIKA: MATERIÁL (S MOŽNOSŤOU ÚPRAVY) ---
st.subheader("💰 Kalkulácia nákladov")
res_m = df_cennik[(df_cennik['material']==material)&(df_cennik['akost']==akost)&(df_cennik['d']>=d)].sort_values('d')

jednotkova_mat_m = 0.0
if not res_m.empty:
    jednotkova_mat_m = safe_num(res_m.iloc[0]['cena'])
    vypocitana_cena_mat_ks = (jednotkova_mat_m * l) / 1000
else:
    vypocitana_cena_mat_ks = 0.0

col_m1, col_m2 = st.columns(2)
with col_m1:
    j_cena_mat_potvrdena = st.number_input("J. cena materiálu [€/m]", value=jednotkova_mat_m, format="%.2f")
with col_m2:
    # Ak sa zmení J. cena tyče, prepočíta sa náklad na kus
    naklad_mat_ks = st.number_input("Konečný náklad materiál na KUS [€]", value=(j_cena_mat_potvrdena * l / 1000), format="%.3f")

# --- 7. EKONOMIKA: KOOPERÁCIA (S MOŽNOSŤOU ÚPRAVY) ---
druhy_koop = ["Bez kooperácie"] + sorted(df_koop['druh'].unique().tolist())
vybrana_koop = st.selectbox("Druh kooperácie", druhy_koop)

vypocitana_cena_koop_ks = 0.0
if vybrana_koop != "Bez kooperácie":
    match_k = df_koop[(df_koop['druh'] == vybrana_koop) & (df_koop['material'] == material)]
    if not match_k.empty:
        rk = match_k.iloc[0]
        tar = safe_num(rk.get('tarifa', 0))
        min_z = safe_num(rk.get('minimalna_zakazka', 0))
        j = str(rk.get('jednotka', 'kg')).lower()
        zaklad = (tar * hmotnost) if 'kg' in j else (tar * (plocha_plasta / 10000))
        vypocitana_cena_koop_ks = max(zaklad, min_z / pocet_kusov)

naklad_koop_ks = st.number_input("Konečný náklad kooperácia na KUS [€]", value=vypocitana_cena_koop_ks, format="%.3f")
vstupne_naklady = naklad_mat_ks + naklad_koop_ks

# --- 8. AI PREDIKCIA ---
if ai["m1"] and ai["m2"]:
    # M1: ČAS
    v1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': plocha_prierezu, 
          'plocha_plasta': plocha_plasta, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
    for c in ai["cols1"]:
        if c not in v1: v1[c] = 0
        if c == f"material_{material}": v1[c] = 1
        if c == f"narocnost_{narocnost}": v1[c] = 1
    
    ai_cas_min = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([v1])[ai["cols1"]]))[0]))

    # M2: CENA
    v2 = {'cas': ai_cas_min, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': plocha_prierezu}
    for c in ai["cols2"]:
        if c not in v2: v2[c] = 0
        if c == f"krajina_{krajina}": v2[c] = 1
    
    pred_ai_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]]))[0]))
    
    # Finálna predajná cena na kus (AI vs. Náklady)
    jednotkova_cena_predaj = max(pred_ai_cena, vstupne_naklady * 1.2)
    cena_spolu_polozka = jednotkova_cena_predaj * pocet_kusov

    st.divider()
    r1, r2, r3 = st.columns(3)
    r1.metric("Odhadovaný čas", f"{ai_cas_min:.2f} min")
    r2.metric("Jednotková cena (Predaj)", f"{jednotkova_cena_predaj:.2f} €")
    r3.metric("Cena spolu", f"{cena_spolu_polozka:.2f} €")

    # --- 9. ODOVZDANIE A ZÁPIS (ODOSIELANIE DO SHEETU) ---
    if st.button("💾 ULOŽIŤ A ODOSLAŤ PONUKU"):
        # PRÍPRAVA DÁT PRESNE PODĽA TVOJHO APPS SCRIPTU
        payload = {
            "datum": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "ponuka": cislo_cp,
            "zakaznik": vyber_z,
            "krajina": krajina,
            "lojalita": lojalita,
            "item": item_nazov,
            "material": material,
            "akost": akost,
            "d": d,
            "l": l,
            "hustota": hustota,
            "hmotnost": hmotnost,
            "narocnost": narocnost,
            "jednotkova_mat": j_cena_mat_potvrdena,
            "naklad_mat_celkom": naklad_mat_ks,
            "cena_kooperacia": naklad_koop_ks,
            "vstupne_naklady": vstupne_naklady,
            "ai_cas": ai_cas_min,
            "ai_cena": jednotkova_cena_predaj,
            "pocet_kusov": pocet_kusov,
            "cena_polozky_spolu": cena_spolu_polozka
        }
        
        try:
            with st.spinner("Zapisujem do databázy..."):
                response = requests.post(WEBHOOK_URL, json=payload)
                if response.status_code == 200:
                    st.success(f"✅ Ponuka {cislo_cp} bola úspešne uložená do Google Sheetu!")
                else:
                    st.error("❌ Chyba pri komunikácii so scriptom. Skontroluj 'Nasadenie' (Deployment).")
        except Exception as e:
            st.error(f"❌ Nepodarilo sa odoslať dáta: {e}")

else:
    st.warning("⚠️ Nahrajte AI modely do priečinka MECASYS_APP/ pre spustenie predikcie.")
