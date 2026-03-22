import streamlit as st
import pandas as pd
import numpy as np
import math
import pickle
import os
import requests
from io import StringIO
from datetime import date
from xgboost import XGBRegressor

# --- 1. KONFIGURÁCIA ---
st.set_page_config(page_title="Mecasys AI PRO", layout="wide")

URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbxv1GNG0Yx7t0TiY4qj2rhK4RN3cEC4fwd1J5A8M33xKL3qgHf_WGPDzCbvrie9vXQu/exec"

URLS = {
    "cisnik": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv",
    "mat_cena": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv",
    "zakaznici": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv",
    "koop": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv"
}

if 'items_cp' not in st.session_state:
    st.session_state.items_cp = []

@st.cache_data(ttl=600)
def load_csv(url):
    try:
        r = requests.get(url, timeout=10)
        r.encoding = 'utf-8'
        df = pd.read_csv(StringIO(r.text))
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

@st.cache_resource
def load_models():
    p = 'MECASYS_APP'
    m1 = XGBRegressor(); m1.load_model(os.path.join(p, 'finalny_model.json'))
    with open(os.path.join(p, 'stlpce_modelu.pkl'), 'rb') as f: c1 = pickle.load(f)
    m2 = XGBRegressor(); m2.load_model(os.path.join(p, 'xgb_model_cena.json'))
    with open(os.path.join(p, 'model_columns.pkl'), 'rb') as f: c2 = pickle.load(f)
    return m1, c1, m2, c2

df_c, df_m, df_z, df_k = load_csv(URLS["cisnik"]), load_csv(URLS["mat_cena"]), load_csv(URLS["zakaznici"]), load_csv(URLS["koop"])
model1, cols1, model2, cols2 = load_models()

# --- 2. UI ---
st.title("🏭 MECASYS AI PRO")

with st.container(border=True):
    h1, h2, h3 = st.columns(3)
    v_oznacenie_cp = h1.text_input("Číslo CP", value="CP-2026-")
    v_datum_cp = h2.date_input("Dátum CP", date.today())
    v_zakaznik = h3.selectbox("Zákazník", sorted(df_z['zakaznik'].unique()) if not df_z.empty else ["-"])

with st.container(border=True):
    st.subheader("⚙️ Parametre ITEMu")
    c1, c2, c3 = st.columns(3)
    with c1:
        v_item = st.text_input("ITEM (Výkres)")
        v_ks = st.number_input("Počet kusov", 1, value=10)
        v_nar = st.selectbox("Náročnosť (1-5)", ['1','2','3','4','5'], index=2)
    with c2:
        v_mat = st.selectbox("Materiál", sorted(df_c['material'].unique()) if not df_c.empty else [])
        v_ako = st.selectbox("Akosť", sorted(df_c[df_c['material'] == v_mat]['akost'].unique()) if not df_c.empty else [])
        v_d = st.number_input("Priemer d [mm]", 1.0, value=20.0)
        v_l = st.number_input("Dĺžka l [mm]", 1.0, value=100.0)
    with c3:
        v_koop_druh = st.selectbox("Kooperácia", ["Žiadna"] + sorted(df_k['druh'].unique().tolist()))
        v_n_koop_manual = st.number_input("Extra náklad [€/ks]", 0.0)

