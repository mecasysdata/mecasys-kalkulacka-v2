import streamlit as st
import pandas as pd
import math
from datetime import date
import re
import numpy as np
import pickle
from xgboost import XGBRegressor
import requests
import datetime
from fpdf import FPDF
import io

# --- INICIALIZÁCIA KOŠÍKA (SESSION STATE) ---
if 'polozky_ponuky' not in st.session_state:
    st.session_state.polozky_ponuky = []

def pridat_polozku():
    nova_polozka = {
        "item":item,
        "Materiál": material,
        "Akosť": akost,
        "Rozmer (d x l)": f"{d} x {l} mm",
        "Kusov": pocet_kusov,
        "Čas (M1)": f"{cas:.2f} min",
        "Cena/ks (M2)": f"{predikovana_cena_m2:.2f} €",
        "Spolu": f"{predikovana_cena_m2 * pocet_kusov:.2f} €"
    }
    st.session_state.polozky_ponuky.append(nova_polozka)
    st.toast("Položka bola pridaná do ponuky! ✅")

# --- NAČÍTANIE DÁT (POTREBNÉ PRE SELEKTY) ---
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRcCPwLT_Cm8Xpj4urw7DUa5FGGyWiCEKKl8ySUEnGtFjsKzbvwtw6MURs1TyqasHhAJsWcdP6d3Q7O/pub?gid=0&single=true&output=csv"
sheet_zakaznici_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSuHQWbpryWNerWr8aKKheHbzTPhXI6lS7YH1sL5zwFIIzLfpTZz47acY_ua2e_fVqEcfxMBe5wnjue/pub?gid=0&single=true&output=csv"

@st.cache_data
def load_data(url):
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    for col in ['material', 'akost']:
        if col in data.columns:
            data[col] = data[col].astype(str).str.strip()
    return data

df_materialy = load_data(sheet_url)
df_zakaznici = load_data(sheet_zakaznici_url)

# =================================================================
# 1. RIADOK: ZÁKAZNÍK, DÁTUM, ČÍSLO PONUKY
# =================================================================
col_zak, col_dat, col_cp = st.columns([2, 1, 1])

with col_zak:
    seznam_zakaznikov = list(sorted(df_zakaznici['zakaznik'].unique()))
    if "Nový zákazník (zadať ručne)" not in seznam_zakaznikov:
        seznam_zakaznikov.append("Nový zákazník (zadať ručne)")
    zakaznik_vyber = st.selectbox("Vyberte zákazníka", options=seznam_zakaznikov, key="vybrany_zakaznik")

with col_dat:
    datum = st.date_input("Dátum", value=date.today())

with col_cp:
    ponuka = st.text_input("Číslo ponuky")

# --- LOGIKA ZÁKAZNÍKA (Krajina, Lojalita) ---
zakaznik = ""
krajina = ""
lojalita = 0.5

if zakaznik_vyber == "Nový zákazník (zadať ručne)":
    c1, c2 = st.columns(2)
    with c1: zakaznik = st.text_input("Meno nového zákazníka:")
    with c2: krajina = st.text_input("Krajina zákazníka:")
    if st.button("🚀 Uložiť zákazníka do databázy"):
        if zakaznik and krajina:
            payload = {"zakaznik": zakaznik, "krajina": krajina, "lojalita": 0.5}
            api_url = "https://script.google.com/macros/s/AKfycbwNR33wxSNXJFo9-o2otM-mdKQE22s3i3y5n08dY7eogGhhKDTasiPn3zaOoSihppTq/exec"
            requests.post(api_url, json=payload)
            st.success(f"Zákazník {zakaznik} uložený!")
else:
    zakaznik = zakaznik_vyber
    data_zak = df_zakaznici[df_zakaznici['zakaznik'] == zakaznik]
    if not data_zak.empty:
        krajina = str(data_zak['krajina'].values[0])
        raw_loj = str(data_zak['lojalita'].values[0]).replace(',', '.')
        lojalita = float(re.sub(r'[^0-9.]', '', raw_loj)) if raw_loj else 0.5

