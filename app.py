import streamlit as st
import pandas as pd

st.title("Moja postupná aplikácia")

# 1. Načítanie dát z Google Sheets (CSV link)
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"

@st.cache_data  # Cache zabezpečí, že dáta sa nebudú sťahovať pri každom kliknutí
def load_data():
    df = pd.read_csv(SHEET_URL)
    return df

df = load_data()

# 2. Premenná - zakaznik (Výber na obrazovke)
zakaznik = st.selectbox("Zákazník", df['zakaznik'].unique())

# 3. Vyhľadanie prislúchajúcich hodnôt (krajina a lojalita)
# Vyfiltrujeme riadok, kde sa meno zhoduje s výberom
data_zakaznika = df[df['zakaznik'] == zakaznik].iloc[0]

krajina = str(data_zakaznika['krajina'])
lojalita = float(data_zakaznika['lojalita'])

# Kontrolný výpis (môžeme neskôr odstrániť)
st.write(f"Zvolený zákazník: **{zakaznik}**")
st.write(f"Krajina: {krajina}")
st.write(f"Lojalita: {lojalita}")
