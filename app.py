import streamlit as st
import pandas as pd
from datetime import date
import re
# 1. premenná - dátum
datum = st.date_input("Dátum", value=date.today())

# 2. premenná - ponuka
ponuka = st.text_input("Číslo ponuky")

# 3. premenná - item
item = st.text_input("Identifikátor položky")

# 4. premenná - pocet_kusov
pocet_kusov = st.number_input("Počet kusov", min_value=1, step=1, format="%d")

# 5. premenná - narocnost
narocnost = st.selectbox("Náročnosť", options=["1", "2", "3", "4", "5"])

# 6. premenná - d
d = st.number_input("Priemer komponentu [mm]", min_value=0.0, step=0.1, format="%.2f")

# 7. premenná - l
l = st.number_input("Dĺžka komponentu [mm]", min_value=0.0, step=0.1, format="%.2f")

# --- SPRÁVNE NAČÍTANIE SHEETU ---
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

@st.cache_data
def load_data(url):
    # Načítame CSV
    data = pd.read_csv(url)
    # Očistíme názvy stĺpcov od medzier (napr. z "hustota " urobí "hustota")
    data.columns = data.columns.str.strip()
    # Očistíme textové hodnoty v stĺpcoch material a akost
    for col in ['material', 'akost']:
        data[col] = data[col].astype(str).str.strip()
    return data

df_materialy = load_data(sheet_url)

# 8. PREMENNÁ - Materiál
seznam_materialov = sorted(df_materialy['material'].unique())
material = st.selectbox("Materiál", options=seznam_materialov)

# 9. PREMENNÁ - Akosť
# K zoznamu zo sheetu pridáme na koniec možnosť "Iná akosť (zadať ručne)"
seznam_akosti = list(sorted(df_materialy[df_materialy['material'] == material]['akost'].unique()))
seznam_akosti.append("Iná akosť (zadať ručne)")

akost_vyber = st.selectbox("Akosť", options=seznam_akosti)

# Ak užívateľ zvolí ručné zadanie, otvorí sa textové pole
if akost_vyber == "Iná akosť (zadať ručne)":
    akost = st.text_input("Zadajte názov novej akosti:")
    if not akost:
        st.warning("Prosím, zadajte názov akosti.")
        st.stop()
else:
    akost = akost_vyber

# 10. PREMENNÁ - HUSTOTA
hustota = 0.0

# Logika hľadania v sheete beží len vtedy, ak nebolo zvolené ručné zadanie akosti
if akost_vyber != "Iná akosť (zadať ručne)":
    if material == "PLAST":
        vyber = df_materialy[(df_materialy['material'] == material) & (df_materialy['akost'] == akost)]
        if not vyber.empty:
            raw_val = str(vyber['hustota'].values[0]).strip()
            temp_val = raw_val.replace(',', '')
            clean_val = re.sub(r'[^0-9.]', '', temp_val)
            try:
                hustota = float(clean_val)
            except ValueError:
                hustota = 0.0
                
    elif material == "NEREZ":
        hustota = 8000.0
    elif material == "OCEĽ":
        hustota = 7900.0
    elif material == "FAREBNÉ KOVY":
        if akost.startswith("3.7"): hustota = 4500.0
        elif akost.startswith("3."): hustota = 2900.0
        elif akost.startswith("2."): hustota = 9000.0

# Ak je akosť nová (ručne zadaná) alebo sa v sheete nenašla hustota (hustota je 0)
if hustota <= 0:
    hustota = st.number_input("Hustota nenájdená. Zadajte manuálne [kg/m3]:", min_value=0.0, format="%.2f")
else:
    hustota = st.number_input("Hustota materiálu [kg/m3]:", value=hustota, format="%.2f")

# Validácia
if hustota <= 0:
    st.warning("Pre pokračovanie je potrebné určiť hustotu materiálu.")
    st.stop()
