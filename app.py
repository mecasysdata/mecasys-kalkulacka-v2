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

# Tvoj overený link na Google Apps Script
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbx4Tt5BZa0Af9OUpXWLcgpZmOH5XM85wMXs30hv8LtA2atZ99Re7WShnEBWMKa6ctc_AQ/exec"

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()  # Odstráni medzery z názvov stĺpcov
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
    except: st.error("⚠️ AI modely nenájdené v priečinku MECASYS_APP/")
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
    d = st.number_input("Priemer d [mm]", value=20.0, step=1.0)
    l = st.number_input("Dĺžka l [mm]", value=50.0, step=1.0)
with col3:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť", options=["1","2","3","4","5"], value="3")

# Výpočty geometrie
row_h = df_f[df_f['akost'] == v_akost]
hustota = safe_num(row_h.iloc[0]['hustota']) if not row_h.empty else 7850.0
hmotnost = hustota * (math.pi/4) * (d/1000)**2 * (l/1000)
plocha_plasta = math.pi * d * l

# Hľadanie v cenníku materiálu
res_m = df_cennik_mat[(df_cennik_mat['material']==v_mat)&(df_cennik_mat['akost']==v_akost)&(df_cennik_mat['d']>=d)].sort_values('d')
cena_za_meter = safe_num(res_m.iloc[0]['cena']) if not res_m.empty else 0.0

# --- 5. EKONOMICKÝ PANEL (Upravená Kooperácia) ---
st.markdown("### 💰 Ekonomický prehľad položky")
eco1, eco2, eco3 = st.columns(3)

with eco1:
    st.write("**Materiál**")
    j_mat_potvrdena = st.number_input("Cena za meter [€/m]", value=cena_za_meter, format="%.2f")
    naklad_mat_ks = (j_mat_potvrdena * l) / 1000
    st.info(f"Náklad na 1 kus: **{naklad_mat_ks:.3f} €**")

with eco2:
    st.write("**Kooperácia**")
    m_clean = str(v_mat).strip()
    # Očistíme názvy stĺpcov pre istotu
    df_koop_cennik.columns = df_koop_cennik.columns.str.strip()
    dostupne_row = df_koop_cennik[df_koop_cennik['material'].astype(str).str.strip() == m_clean]
    dostupne_koop = dostupne_row['druh'].unique().tolist()
    
    v_koop = st.selectbox("Druh kooperácie", ["Bez kooperácie"] + sorted(dostupne_koop))
    
    vyp_koop_ks = 0.0
    if v_koop != "Bez kooperácie":
        mk = dostupne_row[dostupne_row['druh'] == v_koop]
        if not mk.empty:
            r = mk.iloc[0]
            tar = safe_num(r.get('tarifa', 0))
            # Hľadáme min sadzbu pod rôznymi názvami kvôli Excelu
            minz = safe_num(r.get('minimalna_zakazka', r.get('min_zakazka', r.get('minimalna sadzba', 0))))
            jedn = str(r.get('jednotka', 'ks')).lower().strip()
            
            if 'kg' in jedn: base = tar * hmotnost
            elif 'dm2' in jedn: base = tar * (plocha_plasta / 10000)
            else: base = tar
            
            # Logika Minimálky: max(základná cena, minimálna sadzba rozpočítaná na kusy)
            vyp_koop_ks = max(base, minz / pocet_kusov)
            st.caption(f"Info: Tarifa {tar}€ | Min. objednávka: {minz}€")

    naklad_koop_ks = st.number_input("Kooperácia na kus [€]", value=float(vyp_koop_ks), format="%.3f")

with eco3:
    st.write("**Súčet nákladov**")
    vstupne_naklady = naklad_mat_ks + naklad_koop_ks
    st.metric("CELKOVÉ NÁKLADY", f"{vstupne_naklady:.3f} €/ks")

# --- 6. AI PREDIKCIA ---
ai_cas, ai_cena = 0.0, 0.0
if ai["m1"] and ai["m2"]:
    # M1 - Čas
    v1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': (math.pi*d**2)/4, 'plocha_plasta': plocha_plasta, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
    for c in ai["cols1"]:
        if c not in v1: v1[c] = 0
        if c == f"material_{v_mat}": v1[c] = 1
        if c == f"narocnost_{narocnost}": v1[c] = 1
    ai_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([v1])[ai["cols1"]]))[0]))
    
    # M2 - Cena
    v2 = {'cas': ai_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': (math.pi*d**2)/4}
    for c in ai["cols2"]:
        if c not in v2: v2[c] = 0
        if c == f"krajina_{krajina}": v2[c] = 1
    ai_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]]))[0]))

st.divider()
r1, r2 = st.columns(2)
r1.metric("Odhadovaný ČAS (AI)", f"{ai_cas:.2f} min")

# LOGIKA OCHRANY ZISKU
final_predajna_cena = ai_cena
if ai_cena < vstupne_naklady:
    st.error(f"⚠️ AI cena ({ai_cena:.2f} €) je pod nákladmi ({vstupne_naklady:.2f} €)!")
    final_predajna_cena = vstupne_naklady * 1.30 # Návrh ceny s 30% maržou
    st.warning(f"Navrhovaná bezpečná cena: {final_predajna_cena:.2f} €")

r2.metric("Odporúčaná PREDAJNÁ CENA", f"{final_predajna_cena:.2f} €/ks")

# --- 7. KOŠÍK A UKLADANIE ---
if st.button("➕ PRIDAŤ DO ZOZNAMU PONUKY", type="primary", use_container_width=True):
    st.session_state.kosik.append({
        "datum": datum_cp.strftime("%d.%m.%Y"),
        "ponuka": cislo_cp,
        "zakaznik": vyber_z,
        "krajina": krajina,
        "lojalita": lojalita,
        "item": item_nazov,
        "material": v_mat,
        "akost": v_akost,
        "d": d,
        "l": l,
        "hustota": hustota,
        "hmotnost": hmotnost,
        "narocnost": narocnost,
        "jednotkova_mat": j_mat_potvrdena,
        "naklad_mat_celkom": naklad_mat_ks,
        "cena_kooperacia": naklad_koop_ks,
        "vstupne_naklady": vstupne_naklady,
        "ai_cas": ai_cas,
        "ai_cena": final_predajna_cena,
        "pocet_kusov": pocet_kusov,
        "cena_polozky_spolu": final_predajna_cena * pocet_kusov
    })
    st.toast("Položka pridaná!")

if st.session_state.kosik:
    st.divider()
    df_k = pd.DataFrame(st.session_state.kosik)
    st.table(df_k[["item", "material", "pocet_kusov", "vstupne_naklady", "ai_cena", "cena_polozky_spolu"]])
    
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("🗑️ VYMAZAŤ ZOZNAM"):
            st.session_state.kosik = []; st.rerun()
    with cb2:
        if st.button("💾 ULOŽIŤ CELÚ PONUKU", type="primary"):
            with st.spinner("Odosielam do Google Sheets..."):
                try:
                    for p in st.session_state.kosik:
                        requests.post(WEBHOOK_URL, json=p)
                    st.success("Dáta boli úspešne uložené!")
                    st.session_state.kosik = []
                except:
                    st.error("Chyba pri ukladaní. Skontroluj internet alebo Apps Script link.")