st.caption(f"🌍 Krajina: {krajina} | 💎 Lojalita: {lojalita}")

# =================================================================
# 2. RIADOK: ITEM, KS, NÁROČNOSŤ, D, L
# =================================================================
st.write("---")
c_it, c_ks, c_na, c_d, c_l = st.columns([1.5, 1, 1, 1, 1])

with c_it: item = st.text_input("Identifikátor položky")
with c_ks: pocet_kusov = st.number_input("Počet kusov", min_value=1, step=1, format="%d")
with c_na: narocnost = st.selectbox("Náročnosť", options=["1", "2", "3", "4", "5"])
with c_d: d = st.number_input("Priemer d [mm]", min_value=0.0, step=0.1, format="%.2f")
with c_l: l = st.number_input("Dĺžka l [mm]", min_value=0.0, step=0.1, format="%.2f")

# =================================================================
# 3. RIADOK: MATERIÁL, AKOSŤ, KOOPERÁCIA
# =================================================================
c_mat, c_ako, c_kop = st.columns([1.5, 1.5, 1])

with c_mat:
    seznam_materialov = sorted(df_materialy['material'].unique())
    material = st.selectbox("Materiál", options=seznam_materialov)

with c_ako:
    seznam_akosti = list(sorted(df_materialy[df_materialy['material'] == material]['akost'].unique()))
    seznam_akosti.append("Iná akosť (zadať ručne)")
    akost_vyber = st.selectbox("Akosť", options=seznam_akosti)

with c_kop:
    st.write(" ")
    je_kooperacia = st.checkbox("Kooperácia?", value=False, key="chk_koop_final")

# Logika pre akosť a hustotu
if akost_vyber == "Iná akosť (zadať ručne)":
    akost = st.text_input("Názov novej akosti:")
    hustota = 0.0
else:
    akost = akost_vyber
    hustota = 0.0
    if material == "PLAST":
        vyber = df_materialy[(df_materialy['material'] == material) & (df_materialy['akost'] == akost)]
        if not vyber.empty:
            hustota = float(str(vyber['hustota'].values[0]).replace(',', '.').replace('\xa0', '').replace(' ', ''))
    elif material == "NEREZ": hustota = 8000.0
    elif material == "OCEĽ": hustota = 7900.0
    elif material == "FAREBNÉ KOVY":
        akost_t = str(akost).replace(',', '.')
        if akost_t.startswith("3.7"): hustota = 4500.0
        elif akost_t.startswith("3."): hustota = 2900.0
        elif akost_t.startswith("2."): hustota = 9000.0

hustota = st.number_input("Hustota materiálu [kg/m3]:", value=hustota, format="%.2f")

# --- LOGIKA PRE ZÁPIS NOVEJ AKOSTI ---
if akost_vyber == "Iná akosť (zadať ručne)" and st.button("💾 Uložiť akosť do databázy"):
    url_api = "https://script.google.com/macros/s/AKfycbysapIykA2JulM9882rQmM3tfFvbvrmYDeW-iM5jyR4MTg8ZlNWhTdgV4pGxNhn6JNb/exec"
    requests.post(url_api, json={"material": material, "akost": akost, "hustota": hustota})
    st.success("Akosť uložená!")

if hustota <= 0: st.stop()

# =================================================================
# VÝPOČTY (MATERIÁL, NÁKLADY, MODELY)
# =================================================================
st.divider()

# Cena materiálu
sheet_cena_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKPX6HAAr7R3anJH9brFYZdgdnoVasW2NkR-O-hgUv3NebNSbWaKRuC3_CifXgeKsvi1K3na4-gZxU/pub?gid=0&single=true&output=csv"
df_ceny = load_data(sheet_cena_url)
nalezena_cena = 0.0
mask = (df_ceny['material'] == material) & (df_ceny['akost'] == akost)
dostupne = df_ceny[mask].copy()
if not dostupne.empty:
    vhodne = dostupne[dostupne['d'] >= d]
    if not vhodne.empty:
        nalezena_cena = float(str(vhodne.sort_values(by='d').iloc[0]['cena']).replace(',', '.'))

