import streamlit as st
import pandas as pd
from datetime import date

st.title("Moja postupná aplikácia")

# 1. Načítanie dát z Google Sheets
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"

@st.cache_data
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"Nepodarilo sa načítať dáta: {e}")
        return pd.DataFrame(columns=['zakaznik', 'krajina', 'lojalita'])

df = load_data()

# --- SEKCIU VSTUPOV (IDENTIFIKÁCIA) ---
st.subheader("1. Identifikácia ponuky")
col_a, col_b = st.columns(2)

with col_a:
    datum = st.date_input("Dátum vystavenia ponuky", value=date.today())
    ponuka = st.text_input("Označenie cenovej ponuky", placeholder="napr. CP-2024-001")

with col_b:
    item = st.text_input("Označenie komponentu (Item)", placeholder="napr. Motor X-100")

st.divider()

# --- SEKCIU VSTUPOV (ZÁKAZNÍK) ---
st.subheader("2. Detaily zákazníka")

moznosti_zakaznikov = ["--- Vyber zo zoznamu ---", "Nový zákazník (zadať manuálne)"] + sorted(df['zakaznik'].unique().tolist())
vyber = st.selectbox("Zákazník", moznosti_zakaznikov)

# Logika priraďovania hodnôt
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

# ZOBRAZENIE LOJALITY A KRAJINY (vždy, keď je vybraný zákazník)
if vyber != "--- Vyber zo zoznamu ---":
    c1, c2 = st.columns(2)
    c1.info(f"**Lokalita:** {krajina}")
    c2.info(f"**Lojalita (koeficient):** {lojalita}")

st.divider()

# --- SEKCIU VSTUPOV (VÝROBA) ---
st.subheader("3. Parametre výroby")
pocet_kusov = st.number_input("Počet kusov na výrobu", min_value=1, value=1, step=1)

# --- FINÁLNY SÚHRN ---
if zakaznik and ponuka and item:
    st.success("Všetky polia sú pripravené!")
    with st.expander("Pozrieť detailné zhrnutie"):
        st.write(f"**Ponuka:** {ponuka}")
        st.write(f"**Dátum:** {datum}")
        st.write(f"**Položka:** {item}")
        st.write(f"**Zákazník:** {zakaznik} ({krajina})")
        st.write(f"**Množstvo:** {pocet_kusov} ks")
        st.write(f"**Koeficient lojality:** {lojalita}")
