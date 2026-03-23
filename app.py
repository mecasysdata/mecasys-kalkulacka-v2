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
seznam_akosti = sorted(df_materialy[df_materialy['material'] == material]['akost'].unique())
akost = st.selectbox("Akosť", options=seznam_akosti)

# 10. PREMENNÁ - HUSTOTA (opravená pre formát 1,500.00)
hustota = 0.0

if material == "PLAST":
    vyber = df_materialy[(df_materialy['material'] == material) & (df_materialy['akost'] == akost)]
    if not vyber.empty:
        # Získame hodnotu a preistotu ju zbavíme všetkých bielych znakov (medzier)
        raw_val = str(vyber['hustota'].values[0]).strip()
        
        # 1. Odstránime čiarku (oddeľovač tisícov)
        temp_val = raw_val.replace(',', '')
        
        # 2. Ponecháme len číslice a bodku (desatinnú)
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

# ZOBRAZENIE / RUČNÉ ZADANIE
if hustota <= 0:
    hustota = st.number_input("Hustota nenájdená. Zadajte manuálne [kg/m3]:", min_value=0.0, format="%.2f")
else:
    # Ak sa našla, urobíme ju editovateľnú (užívateľ ju vidí a môže zmeniť)
    hustota = st.number_input("Hustota materiálu [kg/m3]:", value=hustota, format="%.2f")

# Validácia pred pokračovaním
if hustota <= 0:
    st.warning("Pre pokračovanie je potrebné určiť hustotu materiálu.")
    st.stop()
