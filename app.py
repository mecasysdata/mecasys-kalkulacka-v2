import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
from datetime import date

# --- 1. KONFIGURÁCIA A NAČÍTANIE DÁT ---
st.set_page_config(page_title="MECASYS AI Kalkulátor V5.1", layout="wide")

URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
SHEET_ZAKAZNICI = f"{URL_BASE}gid=324957857&single=true&output=csv"
SHEET_MATERIALY = f"{URL_BASE}gid=1281008948&single=true&output=csv"
SHEET_CENNIK    = f"{URL_BASE}gid=901617097&single=true&output=csv"
SHEET_KOOPERACIE= f"{URL_BASE}gid=1180392224&single=true&output=csv"

def clean_number(val):
    if pd.isna(val): return 0.0
    try:
        # Odstráni tisíckové čiarky a spracuje formát (napr. 1,200.00 -> 1200.0)
        s = str(val).replace(',', '').strip()
        return float(s)
    except:
        return 0.0

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

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

st.title("⚙️ Komplexný AI kalkulačný systém")

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
    elif vyber_z != "--- Vyber ---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik = vyber_z
        krajina = str(dz['krajina'])
        lojalita = float(dz['lojalita'])
        st.info(f"✅ Zákazník: {krajina} | Lojalita: {lojalita}")

st.divider()

# --- 3. MATERIÁL A HUSTOTA ---
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
        hustota = st.number_input("Zadaj hustotu [kg/m³]", min_value=0.0)
    else:
        akost = vyber_ako
        if material == "NEREZ": hustota = 8000.0
        elif material == "OCEĽ": hustota = 7900.0
        elif material == "PLAST":
            raw_h = df_f[df_f['akost'] == akost]['hustota'].iloc[0]
            hustota = clean_number(raw_h)
        elif material == "FAREBNÉ KOVY":
            ako_s = str(akost)
            hustota = 4500.0 if ako_s.startswith("3.7") else (2900.0 if ako_s.startswith("3.") else 9000.0)
        
        st.metric("Hustota (kg/m³)", f"{hustota}")

st.divider()

# --- 4. ROZMERY A GEOMETRIA ---
st.subheader("3. Technické parametre")
col_p1, col_p2 = st.columns(2)

with col_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.1, value=20.0, format="%.2f")
    l = st.number_input("Dĺžka l [mm]", min_value=0.1, value=50.0, format="%.2f")

with col_p2:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

# Výpočty geometrie
plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

st.divider()

# --- 5. EKONOMIKA ---
st.subheader("4. Ekonomika")

# 5.1 CENA MATERIÁLU (OPRAVENÁ LOGIKA)
cena_material = 0.0
if not df_cennik.empty:
    mask = (df_cennik['material'].str.strip() == material) & (df_cennik['akost'].str.strip() == akost)
    res_mat = df_cennik[mask].copy()

    if not res_mat.empty:
        res_mat['d_num'] = res_mat['d'].apply(clean_number)
        res_mat['cena_num'] = res_mat['cena'].apply(clean_number)
        vhodne = res_mat[res_mat['d_num'] >= d].sort_values('d_num')
        
        if not vhodne.empty:
            najblizsi = vhodne.iloc[0]
            cena_material = (najblizsi['cena_num'] * l) / 1000
            st.success(f"✅ Materiál: Polotovar d={najblizsi['d_num']} mm | Cena: {najblizsi['cena_num']} €/m")
        else:
            st.error(f"❌ V cenníku nie je priemer aspoň {d} mm")
            cena_material = st.number_input("Manuálna cena materiálu [€/ks]", min_value=0.0, key="m_man")
    else:
        cena_material = st.number_input("Kombinácia nenájdená. Zadaj manuálne [€/ks]", min_value=0.0, key="m_miss")

# 5.2 CENA KOOPERÁCIE
ma_koop = st.radio("Kooperácia?", ["Nie", "Áno"], horizontal=True)
cena_kooperacia, vybrany_druh_koop = 0.0, "Žiadna"

if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
    list_k = sorted(df_k_f['druh'].unique().tolist()) if not df_k_f.empty else []
    
    if list_k:
        vybrany_druh_koop = st.selectbox("Druh kooperácie", list_k)
        rk = df_k_f[df_k_f['druh'] == vybrany_druh_koop].iloc[0]
        
        # Robustné hľadanie stĺpcov
        def get_val(row, keys):
            for col in row.index:
                if all(k in col.lower() for k in keys): return clean_number(row[col])
            return 0.0

        tarifa = get_val(rk, ['tarifa'])
        min_zak = get_val(rk, ['min', 'zak'])
        jednotka = str(rk[[c for c in rk.index if 'jednotka' in c.lower()][0]]).lower()
        
        odhad = (tarifa * hmotnost) if 'kg' in jednotka else (tarifa * plocha_plasta / 10000)
        cena_kooperacia = max(odhad, min_zak / pocet_kusov)
    else:
        cena_kooperacia = st.number_input("Cena kooperácie manuálne [€/ks]", min_value=0.0)

vstupne_naklady = cena_material + cena_kooperacia

# --- 6. AI PREDIKCIA (MODEL 1) ---
predikovany_cas_min = 0.0
if model_ai and expected_columns and d > 0 and l > 0:
    st.divider()
    st.subheader("🤖 AI Výpočet strojného času (M1)")
    
    input_row = {
        'd': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov),
        'plocha_prierezu': plocha_prierezu, 'plocha_plasta': plocha_plasta,
        'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady
    }
    for col in expected_columns:
        if col not in input_row: input_row[col] = 0
    for c, v in [("material", material), ("akost", akost), ("narocnost", narocnost)]:
        key = f"{c}_{str(v).upper()}"
        if key in expected_columns: input_row[key] = 1
    
    dmatrix = xgb.DMatrix(pd.DataFrame([input_row])[expected_columns])
    predikovany_cas_min = float(np.expm1(model_ai.predict(dmatrix)[0]))
    st.metric("Predikovaný čas M1", f"{predikovany_cas_min:.2f} min/ks")

# --- 7. FINÁLNY PREHĽAD ---
st.divider()
st.subheader("📋 Kompletný prehľad")
final_data = {
    "Vlastnosť": ["Ponuka", "Zákazník", "Lojalita", "Hustota [kg/m³]", "Hmotnosť [kg]", "Cena mat. [€/ks]", "Cena koop. [€/ks]", "Vstupné náklady [€/ks]", "AI Čas M1 [min/ks]"],
    "Hodnota": [ponuka, zakaznik, lojalita, hustota, round(hmotnost, 4), round(cena_material, 4), round(cena_kooperacia, 4), round(vstupne_naklady, 4), round(predikovany_cas_min, 2)]
}
st.table(pd.DataFrame(final_data))
