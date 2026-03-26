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
        "Materiál": material,
        "Akosť": akost,
        "Rozmer (d x l)": f"{d} x {l} mm",
        "Kusov": pocet_kusov,
        "Čas (M1)": f"{cas:.2f} min",
        "Cena/ks (M2)": f"{finalna_cena_na_zapis:.2f} EUR", 
        "Spolu": f"{finalna_cena_na_zapis * pocet_kusov:.2f} EUR",
        # Dáta pre PDF a Export
        "mat_na_kus": cena_material,
        "koop_na_kus": cena_kooperacia,
        "predikovany_cas": cas,
        "identifikator_polozky": item
    }
    st.session_state.polozky_ponuky.append(nova_polozka)
    st.toast("Položka pridaná do ponuky! ✅")

# --- VSTUPNÉ PREMENNÉ ---
datum = st.date_input("Dátum", value=date.today())
ponuka = st.text_input("Číslo ponuky")
item = st.text_input("Identifikátor položky")
pocet_kusov = st.number_input("Počet kusov", min_value=1, step=1, format="%d")
narocnost = st.selectbox("Náročnosť", options=["1", "2", "3", "4", "5"])
d = st.number_input("Priemer komponentu [mm]", min_value=0.0, step=0.1, format="%.2f")
l = st.number_input("Dĺžka komponentu [mm]", min_value=0.0, step=0.1, format="%.2f")

# --- NAČÍTANIE SHEETU (MATERIÁLY) ---
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

@st.cache_data
def load_data(url):
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    for col in ['material', 'akost']:
        data[col] = data[col].astype(str).str.strip()
    return data

df_materialy = load_data(sheet_url)
seznam_materialov = sorted(df_materialy['material'].unique())
material = st.selectbox("Materiál", options=seznam_materialov)

seznam_akosti = list(sorted(df_materialy[df_materialy['material'] == material]['akost'].unique()))
seznam_akosti.append("Iná akosť (zadať ručne)")
akost_vyber = st.selectbox("Akosť", options=seznam_akosti)

if akost_vyber == "Iná akosť (zadať ručne)":
    akost = st.text_input("Zadajte názov novej akosti:")
    if not akost: st.stop()
else:
    akost = akost_vyber

# --- HUSTOTA ---
hustota = 0.0
if material == "PLAST":
    vyber = df_materialy[(df_materialy['material'] == material) & (df_materialy['akost'] == akost)]
    if not vyber.empty:
        raw_val = str(vyber['hustota'].values[0]).strip().replace(',', '')
        clean_val = re.sub(r'[^0-9.]', '', raw_val)
        hustota = float(clean_val)
elif material == "NEREZ": hustota = 8000.0
elif material == "OCEĽ": hustota = 7900.0
elif material == "FAREBNÉ KOVY":
    if akost.startswith("3.7"): hustota = 4500.0
    elif akost.startswith("3."): hustota = 2900.0
    elif akost.startswith("2."): hustota = 9000.0

if hustota <= 0:
    hustota = st.number_input("Zadajte hustotu manuálne [kg/m3]:", min_value=0.0, format="%.2f")
else:
    hustota = st.number_input("Hustota materiálu [kg/m3]:", value=hustota, format="%.2f")

# --- GEOMETRIA ---
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)
plocha_prierezu = (math.pi * d**2) / 4
plocha_prierez_dm2 = plocha_prierezu / 10000
plocha_plasta = math.pi * d * l

# --- ZÁKAZNÍK ---
sheet_zakaznici_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"
df_zakaznici = pd.read_csv(sheet_zakaznici_url)
seznam_zakaznikov = list(sorted(df_zakaznici['zakaznik'].unique()))
seznam_zakaznikov.append("Nový zákazník (zadať ručne)")
zakaznik_vyber = st.selectbox("Zákazník", options=seznam_zakaznikov)

if zakaznik_vyber == "Nový zákazník (zadať ručne)":
    zakaznik = st.text_input("Meno nového zákazníka:")
    krajina = st.text_input("Krajina:")
    lojalita = 0.5
else:
    zakaznik = zakaznik_vyber
    dz = df_zakaznici[df_zakaznici['zakaznik'] == zakaznik].iloc[0]
    krajina = str(dz['krajina'])
    lojalita = float(str(dz['lojalita']).replace(',', '.'))

# --- CENA MATERIÁLU ---
sheet_cena_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv"
df_ceny = pd.read_csv(sheet_cena_url)
mask = (df_ceny['material'] == material) & (df_ceny['akost'] == akost)
vhodne = df_ceny[mask & (df_ceny['d'] >= d)].sort_values(by='d')
nalezena_cena = float(str(vhodne.iloc[0]['cena']).replace(',', '.')) if not vhodne.empty else 0.0

cena_za_meter = st.number_input("Cena za meter [EUR/m]:", value=nalezena_cena)
cena_material = cena_za_meter * (l / 1000)

# --- KOOPERÁCIA ---
sheet_koop_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv"
df_koop = pd.read_csv(sheet_koop_url)
je_kooperacia = st.checkbox("Kooperácia?")
cena_kooperacia = 0.0

if je_kooperacia:
    druh_k = st.selectbox("Druh koop.", options=df_koop['druh'].unique())
    riadok_k = df_koop[df_koop['druh'] == druh_k].iloc[0]
    tarifa = float(riadok_k['tarifa'])
    jednotka = str(riadok_k['jednotka']).lower()
    vyp_c = tarifa * hmotnost if jednotka == "kg" else tarifa * plocha_prierez_dm2
    cena_kooperacia = max(vyp_c, float(riadok_k['minimum']) / pocet_kusov)

