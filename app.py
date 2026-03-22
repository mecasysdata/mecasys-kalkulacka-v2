import streamlit as st
import pandas as pd
from datetime import date

# --- 1. NAČÍTANIE DÁT ---
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

st.title("Konfigurátor vstupov")

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
list_zakaznikov = ["--- Vyber ---", "Nový zákazník (manuálne)"] + sorted(df_zakaznici['zakaznik'].unique().tolist()) if not df_zakaznici.empty else ["Nový zákazník (manuálne)"]
vyber_z = st.selectbox("Vyber zákazníka", list_zakaznikov)

# Premenné zákazníka
if vyber_z == "Nový zákazník (manuálne)":
    zakaznik = st.text_input("Meno nového zákazníka")
    krajina = st.text_input("Krajina")
    lojalita = 0.5
elif vyber_z != "--- Vyber ---":
    data_z = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
    zakaznik = vyber_z
    krajina = str(data_z['krajina'])
    lojalita = float(data_z['lojalita'])
    st.info(f"Krajina: {krajina} | Lojalita: {lojalita}")
else:
    zakaznik, krajina, lojalita = "", "", 0.0

st.divider()

# --- 4. MATERIÁL A HUSTOTA ---
st.subheader("3. Výber materiálu")
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    list_mat = sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else []
    material = st.selectbox("Materiál", list_mat)

with col_m2:
    df_f = df_mat[df_mat['material'] == material]
    list_ako = sorted(df_f['akost'].unique().tolist())
    akost = st.selectbox("Akosť", list_ako)

# Logika hustoty (vstupy)
hustota = 0.0
if material == "NEREZ": hustota = 8000.0
elif material == "OCEĽ": hustota = 7900.0
elif material == "PLAST":
    try: hustota = float(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
    except: hustota = 0.0
elif material == "FAREBNÉ KOVY":
    a_str = str(akost)
    if a_str.startswith("3.7"): hustota = 4500.0
    elif a_str.startswith("3."): hustota = 2900.0
    elif a_str.startswith("2."): hustota = 9000.0

with col_m3:
    st.metric("Hustota", f"{hustota}")

st.divider()

# --- 5. TECHNICKÉ PARAMETRE ---
st.subheader("4. Rozmery a náročnosť")
col_p1, col_p2, col_p3 = st.columns(3)

with col_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.0, step=0.1, format="%.2f")
with col_p2:
    l = st.number_input("Dĺžka l [mm]", min_value=0.0, step=0.1, format="%.2f")
with col_p3:
    narocnost = st.select_slider("Náročnosť", options=["1", "2", "3", "4", "5"], value="3")

pocet_kusov = st.number_input("Počet kusov", min_value=1, step=1)

# --- SÚHRN VSTUPOV ---
st.divider()
st.subheader("Kontrola zadaných vstupov")
prehlad = {
    "Premenná": ["Dátum", "Ponuka", "Item", "Zákazník", "Krajina", "Lojalita", "Materiál", "Akosť", "Hustota", "Priemer d", "Dĺžka l", "Náročnosť", "Počet kusov"],
    "Hodnota": [datum, ponuka, item, zakaznik, krajina, lojalita, material, akost, hustota, d, l, narocnost, pocet_kusov]
}
st.table(pd.DataFrame(prehlad))
