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
        # TIETO RIADKY SÚ POTREBNÉ PRE PDF A EXPORT:
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

# --- HUSTOTA A GEOMETRIA ---
hustota = 0.0
if material == "PLAST":
    vyber = df_materialy[(df_materialy['material'] == material) & (df_materialy['akost'] == akost)]
    if not vyber.empty:
        raw_val = str(vyber['hustota'].values[0]).strip()
        temp_val = raw_val.replace(',', '')
        clean_val = re.sub(r'[^0-9.]', '', temp_val)
        try: hustota = float(clean_val)
        except: hustota = 0.0
elif material == "NEREZ": hustota = 8000.0
elif material == "OCEĽ": hustota = 7900.0
elif material == "FAREBNÉ KOVY":
    if akost.startswith("3.7"): hustota = 4500.0
    elif akost.startswith("3."): hustota = 2900.0
    elif akost.startswith("2."): hustota = 9000.0

if hustota <= 0:
    hustota = st.number_input("Hustota manuálne [kg/m3]:", min_value=0.0, format="%.2f")
else:
    hustota = st.number_input("Hustota materiálu [kg/m3]:", value=hustota, format="%.2f")

hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)
plocha_prierezu = (math.pi * d**2) / 4
plocha_prierez_dm2 = plocha_prierezu / 10000
plocha_plasta = math.pi * d * l

# --- ZÁKAZNÍK ---
sheet_zakaznici_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"
df_zakaznici = pd.read_csv(sheet_zakaznici_url)
seznam_zakaznikov = list(sorted(df_zakaznici['zakaznik'].unique()))
seznam_zakaznikov.append("Nový zákazník (zadať ručne)")
zakaznik_vyber = st.selectbox("Vyberte zákazníka", options=seznam_zakaznikov)

if zakaznik_vyber == "Nový zákazník (zadať ručne)":
    zakaznik = st.text_input("Meno nového zákazníka:")
    krajina = st.text_input("Krajina zákazníka:")
    lojalita = 0.5
else:
    zakaznik = zakaznik_vyber
    data_z = df_zakaznici[df_zakaznici['zakaznik'] == zakaznik].iloc[0]
    krajina = str(data_z['krajina'])
    lojalita = float(str(data_z['lojalita']).replace(',', '.'))

# --- CENA MATERIÁLU ---
sheet_cena_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv"
df_ceny = pd.read_csv(sheet_cena_url)
mask = (df_ceny['material'] == material) & (df_ceny['akost'] == akost)
vhodne = df_ceny[mask & (df_ceny['d'] >= d)].sort_values(by='d')
nalezena_cena = float(str(vhodne.iloc[0]['cena']).replace(',', '.')) if not vhodne.empty else 0.0

cena_za_meter = st.number_input("Cena materiálu [EUR/m]:", value=nalezena_cena, format="%.2f")
cena_material = cena_za_meter * (l / 1000)

# --- KOOPERÁCIA ---
sheet_koop_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv"
df_koop = pd.read_csv(sheet_koop_url)
je_kooperacia = st.checkbox("Vyžaduje diel kooperáciu?")
cena_kooperacia = 0.0

if je_kooperacia:
    vybrany_druh = st.selectbox("Druh kooperácie", options=df_koop['druh'].unique())
    riadok_k = df_koop[df_koop['druh'] == vybrany_druh].iloc[0]
    tarifa = float(riadok_k['tarifa'])
    jednotka = str(riadok_k['jednotka']).lower()
    vyp_cena = tarifa * hmotnost if jednotka == "kg" else tarifa * plocha_prierez_dm2
    cena_kooperacia = max(vyp_cena, float(riadok_k['minimum']) / pocet_kusov)

vstupne_naklady = cena_material + cena_kooperacia

# --- !!! ZÁKLADNÁ LOGIKA MODELOV (NEMENIŤ) !!! ---
# --- MODEL 1 (ČAS) ---
cas = 0.0
try:
    with open('MECASYS_APP/stlpce_modelu.pkl', 'rb') as f: model_columns = pickle.load(f)
    loaded_model = XGBRegressor(); loaded_model.load_model('MECASYS_APP/finalny_model.json')
    input_df = pd.DataFrame(0, index=[0], columns=model_columns)
    input_df['pocet_kusov'] = np.log1p(pocet_kusov)
    input_df['d'] = d; input_df['l'] = l
    input_df['plocha_prierezu'] = plocha_prierezu; input_df['plocha_plasta'] = plocha_plasta
    for prefix, value in {'material': material, 'akost': akost, 'narocnost': narocnost}.items():
        col_name = f"{prefix}_{value}"
        if col_name in input_df.columns: input_df[col_name] = 1
    log_predikcia = loaded_model.predict(input_df)[0]
    cas = np.expm1(log_predikcia)
except Exception as e:
    st.warning(f"Model 1 chyba: {e}")

