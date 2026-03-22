import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
from datetime import date

# --- 1. KONFIGURÁCIA A NAČÍTANIE DÁT ---
st.set_page_config(page_title="Kalkulačný systém V3", layout="wide")

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

# Načítanie AI prostriedkov
@st.cache_resource
def load_ai_assets():
    try:
        bst = xgb.Booster()
        bst.load_model('finalny_model.json')
        with open('stlpce_modelu.pkl', 'rb') as f:
            cols = pickle.load(f)
        return bst, cols
    except:
        return None, None

df_zakaznici = load_data(SHEET_ZAKAZNICI)
df_mat = load_data(SHEET_MATERIALY)
df_cennik = load_data(SHEET_CENNIK)
df_koop_cennik = load_data(SHEET_KOOPERACIE)
model_ai, expected_columns = load_ai_assets()

st.title("⚙️ Komplexný kalkulačný systém s AI")

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

    zakaznik, krajina, lojalita = "", "", 0.0
    if vyber_z == "Nový zákazník (manual)":
        zakaznik = st.text_input("Meno nového zákazníka")
        krajina = st.text_input("Krajina")
        lojalita = 0.5
        st.warning(f"⚠️ Doplniť údaje! Automatická lojalita: {lojalita}")
    elif vyber_z != "--- Vyber ---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik, krajina, lojalita = vyber_z, str(dz['krajina']), float(dz['lojalita'])
        st.info(f"✅ Zákazník: {krajina} | Lojalita: {lojalita}")

# --- 3. MATERIÁL A HUSTOTA ---
st.divider()
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
            try:
                hustota = float(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
            except: hustota = 0.0
        elif material == "FAREBNÉ KOVY":
            ako_s = str(akost)
            if ako_s.startswith("3.7"): hustota = 4500.0
            elif ako_s.startswith("3."): hustota = 2900.0
            else: hustota = 9000.0
        st.metric("Hustota (kg/m³)", f"{hustota}")
    if hustota == 0: st.error("❌ Chýba hustota!")

# --- 4. ROZMERY A GEOMETRIA ---
st.divider()
st.subheader("3. Technické parametre")
col_p1, col_p2 = st.columns(2)
with col_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.0, format="%.2f")
    l = st.number_input("Dĺžka l [mm]", min_value=0.0, format="%.2f")
with col_p2:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

# --- 5. EKONOMIKA ---
st.divider()
st.subheader("4. Ekonomika")
cena_material = 0.0
res_mat = df_cennik[(df_cennik['material'] == material) & (df_cennik['akost'] == akost) & (df_cennik['d'] >= d)]
if not res_mat.empty:
    row_m = res_mat.sort_values('d').iloc[0]
    cena_material = (float(row_m['cena']) * l) / 1000
    st.success(f"✅ Polotovar d={row_m['d']} mm nájdený.")
else:
    cena_material = st.number_input("Zadaj cenu materiálu manuálne [€/ks]", min_value=0.0)

ma_koop = st.radio("Kooperácia?", ["Nie", "Áno"], horizontal=True)
cena_kooperacia, vybrany_druh_koop = 0.0, "Žiadna"
if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
    list_k = sorted(df_k_f['druh'].unique().tolist()) if not df_k_f.empty else []
    if list_k:
        vybrany_druh_koop = st.selectbox("Druh kooperácie", list_k)
        rk = df_k_f[df_k_f['druh'] == vybrany_druh_koop].iloc[0]
        odhad = (float(rk['tarifa']) * hmotnost) if str(rk['jednotka']).lower() == 'kg' else (float(rk['tarifa']) * plocha_plasta / 10000)
        cena_kooperacia = max(odhad, float(rk['minimalna_zakazka']) / pocet_kusov)
    else:
        cena_kooperacia = st.number_input("Manuálna cena kooperácie [€/ks]", min_value=0.0)
        vybrany_druh_koop = "Manuálne"

vstupne_naklady = cena_material + cena_kooperacia

# --- 6. AI PREDIKCIA ---
predikovany_cas_min = 0.0
if model_ai and expected_columns:
    st.divider()
    st.subheader("5. AI Predikcia výrobného času")
    
    # Príprava riadku pre model
    row_dict = {
        'd': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov),
        'plocha_prierezu': plocha_prierezu, 'plocha_plasta': plocha_plasta,
        'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady
    }
    
    # One-hot encoding naživo
    for col in expected_columns:
        if col not in row_dict: row_dict[col] = 0
    
    cat_mat = f"material_{str(material).strip().upper()}"
    cat_ako = f"akost_{str(akost).strip().upper()}"
    cat_nar = f"narocnost_{str(narocnost).strip().upper()}"
    
    if cat_mat in expected_columns: row_dict[cat_mat] = 1
    if cat_ako in expected_columns: row_dict[cat_ako] = 1
    if cat_nar in expected_columns: row_dict[cat_nar] = 1
    
    input_df = pd.DataFrame([row_dict])[expected_columns]
    log_pred = model_ai.predict(xgb.DMatrix(input_df))[0]
    predikovany_cas_min = float(np.expm1(log_pred)) # ODLOGARITMOVANIE

    c1, c2 = st.columns(2)
    c1.metric("Predikovaný čas na 1ks", f"{predikovany_cas_min:.2f} min")
    c2.metric("Celkový čas dávky", f"{(predikovany_cas_min * pocet_kusov)/60:.2f} hod")

# --- 7. TABUĽKA PREHĽADU PREMENNÝCH ---
st.divider()
st.subheader("6. Kompletný prehľad všetkých premenných")

data_final = {
    "Premenná": [
        "Označenie ponuky", "Item", "Dátum", "Zákazník", "Krajina", "Lojalita",
        "Materiál", "Akosť", "Hustota [kg/m³]", "Priemer d [mm]", "Dĺžka l [mm]",
        "Počet kusov", "Náročnosť", "Plocha prierezu [mm²]", "Plocha plášťa [mm²]",
        "Hmotnosť [kg]", "Cena materiálu [€/ks]", "Druh kooperácie", 
        "Cena kooperácie [€/ks]", "Vstupne naklady [€/ks]", "AI predikovaný čas [min/ks]"
    ],
    "Hodnota": [
        ponuka, item, datum, zakaznik, krajina, lojalita,
        material, akost, hustota, d, l,
        pocet_kusov, narocnost, round(plocha_prierezu, 2), round(plocha_plasta, 2),
        round(hmotnost, 4), round(cena_material, 4), vybrany_druh_koop,
        round(cena_kooperacia, 4), round(vstupne_naklady, 4), round(predikovany_cas_min, 2)
    ]
}
st.table(pd.DataFrame(data_final))
