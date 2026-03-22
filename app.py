import streamlit as st
import pandas as pd

st.title("Moja postupná aplikácia")

# 1. Načítanie dát
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"

@st.cache_data
def load_data():
    df = pd.read_csv(SHEET_URL)
    return df

df = load_data()

# --- SEKCIU VSTUPOV ---

# 2. Premenná - zakaznik
zakaznik = st.selectbox("Zákazník", df['zakaznik'].unique())

# 3. Vyhľadanie hodnôt z tabuľky
data_zakaznika = df[df['zakaznik'] == zakaznik].iloc[0]
krajina = str(data_zakaznika['krajina'])
lojalita = float(data_zakaznika['lojalita'])

# 4. NOVÁ PREMENNÁ - pocet_kusov
# min_value=1 zabezpečí, že nevyrobíme 0 alebo záporný počet
pocet_kusov = st.number_input("Počet kusov na výrobu", min_value=1, value=10, step=1)

# --- ZOBRAZENIE VÝSLEDKOV ---

st.divider() # Pridá vodorovnú čiaru pre prehľadnosť

col1, col2 = st.columns(2)

with col1:
    st.write(f"**Zákazník:** {zakaznik}")
    st.write(f"**Krajina:** {krajina}")

with col2:
    st.write(f"**Lojalita:** {lojalita}")
    st.write(f"**Plánovaná výroba:** {pocet_kusov} ks")

# Overenie dátového typu pre teba:
# st.write(f"Dátový typ pocet_kusov: {type(pocet_kusov)}")
