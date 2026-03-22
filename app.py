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
from fpdf import FPDF

# --- 1. KONFIGURÁCIA A ZDROJE ---
st.set_page_config(page_title="Mecasys AI PRO", layout="wide")

# Link na tvoj Apps Script (Archív A-U)
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbxv1GNG0Yx7t0TiY4qj2rhK4RN3cEC4fwd1J5A8M33xKL3qgHf_WGPDzCbvrie9vXQu/exec"

URLS = {
    "cisnik": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv",
    "mat_cena": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv",
    "koop": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv",
    "zakaznici": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"
}

# Inicializácia košíka v session state
if 'items_cp' not in st.session_state:
    st.session_state.items_cp = []

@st.cache_data(ttl=600)
def load_csv(url):
    try:
        r = requests.get(url, timeout=10)
        r.encoding = 'utf-8'
        df = pd.read_csv(StringIO(r.text))
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip().str.upper()
        return df
    except: return pd.DataFrame()

@st.cache_resource
def load_models():
    p = 'MECASYS_APP'
    # MODEL 1 - ČAS
    m1 = XGBRegressor(); m1.load_model(os.path.join(p, 'finalny_model.json'))
    with open(os.path.join(p, 'stlpce_modelu.pkl'), 'rb') as f: c1 = pickle.load(f)
    # MODEL 2 - CENA
    m2 = XGBRegressor(); m2.load_model(os.path.join(p, 'xgb_model_cena.json'))
    with open(os.path.join(p, 'model_columns.pkl'), 'rb') as f: c2 = pickle.load(f)
    return m1, c1, m2, c2

df_c, df_m, df_k, df_z = load_csv(URLS["cisnik"]), load_csv(URLS["mat_cena"]), load_csv(URLS["koop"]), load_csv(URLS["zakaznici"])
model1, cols1, model2, cols2 = load_models()

# --- 2. LOGICKÉ FUNKCIE (PDF, HUSTOTA) ---
class PDF(FPDF):
    def header(self):
        if os.path.exists("logo_mecasys.png"):
            self.image("logo_mecasys.png", 10, 8, 33)
        self.set_font('helvetica', 'B', 15)
        self.cell(80)
        self.cell(100, 10, 'CENOVÁ PONUKA / QUOTATION', 0, 0, 'R')
        self.ln(20)

def get_hustota(mat, ako, df_cis):
    if mat == 'NEREZ': return 8000.0
    if mat == 'OCEĽ': return 7900.0
    if mat == 'FAREBNÉ KOVY':
        if ako.startswith('3.7'): return 4500.0
        if ako.startswith('3.'): return 2900.0
        if ako.startswith('2.'): return 9000.0
    if mat == 'PLAST':
        row = df_cis[df_cis['AKOST'] == ako]
        if not row.empty:
            try: return float(str(row.iloc[0].get('HUSTOTA', '')).replace(',', '.'))
            except: return 1200.0
    return 7850.0

# --- 3. ROZHRANIE (UI) ---
st.title("🏭 MECASYS AI PRO - Kalkulačný systém")

with st.container(border=True):
    st.subheader("📋 Hlavička ponuky")
    h1, h2, h3 = st.columns(3)
    v_oznacenie_cp = h1.text_input("Číslo CP", value="CP-2026-")
    v_datum_cp = h2.date_input("Dátum CP", date.today())
    v_zakaznik = h3.selectbox("Zákazník", sorted(df_z['ZAKAZNIK'].unique()) if not df_z.empty else ["-"])

st.divider()

with st.container(border=True):
    st.subheader("⚙️ Technické parametre ITEMu")
    c1, c2, c3 = st.columns(3)
    with c1:
        v_item = st.text_input("ITEM (Názov/Výkres)")
        v_ks = st.number_input("Počet kusov", 1, value=10)
        v_nar = st.selectbox("Náročnosť (1-5)", ['1','2','3','4','5'], index=2)
    with c2:
        v_mat = st.selectbox("Materiál", sorted(df_c['MATERIAL'].unique()))
        v_ako = st.selectbox("Akosť", sorted(df_c[df_c['MATERIAL'] == v_mat]['AKOST'].unique()))
        v_d = st.number_input("Priemer d [mm]", 1.0, value=20.0)
        v_l = st.number_input("Dĺžka l [mm]", 1.0, value=100.0)
    with c3:
        v_ma_koop = st.checkbox("Externá kooperácia?")
        v_n_koop_manual = st.number_input("Náklad na kooperáciu [€/ks]", 0.0) if v_ma_koop else 0.0

