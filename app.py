import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
from datetime import date

# --- 1. KONFIGURÁCIA A NAČÍTANIE DÁT ---
st.set_page_config(page_title="MECASYS AI Dual-Kalkulátor V6.1", layout="wide")

URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
SHEET_ZAKAZNICI = f"{URL_BASE}gid=324957857&single=true&output=csv"
SHEET_MATERIALY = f"{URL_BASE}gid=1281008948&single=true&output=csv"
SHEET_CENNIK    = f"{URL_BASE}gid=901617097&single=true&output=csv"
SHEET_KOOPERACIE= f"{URL_BASE}gid=1180392224&single=true&output=csv"

def clean_number(val):
    if pd.isna(val): return 0.0
    try:
        s = str(val).replace(',', '').strip()
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
        # MODEL 1 (ČAS)
        if os.path.exists(f"{p}finalny_model.json"):
            m1 = xgb.Booster(); m1.load_model(f"{p}finalny_model.json")
            with open(f"{p}stlpce_modelu.pkl", 'rb') as f: assets["cols1"] = pickle.load(f)
            assets["m1"] = m1
        
        # MODEL 2 (CENA)
        if os.path.exists(f"{p}xgb_model_cena.json"):
            m2 = xgb.Booster(); m2.load_model(f"{p}xgb_model_cena.json")
            with open(f"{p}model_columns.pkl", 'rb') as f: assets["cols2"] = pickle.load(f)
            assets["m2"] = m2
    except Exception as e:
        st.error(f"⚠️ Chyba pri načítaní AI: {e}")
    return assets

df_zakaznici = load_data(SHEET_ZAKAZNICI)
df_mat = load_data(SHEET_MATERIALY)
df_cennik = load_data(SHEET_CENNIK)
df_koop_cennik = load_data(SHEET_KOOPERACIE)
ai = load_ai_models()

st.title("⚙️ MECASYS AI Dual-Kalkulačný Systém")

# --- 2. VSTUPY ---
st.subheader("1. Zákazník a Identifikácia")
c1, c2 = st.columns(2)
with c1:
    datum = st.date_input("Dátum", value=date.today())
    ponuka = st.text_input("Označenie ponuky", "CP-2026-001")
    item = st.text_input("Názov položky (Item)")
with c2:
    list_z = ["--- Vyber ---", "Nový zákazník"]
    if not df_zakaznici.empty: list_z += sorted(df_zakaznici['zakaznik'].dropna().unique().tolist())
    vyber_z = st.selectbox("Zákazník", list_z)
    zakaznik, krajina, lojalita = "", "", 0.0
    if vyber_z == "Nový zákazník":
        zakaznik = st.text_input("Meno")
        krajina = st.text_input("Krajina (napr. SK)").upper()
        lojalita = 0.5
    elif vyber_z != "--- Vyber ---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik, krajina, lojalita = vyber_z, str(dz['krajina']).upper(), float(dz['lojalita'])

st.divider()
st.subheader("2. Technické Parametre")
t1, t2, t3 = st.columns(3)
with t1:
    material = st.selectbox("Materiál", sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else [])
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique().tolist()) if not df_f.empty else ["N/A"])
    narocnost = st.select_slider("Náročnosť", options=["1", "2", "3", "4", "5"], value="3")
