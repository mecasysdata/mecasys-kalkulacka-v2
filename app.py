import streamlit as st
import pandas as pd
import math
import numpy as np
import pickle
import xgboost as xgb
import os
import requests
from datetime import date

# --- 1. KONFIGURÁCIA A SESSION STATE ---
st.set_page_config(page_title="MECASYS AI Multi-Kalkulátor V8.5", layout="wide")

if 'kosik' not in st.session_state:
    st.session_state.kosik = []

URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbwcpPJfA1R_ZQP4h6Uj-QNObxoTwO_9TxSLR_Ki75E-cZCvQ3XTlNN0wOzVZShWv1iKbQ/exec"

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

st.title("⚙️ MECASYS AI Multi-Kalkulačný Systém")

# --- 2. HLAVIČKA PONUKY ---
with st.expander("📄 Hlavička ponuky (Spoločné údaje)", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        datum_v = st.date_input("Dátum CP", value=date.today())
        ponuka_v = st.text_input("Číslo CP", "CP-2026-001")
    with c2:
        list_z = ["--- Vyber ---", "Nový zákazník"]
        if not df_zakaznici.empty: list_z += sorted(df_zakaznici['zakaznik'].dropna().unique().tolist())
        vyber_z = st.selectbox("Zákazník", list_z)
        zakaznik_v, krajina_v, lojalita_v = "", "", 0.0
        if vyber_z == "Nový zákazník":
            zakaznik_v = st.text_input("Meno")
            krajina_v = st.text_input("Krajina (napr. SK)").upper()
            lojalita_v = 0.5
        elif vyber_z != "--- Vyber ---":
            dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
            zakaznik_v, krajina_v, lojalita_v = vyber_z, str(dz['krajina']).upper(), float(dz['lojalita'])

st.divider()

# --- 3. TECHNICKÉ PARAMETRE ---
st.subheader("🛠️ Definícia položky (Item)")
t1, t2, t3 = st.columns(3)
with t1:
    item_v = st.text_input("Názov položky / ITEM")
    material_v = st.selectbox("Materiál", sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else [])
    df_f = df_mat[df_mat['material'] == material_v]
    akost_v = st.selectbox("Akosť", sorted(df_f['akost'].unique().tolist()) if not df_f.empty else ["N/A"])
    narocnost_v = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")
with t2:
    d_v = st.number_input("Priemer d [mm]", min_value=0.1, value=20.0, format="%.2f")
    l_v = st.number_input("Dĺžka l [mm]", min_value=0.1, value=50.0, format="%.2f")
    pocet_v = st.number_input("Počet kusov [ks]", min_value=1, value=1)

# Logika hustoty
hustota_v = 0.0
if material_v == "NEREZ": hustota_v = 8000.0
elif material_v == "OCEĽ": hustota_v = 7900.0
elif material_v == "PLAST":
    try: hustota_v = clean_number(df_f[df_f['akost'] == akost_v]['hustota'].iloc[0])
    except: hustota_v = 0.0
elif material_v == "FAREBNÉ KOVY":
    ako_s = str(akost_v)
    if ako_s.startswith("3.7"): hustota_v = 4500.0
    elif ako_s.startswith("3."): hustota_v = 2900.0
    else: hustota_v = 9000.0

with t3:
    st.metric("Vypočítaná hustota", f"{hustota_v} kg/m³")

# Geometrické medzivýpočty
plocha_prierezu = (math.pi * (d_v**2)) / 4
plocha_plasta = math.pi * d_v * l_v
hmotnost_v = hustota_v * (math.pi / 4) * (d_v / 1000)**2 * (l_v / 1000)

# Náklady
cena_mat_j = 0.0
res_mat = df_cennik[(df_cennik['material'] == material_v) & (df_cennik['akost'] == akost_v)]
if not res_mat.empty:
    res_mat = res_mat.copy(); res_mat['d_n'] = res_mat['d'].apply(clean_number)
    vhodne = res_mat[res_mat['d_n'] >= d_v].sort_values('d_n')
    if not vhodne.empty: cena_mat_j = clean_number(vhodne.iloc[0]['cena'])
cena_mat_kus = (cena_mat_j * l_v) / 1000

ma_koop = st.radio("Kooperácia?", ["Nie", "Áno"], horizontal=True)
cena_koop_v, druh_koop_v = 0.0, "Žiadna"
if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material_v]
    if not df_k_f.empty:
        druh_koop_v = st.selectbox("Vyber kooperáciu", sorted(df_k_f['druh'].unique()))
        rk = df_k_f[df_k_f['druh'] == druh_koop_v].iloc[0]
        def gv(r, k): 
            for c in r.index: 
                if all(x in c.lower() for x in k): return clean_number(r[c])
            return 0.0
        tarifa, min_z = gv(rk, ['tarifa']), gv(rk, ['min', 'zak'])
        jednotka = str(rk[[c for c in rk.index if 'jednotka' in c.lower()][0]]).lower()
        odhad = (tarifa * hmotnost_v) if 'kg' in jednotka else (tarifa * plocha_plasta / 10000)
        cena_koop_v = max(odhad, min_z / pocet_v)