vstupne_naklady = cena_material + cena_kooperacia

# --- TVRDÉ NAČÍTANIE MODELOV (BEZ TRY-EXCEPT) ---
# Model 1 (Čas)
with open('MECASYS_APP/stlpce_modelu.pkl', 'rb') as f: m_cols = pickle.load(f)
m1 = XGBRegressor(); m1.load_model('MECASYS_APP/finalny_model.json')
input_df = pd.DataFrame(0, index=[0], columns=m_cols)
input_df['pocet_kusov'] = np.log1p(pocet_kusov)
input_df['d'] = d; input_df['l'] = l
input_df['plocha_prierezu'] = plocha_prierezu; input_df['plocha_plasta'] = plocha_plasta
for pref, val in {'material': material, 'akost': akost, 'narocnost': narocnost}.items():
    c_n = f"{pref}_{val}"
    if c_n in input_df.columns: input_df[c_n] = 1
log_p1 = m1.predict(input_df)[0]
cas = np.expm1(log_p1)

# Model 2 (Cena)
with open('MECASYS_APP/model_columns.pkl', 'rb') as f: m2_cols = pickle.load(f)
m2 = XGBRegressor(); m2.load_model('MECASYS_APP/xgb_model_cena.json')
input_m2 = pd.DataFrame(0, index=[0], columns=m2_cols)
input_m2['cas'] = cas; input_m2['hmotnost'] = hmotnost
input_m2['plocha_prierezu'] = plocha_prierezu; input_m2['hustota'] = hustota
if f"krajina_{krajina}" in input_m2.columns: input_m2[f"krajina_{krajina}"] = 1
log_p2 = m2.predict(input_m2)[0]
predikovana_cena_m2 = np.expm1(log_p2)

# --- POROVNANIE A VÝSLEDOK ---
finalna_cena_na_zapis = predikovana_cena_m2
if vstupne_naklady > predikovana_cena_m2:
    st.error(f"⚠️ NÁKLADY ({vstupne_naklady:.2f} €) > PREDIKCIA ({predikovana_cena_m2:.2f} €)!")
    finalna_cena_na_zapis = st.number_input("RUČNÁ PREDAJNÁ CENA [EUR]:", min_value=0.0, format="%.2f")
else:
    st.success("✅ Model M2 je v poriadku.")

st.metric("VÝSLEDNÁ CENA", f"{finalna_cena_na_zapis:.2f} EUR")

st.divider()
st.button("➕ Pridať výpočet do ponuky", on_click=pridat_polozku)

# --- ZOBRAZENIE KOŠÍKA ---
if st.session_state.polozky_ponuky:
    st.table(pd.DataFrame(st.session_state.polozky_ponuky))
    
    celkova_suma = 0.0
    for p in st.session_state.polozky_ponuky:
        try:
            h = str(p['Spolu']).replace('EUR', '').replace(',', '.').strip()
            celkova_suma += float(h)
        except: pass
    
    st.metric("CELKOVÁ CENA PONUKY", f"{celkova_suma:.2f} EUR")

    if st.button("🗑️ Vymazať celú ponuku"):
        st.session_state.polozky_ponuky = []
        st.rerun()

    # --- EXPORT DO GOOGLE SHEET ---
    if st.button("🚀 Zapísať do Google Sheet"):
        url_script = "https://script.google.com/macros/s/AKfycbwjChtJjHiZZyU8nVVpHKhcRj2z77pqrJNTw6rDm9dy_WzFaX6Yj0zzbmCSeHU7r8UUyA/exec"
        data_sheet = {"items": []}
        c_cp = "CP-" + datetime.datetime.now().strftime("%Y%m%d-%H%M")
        
        for p in st.session_state.polozky_ponuky:
            data_sheet["items"].append({
                "datum": date.today().strftime("%d.%m.%Y"),
                "cislo_cp": c_cp,
                "zakaznik": zakaznik,
                "krajina": krajina,
                "material": p["Materiál"],
                "akost": p["Akosť"],
                "cena_spolu": float(str(p["Spolu"]).replace(' EUR', '').replace(',', '.'))
            })
        res = requests.post(url_script, json=data_sheet)
        if res.status_code == 200: st.success("Zapísané!")

    # --- PDF GENERÁTOR ---
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"CENOVA PONUKA: {ponuka}", ln=True)
    
    widths = [80, 30, 35, 35, 35, 20, 40]
    headers = ["Polozka", "Cas", "Mat/ks", "Koop/ks", "Cena/ks", "Ks", "Spolu"]
    pdf.set_font("Helvetica", "B", 9)
    for i, head in enumerate(headers): pdf.cell(widths[i], 8, head, border=1, align='C')
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for p in st.session_state.polozky_ponuky:
        pdf.cell(widths[0], 8, f"{p['identifikator_polozky']} ({p['Rozmer (d x l)']})", border=1)
        pdf.cell(widths[1], 8, p['Čas (M1)'], border=1, align='C')
        pdf.cell(widths[2], 8, f"{p['mat_na_kus']:.2f} EUR", border=1, align='R')
        pdf.cell(widths[3], 8, f"{p['koop_na_kus']:.2f} EUR", border=1, align='R')
        pdf.cell(widths[4], 8, p['Cena/ks (M2)'], border=1, align='R')
        pdf.cell(widths[5], 8, str(p['Kusov']), border=1, align='C')
        pdf.cell(widths[6], 8, p['Spolu'], border=1, align='R')
        pdf.ln()

    pdf_out = pdf.output(dest='S').encode('latin-1')
    st.download_button("📥 Stiahnuť PDF", data=pdf_out, file_name=f"Ponuka_{ponuka}.pdf")
