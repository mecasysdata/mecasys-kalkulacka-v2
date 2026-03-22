import streamlit as st
import pandas as pd
import math
from datetime import date

# --- 1. NAČÍTANIE DÁT ---
# Adresy na tvoje Google Sheets (CSV export)
SHEET_ZAKAZNICI = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"
SHEET_MATERIALY = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        # Odstránenie prípadných medzier v názvoch stĺpcov
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

df_zakaznici = load_data(SHEET_ZAKAZNICI)
df_mat = load_data(SHEET_MATERIALY)

st.title("Kalkulačná aplikácia")

# --- 2. IDENTIFIKÁCIA PONUKY ---
st.subheader("1. Základné informácie")
col_id1, col_id2, col_id3 = st.columns(3)

with col_id1:
    datum = st.date_input("Dátum vystavenia", value=date.today())
with col_id2:
    ponuka = st.text_input("Označenie ponuky", placeholder="napr. CP-2026-001")
with col_id3:
    item = st.text_input("Názov komponentu (Item)", placeholder="napr. Hriadeľ X1")

st.divider()

# --- 3. ZÁKAZNÍK ---
st.subheader("2. Detaily zákazníka")
list_zakaznikov = ["--- Vyber zo zoznamu ---", "Nový zákazník (zadať manuálne)"]
if not df_zakaznici.empty:
    list_zakaznikov += sorted(df_zakaznici['zakaznik'].dropna().unique().tolist())

vyber_z = st.selectbox("Zákazník", list_zakaznikov)

# Inicializácia premenných
zakaznik, krajina, lojalita = "", "", 0.0

if vyber_z == "Nový zákazník (zadať manuálne)":
    zakaznik = st.text_input("Meno nového zákazníka")
    krajina = st.text_input("Krajina")
    lojalita = 0.5
elif vyber_z != "--- Vyber zo zoznamu ---":
    data_z = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
    zakaznik = vyber_z
    krajina = str(data_z['krajina'])
    lojalita = float(data_z['lojalita'])
    
    c1, c2 = st.columns(2)
    c1.info(f"**Lokalita:** {krajina}")
    c2.info(f"**Lojalita:** {lojalita}")

st.divider()

# --- 4. MATERIÁL A HUSTOTA ---
st.subheader("3. Materiálové parametre")
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    list_mat = sorted(df_mat['material'].dropna().unique().tolist()) if not df_mat.empty else []
    material = st.selectbox("Materiál", list_mat)

with col_m2:
    df_f = df_mat[df_mat['material'] == material]
    list_ako = sorted(df_f['akost'].dropna().unique().tolist())
    akost = st.selectbox("Akosť", list_ako)

# --- LOGIKA VÝPOČTU HUSTOTY (OPRAVENÝ PLAST) ---
hustota = 0.0

if material == "NEREZ":
    hustota = 8000.0
elif material == "OCEĽ":
    hustota = 7900.0
elif material == "PLAST":
    try:
        val = df_f[df_f['akost'] == akost]['hustota'].iloc[0]
        # Ak je hodnota text (napr. "1,500.00"), vyčistíme ju pre float
        if isinstance(val, str):
            val = val.replace(',', '').strip()
        hustota = float(val)
    except:
        hustota = 0.0
elif material == "FAREBNÉ KOVY":
    a_str = str(akost)
    if a_str.startswith("3.7"):
        hustota = 4500.0
    elif a_str.startswith("3."):
        hustota = 2900.0
    elif a_str.startswith("2."):
        hustota = 9000.0

with col_m3:
    st.metric("Hustota (kg/m³)", f"{hustota}")

st.divider()

# --- 5. TECHNICKÉ PARAMETRE ---
st.subheader("4. Rozmery a náročnosť")
col_p1, col_p2, col_p3 = st.columns(3)

with col_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.0, step=0.1, format="%.2f")
with col_p2:
    l = st.number_input("Dĺžka l [mm]", min_value=0.0, step=0.1, format="%.2f")
with col_p3:
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, step=1, value=1)

# --- 6. KONTROLNÝ SÚHRN ---
st.divider()
if st.checkbox("Zobraziť súhrnnú tabuľku vstupov"):
    prehlad = {
        "Premenná": ["Dátum", "Ponuka", "Item", "Zákazník", "Krajina", "Lojalita", "Materiál", "Akosť", "Hustota", "Priemer d", "Dĺžka l", "Náročnosť", "Počet kusov"],
        "Hodnota": [datum, ponuka, item, zakaznik, krajina, lojalita, material, akost, hustota, d, l, narocnost, pocet_kusov]
    }
    st.table(pd.DataFrame(prehlad))
