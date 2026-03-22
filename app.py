import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os

# --- 1. POMOCNÉ FUNKCIE PRE ČISTENIE DÁT ---
def safe_num(val):
    """Prevedie text z Excelu na číslo, odstráni čiarky a medzery."""
    if pd.isna(val) or val == "": return 0.0
    try:
        s = str(val).replace(',', '').replace(' ', '').replace('€', '')
        return float(s)
    except:
        return 0.0

# --- 2. KONFIGURÁCIA A NAČÍTANIE ---
st.set_page_config(page_title="MECASYS AI FINAL", layout="wide")

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
        # Model 1: ČAS
        m1 = xgb.Booster(); m1.load_model(f"{p}finalny_model.json")
        with open(f"{p}stlpce_modelu.pkl", 'rb') as f: assets["cols1"] = pickle.load(f)
        assets["m1"] = m1
        # Model 2: CENA
        m2 = xgb.Booster(); m2.load_model(f"{p}xgb_model_cena.json")
        with open(f"{p}model_columns.pkl", 'rb') as f: assets["cols2"] = pickle.load(f)
        assets["m2"] = m2
    except Exception as e:
        st.error(f"Chyba pri načítaní modelov: {e}")
    return assets

# Google Sheets linky
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
df_zakaznici = load_data(f"{URL_BASE}gid=324957857&single=true&output=csv")
df_mat = load_data(f"{URL_BASE}gid=1281008948&single=true&output=csv")
df_cennik = load_data(f"{URL_BASE}gid=901617097&single=true&output=csv")
df_koop = load_data(f"{URL_BASE}gid=1180392224&single=true&output=csv")

ai = load_ai_models()

# --- 3. POUŽÍVATEĽSKÉ ROZHRANIE ---
st.title("⚙️ MECASYS AI - Produkčná verzia")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Klient a Materiál")
    z_list = sorted(df_zakaznici['zakaznik'].unique()) if not df_zakaznici.empty else ["Neznámy"]
    vyber_z = st.selectbox("Zákazník", z_list)
    
    # Dáta o zákazníkovi
    dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0] if not df_zakaznici.empty else {}
    lojalita = safe_num(dz.get('lojalita', 0.5))
    krajina = str(dz.get('krajina', 'SK'))

    m_list = sorted(df_mat['material'].unique()) if not df_mat.empty else []
    material = st.selectbox("Materiál", m_list)
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique()) if not df_f.empty else [])

with col2:
    st.subheader("Technické parametre")
    d = st.number_input("Priemer d [mm]", value=20.0, step=1.0)
    l = st.number_input("Dĺžka l [mm]", value=50.0, step=1.0)
    pocet_kusov = st.number_input("Počet kusov", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

# --- 4. LOGIKA HUSTOTY (Nerez 8000 / Oceľ 7900 / Plasty zo Sheetu) ---
hustota = 7900.0
if material == "NEREZ":
    hustota = 8000.0
elif material == "OCEĽ":
    hustota = 7900.0
elif material == "PLAST":
    plast_match = df_f[df_f['akost'] == akost]
    if not plast_match.empty:
        hustota = safe_num(plast_match['hustota'].iloc[0])
    else:
        try: hustota = safe_num(df_f['hustota'].dropna().iloc[0])
        except: hustota = 1200.0
    if hustota < 100: hustota = 1200.0 # Poistka pre nuly v Sheete

elif material == "FAREBNÉ KOVY":
    ako_s = str(akost).upper()
    if "3.7" in ako_s: hustota = 4500.0
    elif "3." in ako_s: hustota = 2800.0
    else: hustota = 8500.0

# Výpočty geometrie
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)
plocha_plasta = math.pi * d * l
plocha_prierezu = (math.pi * d**2) / 4

# --- 5. EKONOMIKA (Materiál + Kooperácia) ---
st.divider()
# Cena materiálu z tabuľky
res_m = df_cennik[(df_cennik['material'] == material) & (df_cennik['akost'] == akost) & (df_cennik['d'] >= d)].sort_values('d')
cena_mat_jednotkova = safe_num(res_m.iloc[0]['cena']) if not res_m.empty else 0.0
cena_material = (cena_mat_jednotkova * l) / 1000

# Kooperácia
cena_kooperacia = 0.0
df_k_f = df_koop[df_koop['material'] == material]
if not df_k_f.empty:
    rk = df_k_f.iloc[0]
    tarifa = safe_num(rk.get('tarifa', 0))
    min_zak = safe_num(rk.get('minimalna_zakazka', 0))
    jednotka = str(rk.get('jednotka', 'kg')).lower()
    
    odhad_koop = (tarifa * hmotnost) if 'kg' in jednotka else (tarifa * plocha_plasta / 10000)
    cena_kooperacia = max(odhad_koop, min_zak / pocet_kusov)

vstupne_naklady = cena_material + cena_kooperacia

# --- 6. AI PREDIKCIA (M1 -> M2) ---
if ai["m1"] and ai["m2"]:
    try:
        # Model 1: PREDPOVEĎ ČASU
        v1 = {
            'd': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 
            'plocha_prierezu': plocha_prierezu, 'plocha_plasta': plocha_plasta,
            'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady
        }
        # One-hot encoding pre M1
        for c in ai["cols1"]:
            if c not in v1: v1[c] = 0
            if c == f"material_{str(material).upper()}": v1[c] = 1
            if c == f"akost_{str(akost).upper()}": v1[c] = 1
            if c == f"narocnost_{narocnost}": v1[c] = 1
        
        dmatrix1 = xgb.DMatrix(pd.DataFrame([v1])[ai["cols1"]])
        pred_cas = float(np.expm1(ai["m1"].predict(dmatrix1)[0]))

        # Model 2: PREDPOVEĎ CENY
        v2 = {
            'cas': pred_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 
            'hustota': hustota, 'plocha_prierezu': plocha_prierezu
        }
        # One-hot encoding pre M2
        for c in ai["cols2"]:
            if c not in v2: v2[c] = 0
            if c == f"krajina_{str(krajina).upper()}": v2[c] = 1
        
        dmatrix2 = xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]])
        pred_cena = float(np.expm1(ai["m2"].predict(dmatrix2)[0]))

        # ZOBRAZENIE VÝSLEDKOV
        st.subheader("Výsledky AI Analýzy")
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric("Odhadovaný čas", f"{pred_cas:.2f} min")
        res_col2.metric("Navrhovaná cena", f"{pred_cena:.2f} €/ks")
        res_col3.metric("Vstupné náklady", f"{vstupne_naklady:.3f} €")

    except Exception as e:
        st.warning(f"AI model narazil na nečakanú hodnotu. Skontroluj vstupy. ({e})")
else:
    st.info("Nahrajte modely do priečinka MECASYS_APP pre aktiváciu AI predikcie.")

# Kontrolná sekcia na spodku
with st.expander("Detailné technické údaje"):
    st.write(f"Hustota: {hustota} kg/m³ | Hmotnosť: {hmotnost:.4f} kg")
    st.write(f"Lojalita klienta: {lojalita} | Krajina: {krajina}")
