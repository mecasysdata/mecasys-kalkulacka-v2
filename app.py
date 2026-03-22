import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
from datetime import date

# --- 1. KONFIGURÁCIA A INICIALIZÁCIA ---
st.set_page_config(page_title="MECASYS Kalkulátor", layout="wide")

# Definícia všetkých premenných (Ochrana proti NameError)
ponuka, item, zakaznik, krajina, lojalita = "", "", "", "", 0.0
material, akost, hustota = "OCEĽ", "", 0.0
d, l, pocet_kusov, narocnost = 0.0, 0.0, 1, "3"
plocha_prierezu, plocha_plasta, hmotnost = 0.0, 0.0, 0.0
cena_material, cena_kooperacia, vybrany_druh_koop = 0.0, 0.0, "Žiadna"
vstupne_naklady, predikovany_cas_min = 0.0, 0.0
datum = date.today()

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
        if not df.empty:
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str).str.strip()
        return df
    except: return pd.DataFrame()

@st.cache_resource
def load_ai_assets():
    paths = ['', 'MECASYS_APP/']
    for p in paths:
        m_path, c_path = f"{p}finalny_model.json", f"{p}stlpce_modelu.pkl"
        if os.path.exists(m_path) and os.path.exists(c_path):
            try:
                bst = xgb.Booster()
                bst.load_model(m_path)
                with open(c_path, 'rb') as f:
                    cols = pickle.load(f)
                return bst, cols
            except: continue
    return None, None

df_zakaznici = load_data(SHEET_ZAKAZNICI)
df_mat = load_data(SHEET_MATERIALY)
df_cennik = load_data(SHEET_CENNIK)
df_koop_cennik = load_data(SHEET_KOOPERACIE)
model_ai, expected_columns = load_ai_assets()

st.title("⚙️ Komplexný kalkulačný systém (AI M1)")

# --- 2. IDENTIFIKÁCIA ---
st.subheader("1. Identifikácia")
c_id1, c_id2 = st.columns(2)
with c_id1:
    ponuka = st.text_input("Označenie ponuky", placeholder="napr. CP-2026-001")
    item = st.text_input("Názov komponentu")
with c_id2:
    list_z = ["--- Vyber ---"] + (sorted(df_zakaznici['zakaznik'].unique().tolist()) if not df_zakaznici.empty else [])
    vyber_z = st.selectbox("Zákazník", list_z)
    if vyber_z != "--- Vyber ---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik, lojalita = vyber_z, float(dz['lojalita'])

# --- 3. MATERIÁL A ROZMERY (OPRAVENÁ HUSTOTA) ---
st.divider()
st.subheader("2. Materiál a Rozmery")
c_m1, c_m2 = st.columns(2)

with c_m1:
    list_mat = sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else ["OCEĽ"]
    material = st.selectbox("Materiál", list_mat)
    df_f = df_mat[df_mat['material'] == material]
    list_ako = sorted(df_f['akost'].unique().tolist())
    akost = st.selectbox("Akosť", list_ako)

with c_m2:
    # --- LOGIKA HUSTOTY PODĽA ZADANIA ---
    if material == "NEREZ":
        hustota = 8000.0
    elif material == "OCEĽ":
        hustota = 7900.0
    elif material == "FAREBNÉ KOVY":
        ako_s = str(akost)
        if ako_s.startswith("3.7"): hustota = 4500.0
        elif ako_s.startswith("3."): hustota = 2900.0
        else: hustota = 9000.0
    elif material == "PLAST":
        try:
            # Ťaháme priamo z tabuľky MATERIALY zo stĺpca 'hustota'
            hustota = float(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
        except:
            hustota = 0.0
    
    st.metric("Hustota (kg/m³)", f"{hustota}")
    if hustota == 0:
        st.error("❌ Hustota nebola nájdená!")

c_p1, c_p2 = st.columns(2)
with c_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.0)
    l = st.number_input("Dĺžka l [mm]", min_value=0.0)
with c_p2:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")

# Geometria
plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

# --- 4. EKONOMIKA ---
st.divider()
st.subheader("3. Ekonomika")
res_mat = df_cennik[(df_cennik['material'] == material) & (df_cennik['akost'] == akost) & (df_cennik['d'] >= d)]
if not res_mat.empty:
    row_m = res_mat.sort_values('d').iloc[0]
    cena_material = (float(row_m['cena']) * l) / 1000
    st.success(f"✅ Materiál z polotovaru d={row_m['d']}")
else:
    cena_material = st.number_input("Manuálna cena materiálu [€/ks]", min_value=0.0)

df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
list_k = ["Žiadna"] + (sorted(df_k_f['druh'].unique().tolist()) if not df_k_f.empty else [])
vybrany_druh_koop = st.selectbox("Kooperácia", list_k)

if vybrany_druh_koop != "Žiadna":
    rk = df_k_f[df_k_f['druh'] == vybrany_druh_koop].iloc[0]
    t, m_z = float(rk['tarifa']), float(rk['minimalna_zakazka'])
    odhad = (t * hmotnost) if str(rk['jednotka']).lower() == 'kg' else (t * plocha_plasta / 10000)
    cena_kooperacia = max(odhad, m_z / pocet_kusov)

vstupne_naklady = cena_material + cena_kooperacia

# --- 5. AI PREDIKCIA ---
if model_ai and expected_columns:
    st.divider()
    row_dict = {
        'd': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov),
        'plocha_prierezu': plocha_prierezu, 'plocha_plasta': plocha_plasta,
        'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady
    }
    for col in expected_columns:
        if col not in row_dict: row_dict[col] = 0
    
    for c, v in [("material", material), ("akost", akost), ("narocnost", narocnost)]:
        k = f"{c}_{str(v).upper()}"
        if k in expected_columns: row_dict[k] = 1
    
    input_df = pd.DataFrame([row_dict])[expected_columns]
    log_pred = model_ai.predict(xgb.DMatrix(input_df))[0]
    predikovany_cas_min = float(np.expm1(log_pred))

    c1, c2 = st.columns(2)
    c1.metric("AI Predikovaný čas / 1ks", f"{predikovany_cas_min:.2f} min")
    c2.metric("Celkový čas výroby", f"{(predikovany_cas_min * pocet_kusov)/60:.2f} hod")

# --- 6. SUMÁR ---
st.divider()
st.subheader("4. Prehľad premenných")
prehlad = pd.DataFrame({
    "Premenná": ["Zákazník", "Hustota [kg/m³]", "Hmotnosť [kg]", "Materiál [€/ks]", "Kooperácia [€/ks]", "AI Čas [min/ks]"],
    "Hodnota": [zakaznik, hustota, round(hmotnost, 4), round(cena_material, 2), round(cena_kooperacia, 2), round(predikovany_cas_min, 2)]
})
st.table(prehlad)