# --- MODEL 2 (TRHOVÁ CENA) ---
predikovana_cena_m2 = 0.0
try:
    with open('MECASYS_APP/model_columns.pkl', 'rb') as f: m2_columns = pickle.load(f)
    model_m2 = XGBRegressor(); model_m2.load_model('MECASYS_APP/xgb_model_cena.json')
    input_m2 = pd.DataFrame(0, index=[0], columns=m2_columns)
    input_m2['cas'] = cas; input_m2['hmotnost'] = hmotnost
    input_m2['plocha_prierezu'] = plocha_prierezu; input_m2['hustota'] = hustota
    col_krajina = f"krajina_{krajina}"
    if col_krajina in input_m2.columns: input_m2[col_krajina] = 1
    log_pred_m2 = model_m2.predict(input_m2)[0]
    predikovana_cena_m2 = np.expm1(log_pred_m2)
except Exception as e:
    st.warning(f"Model 2 chyba: {e}")

# --- FINÁLNA CENA A KOŠÍK ---
finalna_cena_na_zapis = predikovana_cena_m2
if vstupne_naklady > predikovana_cena_m2:
    st.error(f"⚠️ NÁKLADY ({vstupne_naklady:.2f} €) > PREDIKCIA ({predikovana_cena_m2:.2f} €)!")
    finalna_cena_na_zapis = st.number_input("ZADAJTE RUČNE PREDAJNÚ CENU [EUR]:", min_value=0.0, format="%.2f")
else:
    st.success(f"✅ Model M2 je v poriadku.")

st.metric("VÝSLEDNÁ CENA", f"{finalna_cena_na_zapis:.2f} EUR")

st.divider()
st.button("➕ Pridať aktuálny výpočet do ponuky", on_click=pridat_polozku)

if st.session_state.polozky_ponuky:
    st.table(pd.DataFrame(st.session_state.polozky_ponuky))
    
    celkova_suma = 0.0
    for i in st.session_state.polozky_ponuky:
        try:
            h_str = str(i['Spolu']).replace('EUR', '').replace('€', '').replace(',', '.').strip()
            celkova_suma += float(h_str)
        except: pass
    
    st.metric("CELKOVÁ CENA PONUKY", f"{celkova_suma:.2f} EUR")

    if st.button("🗑️ Vymazať celú ponuku"):
        st.session_state.polozky_ponuky = []
        st.rerun()

    # --- PDF EXPORT (A4 Landscape) ---
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"CENOVA PONUKA: {ponuka}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Datum: {datetime.date.today().strftime('%d.%m.%Y')}", ln=True)
    pdf.ln(5)

    widths = [80, 30, 35, 35, 35, 20, 40]
    headers = ["Polozka (Nazov a Rozmer)", "Predik. cas", "Mat. / kus", "Koop. / kus", "Cena / kus", "Ks", "Spolu"]
    
    pdf.set_font("Helvetica", "B", 9)
    for idx, h in enumerate(headers):
        pdf.cell(widths[idx], 8, h, border=1, align='C')
    pdf.ln()

    def clean_pdf(txt):
        t = str(txt)
        reps = {'á':'a','é':'e','í':'i','ó':'o','ú':'u','ý':'y','č':'c','ď':'d','ľ':'l','ň':'n','š':'s','ť':'t','ž':'z','€':'','EUR':''}
        for k, v in reps.items(): t = t.replace(k, v)
        return t.strip()

    pdf.set_font("Helvetica", "", 9)
    for p in st.session_state.polozky_ponuky:
        n_item = f"{p['identifikator_polozky']} - {p['Materiál']} ({p['Rozmer (d x l)']})"
        pdf.cell(widths[0], 8, clean_pdf(n_item), border=1)
        pdf.cell(widths[1], 8, clean_pdf(p['Čas (M1)']), border=1, align='C')
        pdf.cell(widths[2], 8, f"{p.get('mat_na_kus', 0):.2f} EUR", border=1, align='R')
        pdf.cell(widths[3], 8, f"{p.get('koop_na_kus', 0):.2f} EUR", border=1, align='R')
        pdf.cell(widths[4], 8, clean_pdf(p['Cena/ks (M2)']), border=1, align='R')
        pdf.cell(widths[5], 8, str(p['Kusov']), border=1, align='C')
        pdf.cell(widths[6], 8, clean_pdf(p['Spolu']), border=1, align='R')
        pdf.ln()

    pdf.ln(5); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(sum(widths[:-1]), 10, "CELKOVA SUMA PONUKY (EUR):", 0, 0, 'R')
    pdf.cell(widths[-1], 10, f"{celkova_suma:.2f}", 1, 1, 'C')

    pdf_output = pdf.output(dest='S').encode('latin-1')
    st.download_button("📥 Stiahnuť ponuku v PDF", data=pdf_output, file_name=f"Ponuka_{ponuka}.pdf", mime="application/pdf")