cena_za_meter = st.number_input("Cena materiálu [€/m]:", value=nalezena_cena, format="%.2f")
cena_material = cena_za_meter * (l / 1000)

# Uloženie do cenníka ak chýba
if nalezena_cena == 0 and st.button("💾 Uložiť cenu do cenníka"):
    url_cennik = "https://script.google.com/macros/s/AKfycbzrIngx_yh9h--ilq_SV3glHARaLb7pncAVEsrIQG9JQBRolvuzWcPTCq2EHuFtewgeXw/exec"
    requests.post(url_cennik, json={"material": material, "akost": akost, "d": d, "cena": cena_za_meter})
    st.success("Cena uložená!")

# Technické výpočty
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)
plocha_prierezu = (math.pi * d**2) / 4
plocha_prierez_dm2 = plocha_prierezu / 10000
plocha_plasta = math.pi * d * l

# Kooperácia
cena_kooperacia = 0.0
if je_kooperacia:
    sheet_koop_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv"
    df_koop = load_data(sheet_koop_url)
    vybrany_druh = st.selectbox("Druh kooperácie", options=sorted(df_koop['druh'].unique()))
    riadok_koop = df_koop[(df_koop['druh'] == vybrany_druh)].iloc[0]
    tarifa = float(riadok_koop['tarifa'])
    jednotka = str(riadok_koop['jednotka']).strip().lower()
    vyp_cena = tarifa * hmotnost if jednotka == "kg" else tarifa * plocha_prierez_dm2
    cena_kooperacia = max(vyp_cena, float(riadok_koop['minimum']) / pocet_kusov)

vstupne_naklady = cena_material + cena_kooperacia

# Modely (M1 a M2)
cas = 0.0
predikovana_cena_m2 = 0.0

try:
    with open('MECASYS_APP/stlpce_modelu.pkl', 'rb') as f: m_cols = pickle.load(f)
    m1 = XGBRegressor(); m1.load_model('MECASYS_APP/finalny_model.json')
    inp1 = pd.DataFrame(0, index=[0], columns=m_cols)
    inp1['pocet_kusov'] = np.log1p(pocet_kusov); inp1['d'] = d; inp1['l'] = l
    inp1['plocha_prierezu'] = plocha_prierezu; inp1['plocha_plasta'] = plocha_plasta
    for p, v in {'material': material, 'akost': akost, 'narocnost': narocnost}.items():
        if f"{p}_{v}" in inp1.columns: inp1[f"{p}_{v}"] = 1
    cas = np.expm1(m1.predict(inp1)[0])

    with open('MECASYS_APP/model_columns.pkl', 'rb') as f: m2_cols = pickle.load(f)
    m2 = XGBRegressor(); m2.load_model('MECASYS_APP/xgb_model_cena.json')
    inp2 = pd.DataFrame(0, index=[0], columns=m2_cols)
    inp2['cas'] = cas; inp2['hmotnost'] = hmotnost; inp2['plocha_prierezu'] = plocha_prierezu; inp2['hustota'] = hustota
    if f"krajina_{krajina}" in inp2.columns: inp2[f"krajina_{krajina}"] = 1
    predikovana_cena_m2 = np.expm1(m2.predict(inp2)[0])
except: pass

# =================================================================
# 4. RIADOK: SUMARIZÁCIA VÝSLEDKOV
# =================================================================
st.subheader("📊 Výsledky predikcie")
res1, res2, res3, res4, res5 = st.columns(5)
with res1: st.metric("Čas (M1)", f"{cas:.2f} min")
with res2: st.metric("Cena (M2)", f"{predikovana_cena_m2:.2f} €")
with res3: st.metric("Hmotnosť", f"{hmotnost:.4f} kg")
with res4: st.metric("Plášť", f"{plocha_plasta:.0f} mm²")
with res5: st.metric("Prierez", f"{plocha_prierezu:.2f} mm²")

