import streamlit as st
import pandas as pd
from datetime import date

st.title("Moja postupná aplikácia")

# 1. Načítanie dát
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"

@st.cache_data
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except:
        return pd.DataFrame(columns=['zakaznik', 'krajina', 'lojalita'])

df = load_data()

# --- SEKCIU VSTUPOV (ZÁKLADNÉ INFO) ---
st.subheader("Základné informácie o ponuke")

col_a, col_b = st.columns(2)

with col_a:
    # NOVÁ PREMENNÁ - datum (typ: date)
    datum = st.date_input("Dátum vystavenia ponuky", value=date.today())
    
    # NOVÁ PREMENNÁ - ponuka (typ: string)
    ponuka = st.text_input("Označenie cenovej ponuky (napr. CP-2024-001)")

with col_b:
    # NOVÁ PREMENNÁ - item (typ: string)
    item = st.text_input("Označenie komponentu (Item)")

st.divider()

# --- SEKCIU VSTUPOV (ZÁKAZNÍK A MNOŽSTVO) ---
st.subheader("Detaily zákazníka a výroby")

moznosti_zakaznikov = ["--- Vyber zo zoznamu ---", "Nový zákazník (zadať manuálne)"] + sorted(df['zakaznik'].unique().tolist())
vyber = st.selectbox("Vyberte zákazníka", moznosti_zakaznikov)

if vyber == "Nový zákazník (zadať manuálne)":
    zakaznik = st.text_input("Zadajte názov nového zákazníka")
    krajina = st.text_input("Zadajte krajinu zákazníka")
    lojalita = 0.5
elif vyber != "--- Vyber zo zoznamu ---":
    data_zakaznika = df[df['zakaznik'] == vyber].iloc[0]
    zakaznik = vyber
    krajina = str(data_zakaznika['krajina'])
    lojalita = float(data_zakaznika['lojalita'])
else:
    zakaznik, krajina, lojalita = "", "", 0.0

pocet_kusov = st.number_input("Počet kusov na výrobu", min_value=1, value=10, step=1)

# --- ZOBRAZENIE ZHRNUTIA ---
if zakaznik and ponuka and item:
    st.success("Všetky potrebné údaje sú vyplnené.")
    st.write("### Súhrn ponuky:")
    
    info_col1, info_col2, info_col3 = st.columns(3)
    info_col1.metric("Ponuka", ponuka)
    info_col2.metric("Dátum", str(datum))
    info_col3.metric("Item", item)
    
    st.write(f"**Zákazník:** {zakaznik} ({krajina}) | **Lojalita:** {lojalita} | **Množstvo:** {pocet_kusov} ks")
