import streamlit as st
import pandas as pd
from datetime import date

# --- NAČÍTANIE DÁT ---
SHEET_ZAKAZNICI = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"
SHEET_MATERIALY = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

@st.cache_data
def load_data(url):
    try:
        return pd.read_csv(url)
    except:
        return pd.DataFrame()

df_zakaznici = load_data(SHEET_ZAKAZNICI)
df_mat = load_data(SHEET_MATERIALY)

st.title("Moja postupná aplikácia")

# ... (tu ostáva kód pre Identifikáciu a Zákazníka, ktorý sme už vytvorili) ...

st.divider()

# --- 5. VÝBER MATERIÁLU A AKOSTI ---
st.subheader("5. Materiálové parametre")

col_mat, col_ako = st.columns(2)

with col_mat:
    zoznam_materialov = sorted(df_mat['material'].unique().tolist())
    material = st.selectbox("Vyber materiál", zoznam_materialov)

with col_ako:
    # Filter akostí podľa vybraného materiálu
    df_filtrovane = df_mat[df_mat['material'] == material]
    zoznam_akosti = sorted(df_filtrovane['akost'].unique().tolist())
    akost = st.selectbox("Vyber akosť", zoznam_akosti)

# --- VÝPOČET HUSTOTY (tvoja logika) ---
hustota = 0.0

if material == "NEREZ":
    hustota = 8000.0
elif material == "OCEĽ":
    hustota = 7900.0
elif material == "PLAST":
    # Dotiahnutie zo stĺpca 'hustota' v sheete
    try:
        hustota = float(df_filtrovane[df_filtrovane['akost'] == akost]['hustota'].iloc[0])
    except:
        hustota = 0.0
elif material == "FAREBNÉ KOVY":
    akost_str = str(akost)
    if akost_str.startswith("3.7"):
        hustota = 4500.0
    elif akost_str.startswith("3."):
        hustota = 2900.0
    elif akost_str.startswith("2."):
        hustota = 9000.0

# --- ZOBRAZENIE HUSTOTY NA OBRAZOVKE ---
st.metric(label=f"Aktuálna hustota pre {material} ({akost})", value=f"{hustota} kg/m³")

# Ak je hustota 0, upozorníme užívateľa
if hustota == 0:
    st.warning("Pozor: Hustota pre túto kombináciu nebola nájdená alebo vypočítaná.")

st.divider()

# ... (nasleduje d, l, narocnost a pocet_kusov) ...
