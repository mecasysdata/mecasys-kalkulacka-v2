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
    except Exception as e:
        return pd.DataFrame(columns=['zakaznik', 'krajina', 'lojalita'])

df = load_data()

# --- 1. IDENTIFIKÁCIA PONUKY ---
st.subheader("1. Identifikácia ponuky")
col_a, col_b = st.columns(2)
with col_a:
    datum = st.date_input("Dátum vystavenia ponuky", value=date.today())
    ponuka = st.text_input("Označenie cenovej ponuky", placeholder="napr. CP-2024-001")
with col_b:
    item = st.text_input("Označenie komponentu (Item)", placeholder="napr. Hriadeľ")

st.divider()

# --- 2. DETAILY ZÁKAZNÍKA ---
st.subheader("2. Detaily zákazníka")
moznosti_zakaznikov = ["--- Vyber zo zoznamu ---", "Nový zákazník (zadať manuálne)"] + sorted(df['zakaznik'].unique().tolist())
vyber = st.selectbox("Zákazník", moznosti_zakaznikov)

if vyber == "Nový zákazník (zadať manuálne)":
    zakaznik = st.text_input("Meno nového zákazníka")
    krajina = st.text_input("Krajina")
    lojalita = 0.5
elif vyber != "--- Vyber zo zoznamu ---":
    data_zakaznika = df[df['zakaznik'] == vyber].iloc[0]
    zakaznik = vyber
    krajina = str(data_zakaznika['krajina'])
    lojalita = float(data_zakaznika['lojalita'])
else:
    zakaznik, krajina, lojalita = "", "", 0.0

if vyber != "--- Vyber zo zoznamu ---":
    c1, c2 = st.columns(2)
    c1.info(f"**Lokalita:** {krajina}")
    c2.info(f"**Lojalita (koeficient):** {lojalita}")

st.divider()

# --- 3. TECHNICKÉ PARAMETRE ---
st.subheader("3. Technické parametre komponentu")
col_d, col_l = st.columns(2)

with col_d:
    d = st.number_input("Priemer komponentu (d) [mm]", min_value=0.0, value=0.0, step=0.1, format="%.2f")

with col_l:
    l = st.number_input("Dĺžka komponentu (l) [mm]", min_value=0.0, value=0.0, step=0.1, format="%.2f")

# NOVÁ PREMENNÁ - narocnost (kategorická, uložená ako string)
narocnost = st.select_slider(
    "Náročnosť výroby (1 - najnižšia, 5 - najvyššia)",
    options=["1", "2", "3", "4", "5"],
    value="3"
)

st.divider()

# --- 4. PARAMETRE VÝROBY ---
st.subheader("4. Parametre výroby")
pocet_kusov = st.number_input("Počet kusov na výrobu", min_value=1, value=1, step=1)

# --- SÚHRN ---
if zakaznik and ponuka and item:
    with st.expander("Pozrieť detailné zhrnutie"):
        st.write(f"**Zákazník:** {zakaznik}")
        st.write(f"**Item:** {item} (d={d}mm, l={l}mm)")
        st.write(f"**Náročnosť:** {narocnost}")
        st.write(f"**Množstvo:** {pocet_kusov} ks")
