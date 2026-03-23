import streamlit as st
import pandas as pd
from datetime import date

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

# UPRAVENÉ NAČÍTANIE: Pridávame decimal a thousands, aby Pandas hneď spravil z hustoty číslo
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"
df_materialy = pd.read_csv(sheet_url, decimal=',', thousands='\xa0') 
# Poznámka: \xa0 je kód pre nezlomiteľnú medzeru, ktorú Google Sheets používa

# 8. premenná - material
seznam_materialov = df_materialy['material'].unique()
material = st.selectbox("Materiál", options=seznam_materialov)

# 9. premenná - akost (filtrovaná podľa zvoleného materiálu)
seznam_akosti = df_materialy[df_materialy['material'] == material]['akost'].unique()
akost = st.selectbox("Akosť", options=seznam_akosti)

# 10. premenná - hustota 
hustota = 0.0

if material == "PLAST":
    try:
        raw_hustota = df_materialy[(df_materialy['material'] == "PLAST") & (df_materialy['akost'] == akost)]['hustota'].values[0]
        clean_hustota = str(raw_hustota).replace(',', '.').replace('\xa0', '').replace(' ', '')
        hustota = float(clean_hustota)
    except (IndexError, ValueError):
        hustota = 0.0
elif material == "NEREZ":
    hustota = 8000.0
elif material == "OCEĽ":
    hustota = 7900.0
elif material == "FAREBNÉ KOVY":
    if akost.startswith("3.7"):
        hustota = 4500.0
    elif akost.startswith("3."):
        hustota = 2900.0
    elif akost.startswith("2."):
        hustota = 9000.0

# Ak je hustota stále 0 (nenájdená), užívateľ ju zadá ručne
if hustota <= 0:
    hustota = st.number_input("Hustota nebola nájdená. Zadajte ju ručne [kg/m3]", min_value=0.0, step=10.0, format="%.2f")

# Finálna kontrola pred pokračovaním
if hustota <= 0:
    st.warning("Pre pokračovanie je potrebné zadať platnú hustotu materiálu.")
    st.stop()
else:
    st.success(f"Použitá hustota: {hustota} kg/m3")