# --- 3. VÝPOČET ---
if st.button("➕ PRIDAŤ DO PONUKY", use_container_width=True):
    try:
        # Dáta zákazníka
        z_row = df_z[df_z['zakaznik'] == v_zakaznik]
        v_krajina = str(z_row['krajina'].iloc[0]); v_lojalita = float(z_row['lojalita'].iloc[0])

        # Hustota a hmotnosť
        h_row = df_c[(df_c['material'] == v_mat) & (df_c['akost'] == v_ako)]
        v_hustota = float(str(h_row.iloc[0]['hustota']).replace(',','.')) if not h_row.empty else 7850.0
        v_hmotnost = v_hustota * (math.pi/4) * (v_d/1000)**2 * (v_l/1000)

        # Materiál cena
        df_mat_f = df_m[df_m['akost'] == v_ako].copy()
        df_mat_f['d'] = pd.to_numeric(df_mat_f['d'], errors='coerce')
        res_m = df_mat_f[df_mat_f['d'] >= v_d].sort_values('d')
        v_j_cena_m = float(str(res_m.iloc[0]['J.cena/m']).replace(',','.')) if not res_m.empty else 0.0
        v_naklad_m = (v_l/1000) * v_j_cena_m

        # Kooperácia
        v_naklad_k = v_n_koop_manual
        if v_koop_druh != "Žiadna":
            # Hľadáme sadzbu podľa druhu a materiálu (napr. kalenie + OCEĽ)
            k_f = df_k[(df_k['druh'] == v_koop_druh) & (df_k['material'] == v_mat)]
            if not k_f.empty:
                tarifa = float(str(k_f.iloc[0]['tarifa']).replace(',','.'))
                jednotka = str(k_f.iloc[0]['jednotka']).strip()
                v_naklad_k += (tarifa * v_hmotnost) if jednotka == "kg" else tarifa

        # AI Predikcie
        in1 = pd.DataFrame(0.0, index=[0], columns=cols1)
        in1.update({'d':v_d, 'l':v_l, 'plocha_prierezu':(math.pi*v_d**2)/4, 'plocha_plasta':math.pi*v_d*v_l, 'pocet_kusov':np.log1p(float(v_ks))})
        for c in in1.columns:
            if f"MATERIAL_{v_mat}".upper() in c.upper() or f"AKOST_{v_ako}".upper() in c.upper() or f"NAROCNOST_{v_nar}" in c.upper(): in1[c] = 1.0
        v_cas = float(np.expm1(model1.predict(in1.astype('float64'))[0]))

        v_vstupy = v_naklad_m + v_naklad_k
        in2 = pd.DataFrame(0.0, index=[0], columns=cols2)
        in2.update({'cas': v_cas, 'hmotnost': v_hmotnost, 'vstupne_naklady': v_vstupy, 'lojalita': v_lojalita, 'pocet_kusov': np.log1p(float(v_ks))})
        for c in in2.columns:
            if f"KRAJINA_{v_krajina}".upper() in c.upper(): in2[c] = 1.0
        v_cena_ks = float(np.expm1(model2.predict(in2.astype('float64'))[0]))

        # --- SYNC S APPS SCRIPTOM (Kľúče musia sedieť na skript!) ---
        st.session_state.items_cp.append({
            "datum_cp": str(v_datum_cp),
            "cislo_cp": v_oznacenie_cp,
            "zakaznik": v_zakaznik,
            "krajina": v_krajina,
            "lojalita": v_lojalita,
            "item": v_item,
            "material": v_mat,
            "akost": v_ako,
            "d": v_d,
            "l": v_l,
            "hustota": v_hustota,
            "hmotnost": round(v_hmotnost, 4),
            "narocnost": v_nar,
            "j_cena_materialu": round(v_j_cena_m, 2),
            "naklad_material": round(v_naklad_m, 2),
            "naklad_kooperacia": round(v_naklad_k, 2),
            "vstupne_naklady": round(v_vstupy, 2),
            "cas_min": round(v_cas, 2),
            "jednotkova_cena": round(v_cena_ks, 2),
            "pocet_kusov": v_ks,
            "cena_polozky spolu": round(v_cena_ks * v_ks, 2)
        })
        st.rerun()
    except Exception as e: st.error(f"Chyba: {e}")

# --- 4. KOŠÍK ---
if st.session_state.items_cp:
    st.divider()
    st.table(pd.DataFrame(st.session_state.items_cp)[["item", "jednotkova_cena", "cena_polozky spolu"]])
    if st.button("💾 ODOVZDAŤ DO MASTER SHEETU", use_container_width=True):
        # Apps Script očakáva JSON pole objektov
        # DÔLEŽITÉ: Posielame po jednom, alebo upravíme skript, aby prebral celé pole. 
        # Keďže tvoj skript má appendRow(data.datum_cp...), pošleme to v slučke:
        success = True
        for polozka in st.session_state.items_cp:
            resp = requests.post(URL_APPS_SCRIPT, json=polozka)
            if "OK" not in resp.text: success = False
        
        if success:
            st.success("Hotovo! Všetko je v sheete."); st.session_state.items_cp = []; st.rerun()
        else: st.error("Niektoré položky sa nepodarilo zapísať.")
