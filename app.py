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
