import streamlit as st
import pandas as pd

st.title("Moja postupná aplikácia")

# 1. Načítanie dát
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"

@st.cache_data
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except:
        # Záložný prázdny DataFrame, ak by link nefungoval
        return pd.DataFrame(columns=['zakaznik', 'krajina', 'lojalita'])

df = load_data()

# Príprava zoznamu pre selectbox (existujúci + možnosť pridať nového)
moznosti_zakaznikov = ["--- Vyber zo zoznamu ---", "Nový zákazník (zadať manuálne)"] + sorted(df['zakaznik'].unique().tolist())

# --- SEKCIU VSTUPOV ---

vyber = st.selectbox("Vyberte zákazníka", moznosti_zakaznikov)

# Logika pre existujúceho vs. nového zákazníka
if vyber == "Nový zákazník (zadať manuálne)":
    zakaznik = st.text_input("Zadajte názov nového zákazníka")
    krajina = st.text_input("Zadajte krajinu zákazníka")
    lojalita = 0.5
    st.info(f"Nový zákazník má automaticky nastavenú lojalitu na {lojalita}")

elif vyber != "--- Vyber zo zoznamu ---":
    # Načítanie dát z tabuľky
    data_zakaznika = df[df['zakaznik'] == vyber].iloc[0]
    zakaznik = vyber
    krajina = str(data_zakaznika['krajina'])
    lojalita = float(data_zakaznika['lojalita'])
else:
    # Ak ešte nič nevybral
    zakaznik = ""
    krajina = ""
    lojalita = 0.0

# 4. Počet kusov (vždy zobrazený)
pocet_kusov = st.number_input("Počet kusov na výrobu", min_value=1, value=10, step=1)

# --- ZOBRAZENIE VÝSLEDKOV ---
if zakaznik:
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Zákazník:** {zakaznik}")
        st.write(f"**Krajina:** {krajina}")
    with col2:
        st.write(f"**Lojalita:** {lojalita}")
        st.write(f"**Plánovaná výroba:** {pocet_kusov} ks")