# Kontrola nákladov a finálna cena
st.divider()
if vstupne_naklady >= predikovana_cena_m2:
    st.error(f"⚠️ Pozor! Náklady ({vstupne_naklady:.2f} €) sú vyššie ako predikcia.")
else:
    st.info(f"💡 Vstupné náklady: {vstupne_naklady:.2f} €")

predikovana_cena_m2 = st.number_input("Finálna predajná cena [€/ks]:", value=float(predikovana_cena_m2), format="%.2f", key="final_user_p")

# =================================================================
# KOŠÍK, EXPORTY A PDF (Pôvodná logika)
# =================================================================
st.button("➕ Pridať do ponuky", on_click=pridat_polozku)

if st.session_state.polozky_ponuky:
    st.table(pd.DataFrame(st.session_state.polozky_ponuky))
    celkova_suma = sum([float(i['Spolu'].replace(' €', '')) for i in st.session_state.polozky_ponuky])
    st.metric("CELKOVÁ CENA PONUKY", f"{celkova_suma:.2f} €")
    
    if st.button("🗑️ Vymazať ponuku"):
        st.session_state.polozky_ponuky = []; st.rerun()

    if st.button("Zapísať do Google Sheet"):
        url_s = "https://script.google.com/macros/s/AKfycbwjChtJjHiZZyU8nVVpHKhcRj2z77pqrJNTw6rDm9dy_WzFaX6Yj0zzbmCSeHU7r8UUyA/exec"
        items_payload = []
        for i, p in enumerate(st.session_state.polozky_ponuky):
            items_payload.append({
                "datum": date.today().strftime("%d.%m.%Y"), "cislo_cp": ponuka, "zakaznik": zakaznik,
                "item_nazov": p["item"], "material": p["Materiál"], "akost": p["Akosť"], "pocet_kusov": p["Kusov"],
                "jednotkova_cena": float(p["Cena/ks (M2)"].replace(' €', '')), "cena_spolu": float(p["Spolu"].replace(' €', ''))
            })
        requests.post(url_s, json={"items": items_payload})
        st.success("Zapísané!")

    # PDF Export
    if st.button("Pripraviť finálne PDF"):
        pdf = FPDF(orientation='L', unit='mm', format='A4'); pdf.add_page()
        pdf.set_font("Helvetica", "B", 16); pdf.cell(0, 10, "CENOVA PONUKA", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"Zakaznik: {zakaznik}", ln=True)
        pdf.ln(10)
        pdf.set_font("Helvetica", "B", 9)
        cols = ["Item", "Material", "Rozmer", "Ks", "Cena/ks", "Spolu"]
        w = [30, 60, 50, 20, 40, 40]
        for i, h in enumerate(cols): pdf.cell(w[i], 10, h, border=1, align='C')
        pdf.ln(); pdf.set_font("Helvetica", "", 8)
        for p in st.session_state.polozky_ponuky:
            pdf.cell(w[0], 8, str(p['item']), border=1)
            pdf.cell(w[1], 8, f"{p['Materiál']} {p['Akosť']}", border=1)
            pdf.cell(w[2], 8, p['Rozmer (d x l)'], border=1)
            pdf.cell(w[3], 8, str(p['Kusov']), border=1, align='C')
            pdf.cell(w[4], 8, p['Cena/ks (M2)'], border=1, align='R')
            pdf.cell(w[5], 8, p['Spolu'], border=1, align='R')
            pdf.ln()
        st.download_button("⬇️ Stiahnuť PDF", data=bytes(pdf.output()), file_name="ponuka.pdf", mime="application/pdf")
