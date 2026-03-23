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
    if pd.isna(val) or val == "" or val is None: return 0.0
    try:
        s = str(val).replace('\xa0', '').replace(' ', '').replace(',', '.')
        return float(s)
    except: return 0.0

# --- 2. KONFIGURÁCIA ---
st.set_page_config(page_title="MECASYS AI - Final Tool", layout="wide")

if 'kosik' not in st.session_state:
    st.session_state.kosik = []

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbx4Tt5BZa0Af9OUpXWLcgpZmOH5XM85wMXs30hv8LtA2atZ99Re7WShnEBWMKa6ctc_AQ/exec"

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
    except: st.error("⚠️ AI modely nenájdené.")
    return assets

# Načítanie dát
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
df_zakaznici = load_data(f"{URL_BASE}gid=324957857&single=true&output=csv")
df_mat_hustota = load_data(f"{URL_BASE}gid=1281008948&single=true&output=csv")
df_cennik_mat = load_data(f"{URL_BASE}gid=901617097&single=true&output=csv")
df_koop_cennik = load_data(f"{URL_BASE}gid=1180392224&single=true&output=csv")
ai = load_ai_models()

# --- 3. HLAVA PONUKY ---
st.title("⚙️ MECASYS AI: Kalkulačný Systém")
c1, c2 = st.columns(2)
with c1:
    cislo_cp = st.text_input("Číslo CP", value=datetime.now().strftime("%Y-%m") + "-001")
    vyber_z = st.selectbox("Zákazník", sorted(df_zakaznici['zakaznik'].unique()) if not df_zakaznici.empty else ["---"])
with c2:
    item_nazov = st.text_input("Názov položky (ITEM)", value=f"Diel {len(st.session_state.kosik)+1}")
    datum_cp = st.date_input("Dátum vystavenia", datetime.now())

dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0] if not df_zakaznici.empty else {}
lojalita = safe_num(dz.get('lojalita', 0.5))
krajina = str(dz.get('krajina', 'SK'))

# --- 4. TECHNICKÉ PARAMETRE ---
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    v_mat = st.selectbox("Materiál", sorted(df_mat_hustota['material'].unique()))
    df_f = df_mat_hustota[df_mat_hustota['material'] == v_mat]
    v_akost = st.selectbox("Akosť", sorted(df_f['akost'].unique()))
with col2:
    d = st.number_input("Priemer d [mm]", value=20.0, step=0.1)
    l = st.number_input("Dĺžka l [mm]", value=50.0, step=0.1)
with col3:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")

# --- PRESNÉ VÝPOČTY (8 DESATINNÝCH MIEST) ---
row_h = df_f[df_f['akost'] == v_akost]
hustota = safe_num(row_h.iloc[0]['hustota']) if not row_h.empty else 7850.0

# Hmotnosť v kg na 8 desatinných miest
hmotnost = float(hustota * (math.pi/4) * (d/1000)**2 * (l/1000))
# Plocha plášťa v mm2 a prevod na dm2 na 8 desatinných miest
plocha_plasta_mm2 = math.pi * d * l
plocha_dm2 = float(plocha_plasta_mm2 / 10000)

# Sidebar pre kontrolu
st.sidebar.header("🔍 Röntgen súčiastky")
st.sidebar.write(f"Váha: `{hmotnost:.8f}` kg")
st.sidebar.write(f"Plocha: `{plocha_dm2:.88f}` dm²")

res_m = df_cennik_mat[(df_cennik_mat['material']==v_mat)&(df_cennik_mat['akost']==v_akost)&(df_cennik_mat['d']>=d)].sort_values('d')
cena_za_meter = safe_num(res_m.iloc[0]['cena']) if not res_m.empty else 0.0

# --- 5. EKONOMICKÝ PANEL (LOGIKA KOOPERÁCIE) ---
st.markdown("### 💰 Ekonomický prehľad položky")
eco1, eco2, eco3 = st.columns(3)

with eco1:
    st.write("**Materiál**")
    j_mat_potvrdena = st.number_input("Cena za meter [€/m]", value=cena_za_meter, format="%.2f")
    naklad_mat_ks = (j_mat_potvrdena * l) / 1000
    st.info(f"Náklad na 1 kus: **{naklad_mat_ks:.3f} €**")