# --- 4. VÝPOČETNÝ ENGINE ---
if st.button("➕ PRIDAŤ POLOŽKU DO KOŠÍKA", use_container_width=True):
    try:
        # Zákazník info
        z_row = df_z[df_z['ZAKAZNIK'] == v_zakaznik]
        v_krajina = str(z_row['KRAJINA'].iloc[0]) if not z_row.empty else "SK"
        v_lojalita = float(z_row['LOJALITA'].iloc[0]) if not z_row.empty else 5.0

        # Fyzika (Ošetrenie typov)
        h_val = float(get_hustota(v_mat, v_ako, df_c))
        hmot_kg = float(h_val * (math.pi/4) * (v_d/1000)**2 * (v_l/1000))
        pl_prierez = float((math.pi * v_d**2) / 4)
        pl_plast = float(math.pi * v_d * v_l)

        # Náklad materiál
        df_mat_f = df_m[df_m['AKOST'] == v_ako].copy()
        df_mat_f['D'] = pd.to_numeric(df_mat_f['D'], errors='coerce')
        res_m = df_mat_f[df_mat_f['D'] >= v_d].sort_values('D')
        j_cena_m = float(str(res_m.iloc[0]['J.CENA/M']).replace(',','.')) if not res_m.empty else 0.0
        n_mat = float((v_l/1000) * j_cena_m)

        # MODEL 1 (Čas) - Pevné stĺpce a typy
        in1 = pd.DataFrame(0.0, index=[0], columns=cols1)
        in1.update({'d':v_d, 'l':v_l, 'plocha_prierezu':pl_prierez, 'plocha_plasta':pl_plast, 'pocet_kusov':np.log1p(float(v_ks))})
        for c in [f"MATERIAL_{v_mat}", f"AKOST_{v_ako}", f"NAROCNOST_{v_nar}"]:
            if c in in1.columns: in1[c] = 1.0
        cas_min = float(np.expm1(model1.predict(in1.astype('float64'))[0]))

        # MODEL 2 (Cena) - Pevné stĺpce a typy
        vst_naklady = float(n_mat + v_n_koop_manual)
        in2 = pd.DataFrame(0.0, index=[0], columns=cols2)
        in2.update({
            'cas': cas_min, 
            'hmotnost': hmot_kg, 
            'vstupne_naklady': vst_naklady, 
            'lojalita': v_lojalita, 
            'pocet_kusov': np.log1p(float(v_ks)), 
            'plocha_prierezu': pl_prierez
        })
        if f"krajina_{v_krajina}" in in2.columns: in2[f"krajina_{v_krajina}"] = 1.0
        cena_ks = float(np.expm1(model2.predict(in2.astype('float64'))[0]))

        # Uloženie položky (Mapovanie A-U pre Archív)
        st.session_state.items_cp.append({
            "datum": str(v_datum_cp), "cislo_cp": v_oznacenie_cp, "zakaznik": v_zakaznik, "krajina": v_krajina,
            "lojalita": v_lojalita, "item": v_item, "material": v_mat, "akost": v_ako, "d": v_d, "l": v_l,
            "hustota": h_val, "hmotnost": round(hmot_kg, 4), "narocnost": v_nar, "j_cena_mat": round(j_cena_m, 2),
            "naklad_mat": round(n_mat, 2), "naklad_koop": round(v_n_koop_manual, 2), "vstupne_naklady": round(vst_naklady, 2),
            "cas": round(cas_min, 2), "jednotkova_cena": round(cena_ks, 2), "ks": v_ks, "cena_spolu": round(cena_ks * v_ks, 2)
        })
        st.success(f"Položka '{v_item}' pridaná.")
        st.rerun()
    except Exception as e: st.error(f"Chyba: {e}")

# --- 5. PREHĽAD KOŠÍKA A EXPORTY ---
if st.session_state.items_cp:
    st.divider()
    st.subheader(f"🛒 Košík ponuky: {v_oznacenie_cp}")
    df_basket = pd.DataFrame(st.session_state.items_cp)
    st.table(df_basket[["item", "akost", "d", "l", "ks", "jednotkova_cena", "cena_spolu"]])
    
    celkom = df_basket["cena_spolu"].sum()
    st.metric("CELKOVÁ SUMA PONUKY (bez DPH)", f"{celkom:.2f} €")
    
    col1, col2, col3 = st.columns(3)
    
    with col1: # PDF GENERÁTOR
        if st.button("📄 GENEROVAŤ PDF"):
            pdf = PDF()
            pdf.add_page()
            pdf.set_font("helvetica", size=10)
            pdf.cell(100, 7, f"Zákazník: {v_zakaznik}", 0, 1)
            pdf.cell(100, 7, f"Číslo CP: {v_oznacenie_cp}", 0, 1)
            pdf.cell(100, 7, f"Dátum: {v_datum_cp}", 0, 1); pdf.ln(10)
            
            # Tabuľka
            pdf.set_fill_color(230, 230, 230); pdf.set_font("helvetica", 'B', 10)
            pdf.cell(70, 10, "ITEM", 1, 0, 'C', True); pdf.cell(30, 10, "Qty", 1, 0, 'C', True)
            pdf.cell(40, 10, "Price/Item", 1, 0, 'C', True); pdf.cell(50, 10, "Total", 1, 1, 'C', True)
            
            pdf.set_font("helvetica", size=10)
            for i in st.session_state.items_cp:
                pdf.cell(70, 10, str(i['item']), 1)
                pdf.cell(30, 10, str(i['ks']), 1, 0, 'C')
                pdf.cell(40, 10, f"{i['jednotkova_cena']:.2f} EUR", 1, 0, 'R')
                pdf.cell(50, 10, f"{i['cena_spolu']:.2f} EUR", 1, 1, 'R')
            
            pdf.set_font("helvetica", 'B', 11); pdf.cell(140, 10, "TOTAL (w/o VAT):", 0, 0, 'R')
            pdf.cell(50, 10, f"{celkom:.2f} EUR", 0, 1, 'R')
            
            st.download_button("⬇️ Stiahnuť PDF", data=pdf.output(dest='S').encode('latin-1'), file_name=f"CP_{v_oznacenie_cp}.pdf", mime="application/pdf")

    with col2: # ARCHÍV
        if st.button("💾 ULOŽIŤ DO ARCHÍVU"):
            try:
                r = requests.post(URL_APPS_SCRIPT, json=st.session_state.items_cp)
                if "Success" in r.text:
                    st.success("Archivované!"); st.session_state.items_cp = []; st.rerun()
                else: st.error(f"Chyba archívu: {r.text}")
            except Exception as e: st.error(f"Spojenie zlyhalo: {e}")

    with col3:
        if st.button("🗑️ VYMAZAŤ KOŠÍK"):
            st.session_state.items_cp = []; st.rerun()