vstupne_naklady_v = cena_mat_kus + cena_koop_v

# --- 4. AI PREDIKCIA ---
pred_cas, pred_cena = 0.0, 0.0
if ai["m1"] and ai["cols1"]:
    r1 = {'d':d_v, 'l':l_v, 'pocet_kusov':np.log1p(pocet_v), 'plocha_prierezu':plocha_prierezu,
          'plocha_plasta':plocha_plasta, 'lojalita':lojalita_v, 'hustota':hustota_v, 'vstupne_naklady':vstupne_naklady_v}
    for c in ai["cols1"]:
        if c not in r1: r1[c] = 0
        if c == f"material_{material_v.upper()}": r1[c] = 1
        if c == f"akost_{akost_v.upper()}": r1[c] = 1
        if c == f"narocnost_{narocnost_v}": r1[c] = 1
    pred_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([r1])[ai["cols1"]]))[0]))

if ai["m2"] and ai["cols2"] and pred_cas > 0:
    r2 = {'cas': pred_cas, 'hmotnost': hmotnost_v, 'lojalita': lojalita_v, 'hustota': hustota_v, 'plocha_prierezu': plocha_prierezu}
    for c in ai["cols2"]:
        if c not in r2: r2[c] = 0
        if c == f"krajina_{krajina_v}": r2[c] = 1
    pred_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([r2])[ai["cols2"]]))[0]))

# --- 5. TLAČIDLO PRIDAŤ A TABUĽKA PREMENNÝCH ---
st.info(f"💡 **AI Predikcia pre tento Item:** Čas: {round(pred_cas,2)} min | Cena: {round(pred_cena,2)} €")

if st.button("➕ PRIDAŤ POLOŽKU DO PONUKY"):
    nova_polozka = {
        "datum": str(datum_v), "ponuka": ponuka_v, "zakaznik": zakaznik_v, "krajina": krajina_v,
        "lojalita": lojalita_v, "item": item_v, "material": material_v, "akost": akost_v,
        "d": d_v, "l": l_v, "hustota": hustota_v, "hmotnost": round(hmotnost_v, 4),
        "narocnost": narocnost_v, "jednotkova_mat": round(cena_mat_j, 4),
        "naklad_mat_celkom": round(cena_mat_kus, 4), "cena_kooperacia": round(cena_koop_v, 4),
        "vstupne_naklady": round(vstupne_naklady_v, 4), "ai_cas": round(pred_cas, 2),
        "ai_cena": round(pred_cena, 2), "pocet_kusov": pocet_v, "cena_polozky_spolu": round(pred_cena * pocet_v, 2)
    }
    st.session_state.kosik.append(nova_polozka)
    st.success(f"Položka '{item_v}' bola pridaná do košíka.")

# --- 6. FINÁLNY PREHĽAD (KOŠÍK A VŠETKY PREMENNÉ) ---
if st.session_state.kosik:
    st.divider()
    st.subheader("📋 Rozpracovaná ponuka (Košík)")
    
    # Zobrazenie košíka v skrátenej forme
    df_kosik = pd.DataFrame(st.session_state.kosik)
    st.table(df_kosik[["item", "material", "akost", "pocet_kusov", "ai_cas", "ai_cena", "cena_polozky_spolu"]])
    
    # Detailný prehľad všetkých premenných (Full dump)
    with st.expander("🔍 Zobraziť všetky definované premenné pre každý riadok (EXAKTNÝ VÝPIS)"):
        st.write(df_kosik)

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        if st.button("💾 ODOŠLAŤ VŠETKO DO GOOGLE SHEETU"):
            uspesne = 0
            for polozka in st.session_state.kosik:
                try:
                    res = requests.post(URL_APPS_SCRIPT, json=polozka)
                    if res.status_code == 200: uspesne += 1
                except: pass
            
            if uspesne == len(st.session_state.kosik):
                st.success(f"✅ Všetkých {uspesne} položiek úspešne zapísaných do systému!")
                st.session_state.kosik = [] 
            else:
                st.error(f"⚠️ Uložených len {uspesne} z {len(st.session_state.kosik)}.")
    
    with col_u2:
        if st.button("🗑️ VYMAZAŤ CELÝ KOŠÍK"):
            st.session_state.kosik = []
            st.rerun()