with eco2:
    st.write("**Kooperácia**")
    # Bod 1: Rozhodovacia logika
    ma_koop = st.radio("Vyžaduje diel kooperáciu?", ["Nie", "Áno"], horizontal=True)
    
    naklad_koop_ks = 0.0
    if ma_koop == "Áno":
        m_clean = str(v_mat).strip()
        df_koop_cennik.columns = df_koop_cennik.columns.str.strip()
        
        # Bod 2: Filtrovanie a vyhľadávanie
        dostupne_row = df_koop_cennik[df_koop_cennik['material'].astype(str).str.strip() == m_clean]
        
        if not dostupne_row.empty:
            v_druh = st.selectbox("Druh kooperácie", sorted(dostupne_row['druh'].unique().tolist()))
            r = dostupne_row[dostupne_row['druh'] == v_druh].iloc[0]
            
            tarifa = safe_num(r.get('tarifa', 0))
            jednotka = str(r.get('jednotka', 'ks')).lower().strip()
            min_zakazka = safe_num(r.get('minimalna_zakazka', r.get('min_zakazka', 0)))

            # Bod 3: Výpočtové algoritmy (Odhad na 1 kus)
            odhad_kooperacie = 0.0
            if 'kg' in jednotka:
                odhad_kooperacie = float(tarifa * hmotnost)
            elif 'dm' in jednotka:
                odhad_kooperacie = float(plocha_dm2 * tarifa)
            else:
                odhad_kooperacie = float(tarifa)

            # Bod 4: Ochranná podmienka (Kontrola minimálnej zákazky)
            celkom_seria = pocet_kusov * odhad_kooperacie

            if celkom_seria < min_zakazka:
                naklad_koop_ks = min_zakazka / pocet_kusov
                st.warning(f"Aplikovaná minimálna zákazka: {min_zakazka} €")
            else:
                naklad_koop_ks = odhad_kooperacie
                st.success(f"Použitá tarifa: {tarifa} €/{jednotka}")
            
            st.caption(f"Vypočítaný základ na kus: {odhad_kooperacie:.8f} €")

    naklad_koop_ks = st.number_input("Kooperácia na kus [€]", value=float(naklad_koop_ks), format="%.4f")

with eco3:
    st.write("**Súčet nákladov**")
    vstupne_naklady = naklad_mat_ks + naklad_koop_ks
    st.metric("CELKOVÉ NÁKLADY", f"{vstupne_naklady:.3f} €/ks")

# --- 6. AI PREDIKCIA ---
ai_cas, ai_cena = 0.0, 0.0
if ai["m1"] and ai["m2"]:
    v1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': (math.pi*d**2)/4, 'plocha_plasta': plocha_plasta_mm2, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
    for c in ai["cols1"]:
        if c not in v1: v1[c] = 0
        if c == f"material_{v_mat}": v1[c] = 1
        if c == f"narocnost_{narocnost}": v1[c] = 1
    ai_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([v1])[ai["cols1"]]))[0]))
    
    v2 = {'cas': ai_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': (math.pi*d**2)/4}
    for c in ai["cols2"]:
        if c not in v2: v2[c] = 0
        if c == f"krajina_{krajina}": v2[c] = 1
    ai_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]]))[0]))

st.divider()
r1, r2 = st.columns(2)
r1.metric("Odhadovaný ČAS (AI)", f"{ai_cas:.2f} min")

# Zobrazenie odporúčanej ceny (Brzda je teraz vizuálne preč, ale cenu budeme sledovať)
r2.metric("Odporúčaná CENA (AI)", f"{ai_cena:.2f} €/ks")

# --- 7. KOŠÍK ---
if st.button("➕ PRIDAŤ DO PONUKY", type="primary", use_container_width=True):
    st.session_state.kosik.append({
        "datum": datum_cp.strftime("%d.%m.%Y"), "ponuka": cislo_cp, "zakaznik": vyber_z, "item": item_nazov, "material": v_mat, "pocet_kusov": pocet_kusov, "hmotnost_kg": round(hmotnost, 8), "vstupne_naklady": vstupne_naklady, "ai_cena": ai_cena, "cena_spolu": ai_cena * pocet_kusov
    })
    st.toast("Položka pridaná!")

if st.session_state.kosik:
    st.divider()
    df_k = pd.DataFrame(st.session_state.kosik)
    st.table(df_k)
    if st.button("💾 ULOŽIŤ DO GOOGLE SHEETS"):
        for p in st.session_state.kosik: requests.post(WEBHOOK_URL, json=p)
        st.success("Uložené!"); st.session_state.kosik = []
