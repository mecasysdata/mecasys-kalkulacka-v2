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

# Načítanie dát z Google Sheets pre premenné 8 a 9
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"
df_materialy = pd.read_csv(sheet_url)

# 8. premenná - material
seznam_materialov = df_materialy['material'].unique()
material = st.selectbox("Materiál", options=seznam_materialov)

# 9. premenná - akost (filtrovaná podľa zvoleného materiálu)
seznam_akosti = df_materialy[df_materialy['material'] == material]['akost'].unique()
akost = st.selectbox("Akosť", options=seznam_akosti)

# 10. premenná - hustota
if material == "PLAST":
    # Vytiahne hodnotu 'hustota' z riadku, kde sa zhoduje materiál aj akosť
    hustota_val = df_materialy[(df_materialy['material'] == "PLAST") & (df_materialy['akost'] == akost)]['hustota'].values[0]
    hustota = float(hustota_val)
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
    else:
        hustota = 0.0 # Definujeme základnú hodnotu, ak by akosť nespadala do podmienok
else:
    hustota = 0.0

# Zobrazenie premennej (voliteľné pre kontrolu, alebo ju môžeme nechať len v pamäti)
st.write(f"Vypočítaná hustota: {hustota}")