with t2:
    d = st.number_input("Priemer d [mm]", min_value=0.1, value=20.0)
    l = st.number_input("Dĺžka l [mm]", min_value=0.1, value=50.0)
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
with t3:
    hustota = 0.0
    if material == "NEREZ": hustota = 8000.0
    elif material == "OCEĽ": hustota = 7900.0
    elif not df_f.empty:
        hustota = clean_number(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
    st.metric("Hustota", f"{hustota} kg/m³")

# Medzivýpočty
plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

# --- 3. EKONOMIKA ---
st.divider()
st.subheader("3. Náklady")
cena_mat_jednotkova = 0.0
if not df_cennik.empty:
    m_c = df_cennik[(df_cennik['material'].str.strip() == material) & (df_cennik['akost'].str.strip() == akost)]
    if not m_c.empty:
        m_c = m_c.copy(); m_c['d_num'] = m_c['d'].apply(clean_number)
        vhodne = m_c[m_c['d_num'] >= d].sort_values('d_num')
        if not vhodne.empty: 
            cena_mat_jednotkova = (clean_number(vhodne.iloc[0]['cena']) * l) / 1000

ma_koop = st.radio("Kooperácia?", ["Nie", "Áno"], horizontal=True)
cena_koop, druh_koop = 0.0, "Žiadna"
if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
    if not df_k_f.empty:
        druh_koop = st.selectbox("Vyber kooperáciu", sorted(df_k_f['druh'].unique()))
        rk = df_k_f[df_k_f['druh'] == druh_koop].iloc[0]
        def gv(r, k): 
            for c in r.index: 
                if all(x in c.lower() for x in k): return clean_number(r[c])
            return 0.0
        tarifa, min_z = gv(rk, ['tarifa']), gv(rk, ['min', 'zak'])
        jednotka = str(rk[[c for c in rk.index if 'jednotka' in c.lower()][0]]).lower()
        odhad = (tarifa * hmotnost) if 'kg' in jednotka else (tarifa * plocha_plasta / 10000)
        cena_koop = max(odhad, min_z / pocet_kusov)

vstupne_naklady = cena_mat_jednotkova + cena_koop

# --- 4. AI PREDIKCIA ---
pred_cas, pred_cena = 0.0, 0.0

# MODEL 1 (Čas)
if ai["m1"] and ai["cols1"]:
    r1 = {'d':d, 'l':l, 'pocet_kusov':np.log1p(pocet_kusov), 'plocha_prierezu':plocha_prierezu,
          'plocha_plasta':plocha_plasta, 'lojalita':lojalita, 'hustota':hustota, 'vstupne_naklady':vstupne_naklady}
    for c in ai["cols1"]:
        if c not in r1: r1[c] = 0
        if c == f"material_{material.upper()}": r1[c] = 1
        if c == f"akost_{akost.upper()}": r1[c] = 1
        if c == f"narocnost_{narocnost}": r1[c] = 1
    dm1 = xgb.DMatrix(pd.DataFrame([r1])[ai["cols1"]])
    pred_cas = float(np.expm1(ai["m1"].predict(dm1)[0]))

# MODEL 2 (Cena)
if ai["m2"] and ai["cols2"] and pred_cas > 0:
    r2 = {'cas': pred_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 
          'hustota': hustota, 'plocha_prierezu': plocha_prierezu}
    for c in ai["cols2"]:
        if c not in r2: r2[c] = 0
        if c == f"krajina_{krajina}": r2[c] = 1
    dm2 = xgb.DMatrix(pd.DataFrame([r2])[ai["cols2"]])
    pred_cena = float(np.expm1(ai["m2"].predict(dm2)[0]))

# --- 5. FINÁLNY PREHĽAD (VŠETKY PREMENNÉ) ---
st.divider()
st.subheader("📋 Kompletný Výpis Systému")
col_v1, col_v2 = st.columns(2)
with col_v1:
    st.metric("AI Odhadovaný Čas", f"{round(pred_cas, 2)} min/ks")
with col_v2:
    st.metric("AI Odhadovaná Cena", f"{round(pred_cena, 2)} €/ks")

all_vars = {
    "Kategória": [
        "Identifikácia", "Zákazník", "Zákazník", "Zákazník",
        "Technické", "Technické", "Technické", "Technické", "Technické",
        "Geometria", "Geometria", "Geometria", "Geometria",
        "Ekonomika", "Ekonomika", "Ekonomika", "Ekonomika",
        "AI Predikcia", "AI Predikcia"
    ],
    "Premenná": [
        "Ponuka / Item", "Meno zákazníka", "Krajina", "Lojalita (vstup do AI)",
        "Materiál", "Akosť", "Hustota [kg/m³]", "Počet kusov", "Náročnosť",
        "Priemer d [mm]", "Dĺžka l [mm]", "Plocha prierezu [mm²]", "Hmotnosť [kg]",
        "Cena materiálu [€/ks]", "Druh kooperácie", "Cena kooperácie [€/ks]", "Vstupné náklady [€/ks]",
        "AI Čas M1 [min/ks]", "AI Cena M2 [€/ks]"
    ],
    "Hodnota": [
        f"{ponuka} / {item}", zakaznik, krajina, lojalita,
        material, akost, hustota, pocet_kusov, narocnost,
        d, l, round(plocha_prierezu, 2), round(hmotnost, 4),
        round(cena_mat_jednotkova, 4), druh_koop, round(cena_koop, 4), round(vstupne_naklady, 4),
        f"{round(pred_cas, 2)} min", f"{round(pred_cena, 2)} €"
    ]
}
st.table(pd.DataFrame(all_vars))
