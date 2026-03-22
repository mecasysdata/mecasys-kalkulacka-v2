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
    if pd.isna(val) or val == "": return 0.0
    try:
        s = str(val).replace('\xa0', '').replace(' ', '').replace(',', '.')
        return float(s)
    except: return 0.0

# --- 2. KONFIGURÁCIA A SESSION STATE ---
st.set_page_config(page_title="MECASYS AI - Ponukový Systém", layout="wide")

if 'kosik' not in st.session_state:
    st.session_state.kosik = []

# TVOJ FINÁLNY LINK NA APPS SCRIPT
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
        # Model 1 (Čas)
        m1 = xgb.Booster(); m1.load_model(f"{p}finalny_model.json")
        with open(f"{p}stlpce_modelu.pkl", 'rb') as f: assets["cols1"] = pickle.load(f)
        assets["m1"] = m1
        # Model 2 (Cena)
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

# --- 5. LOGIKA VÝPOČTOV ---
row_h = df_f[df_f['akost'] == v_akost]
hustota = safe_num(row_h.iloc[0]['hustota']) if not row_h.empty else 7850.0
hmotnost = hustota * (math.pi/4) * (d/1000)**2 * (l/1000)
plocha_plasta = math.pi * d * l

res_m = df_cennik_mat[(df_cennik_mat['material']==v_mat)&(df_cennik_mat['akost']==v_akost)&(df_cennik_mat['d']>=d)].sort_values('d')
cena_za_meter = safe_num(res_m.iloc[0]['cena']) if not res_m.empty else 0.0

# --- 6. EKONOMICKÝ PANEL ---
st.markdown("### 💰 Ekonomický prehľad položky")
eco1, eco2, eco3 = st.columns(3)

with eco1:
    st.write("**Materiál**")
    j_mat_potvrdena = st.number_input("Cena za meter [€/m]", value=cena_za_meter, format="%.2f")
    naklad_mat_ks = (j_mat_potvrdena * l) / 1000
    st.info(f"Náklad na 1 kus: **{naklad_mat_ks:.3f} €**")

with eco2:
    st.write("**Kooperácia**")
    v_koop = st.selectbox("Druh kooperácie", ["Bez kooperácie"] + sorted(df_koop_cennik['druh'].unique().tolist()))
    vyp_koop_ks = 0.0
    if v_koop != "Bez kooperácie":
        mk = df_koop_cennik[(df_koop_cennik['druh'] == v_koop) & (df_koop_cennik['material'] == v_mat)]
        if not mk.empty:
            tar, minz, jedn = safe_num(mk.iloc[0]['tarifa']), safe_num(mk.iloc[0]['minimalna_zakazka']), str(mk.iloc[0]['jednotka']).lower()
            zakl = (tar * hmotnost) if 'kg' in jedn else (tar * (plocha_plasta / 10000))
            vyp_koop_ks = max(zakl, minz / pocet_kusov)
    naklad_koop_ks = st.number_input("Kooperácia na kus [€]", value=vyp_koop_ks, format="%.3f")

with eco3:
    st.write("**Súčet nákladov**")
    vstupne_naklady = naklad_mat_ks + naklad_koop_ks
    st.metric("CELKOVÉ NÁKLADY", f"{vstupne_naklady:.3f} €/ks")

# --- 7. AI PREDIKCIA ---
ai_cas, ai_cena = 0.0, 0.0
if ai["m1"] and ai["m2"]:
    # M1 - ČAS
    v1 = {'d': d, 'l': l, 'pocet_kusov': np.log1p(pocet_kusov), 'plocha_prierezu': (math.pi*d**2)/4, 'plocha_plasta': plocha_plasta, 'lojalita': lojalita, 'hustota': hustota, 'vstupne_naklady': vstupne_naklady}
    for c in ai["cols1"]:
        if c not in v1: v1[c] = 0
        if c == f"material_{v_mat}": v1[c] = 1
        if c == f"narocnost_{narocnost}": v1[c] = 1
    ai_cas = float(np.expm1(ai["m1"].predict(xgb.DMatrix(pd.DataFrame([v1])[ai["cols1"]]))[0]))
    
    # M2 - CENA
    v2 = {'cas': ai_cas, 'hmotnost': hmotnost, 'lojalita': lojalita, 'hustota': hustota, 'plocha_prierezu': (math.pi*d**2)/4}
    for c in ai["cols2"]:
        if c not in v2: v2[c] = 0
        if c == f"krajina_{krajina}": v2[c] = 1
    ai_cena = float(np.expm1(ai["m2"].predict(xgb.DMatrix(pd.DataFrame([v2])[ai["cols2"]]))[0]))

st.divider()
r1, r2 = st.columns(2)
if ai_cas < 0: r1.error("Chyba: Záporný čas.")
else: r1.metric("Odhadovaný ČAS (AI)", f"{ai_cas:.2f} min")

if ai_cena <= 0: r2.error("Chyba: Neplatná predikcia ceny.")
else: r2.metric("Odporúčaná PREDAJNÁ CENA", f"{ai_cena:.2f} €/ks")

# --- 8. KOŠÍK A ODOSLANIE ---
if st.button("➕ PRIDAŤ POLOŽKU DO ZOZNAMU", type="primary", use_container_width=True):
    if ai_cena > 0:
        nova_polozka = {
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
            "ai_cena": ai_cena,
            "pocet_kusov": pocet_kusov,
            "cena_polozky_spolu": ai_cena * pocet_kusov
        }
        st.session_state.kosik.append(nova_polozka)
        st.toast(f"Položka {item_nazov} pridaná!")
    else:
        st.error("Nemožno pridať položku s chybnou cenou.")

if st.session_state.kosik:
    st.divider()
    st.subheader("📋 Rozpracovaná ponuka")
    df_kosik = pd.DataFrame(st.session_state.kosik)
    st.dataframe(df_kosik[["item", "material", "pocet_kusov", "vstupne_naklady", "ai_cena", "cena_polozky_spolu"]], use_container_width=True)
    
    st.write(f"**Celková hodnota CP: {df_kosik['cena_polozky_spolu'].sum():.2f} €**")
    
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("🗑️ VYMAZAŤ ZOZNAM"):
            st.session_state.kosik = []
            st.rerun()
    with cb2:
        if st.button("🚀 ODOVZDAŤ A ULOŽIŤ PONUKU", type="primary"):
            with st.spinner("Zapisujem do 'databaza_ponuk'..."):
                uspech = True
                for p in st.session_state.kosik:
                    resp = requests.post(WEBHOOK_URL, json=p)
                    if resp.status_code != 200: uspech = False
                
                if uspech:
                    st.success("✅ Všetko bolo úspešne uložené do Google Sheetu!")
                    st.session_state.kosik = []
                else:
                    st.error("❌ Chyba pri ukladaní. Skontrolujte Apps Script.")
