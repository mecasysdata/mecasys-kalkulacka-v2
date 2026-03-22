import streamlit as st
import pandas as pd
import math
from datetime import date

# --- 1. NAČÍTANIE DÁT Z GOOGLE SHEETS ---
SHEET_ZAKAZNICI = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"
SHEET_MATERIALY = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

df_zakaznici = load_data(SHEET_ZAKAZNICI)
df_mat = load_data(SHEET_MATERIALY)

# --- NASTAVENIE STRÁNKY ---
st.set_page_config(page_title="Kalkulačná aplikácia", layout="wide")
st.title("⚙️ Komplexný systém vstupov")

# --- 2. SEKCIU: IDENTIFIKÁCIA ---
st.subheader("1. Základné informácie")
col_id1, col_id2, col_id3 = st.columns(3)
with col_id1:
    datum = st.date_input("Dátum vystavenia", value=date.today())
with col_id2:
    ponuka = st.text_input("Označenie ponuky", placeholder="napr. CP-2026-001")
with col_id3:
    item = st.text_input("Názov komponentu (Item)", placeholder="napr. Hriadeľ")

st.divider()

# --- 3. SEKCIU: ZÁKAZNÍK (Logika krajina a lojalita) ---
st.subheader("2. Detaily zákazníka")
list_zakaznikov = ["--- Vyber zo zoznamu ---", "Nový zákazník (zadať manuálne)"]
if not df_zakaznici.empty:
    list_zakaznikov += sorted(df_zakaznici['zakaznik'].dropna().unique().tolist())

vyber_z = st.selectbox("Zákazník", list_zakaznikov)

zakaznik, krajina, lojalita = "", "", 0.0

if vyber_z == "Nový zákazník (zadať manuálne)":
    zakaznik = st.text_input("Meno nového zákazníka")
    krajina = st.text_input("Krajina")
    lojalita = 0.5
    st.info(f"Nový zákazník má predvolenú lojalitu: {lojalita}")
elif vyber_z != "--- Vyber zo zoznamu ---":
    data_z = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
    zakaznik = vyber_z
    krajina = str(data_z['krajina'])
    lojalita = float(data_z['lojalita'])
    
    c_z1, c_z2 = st.columns(2)
    c_z1.info(f"**Lokalita:** {krajina}")
    c_z2.info(f"**Lojalita:** {lojalita}")

st.divider()

# --- 4. SEKCIU: MATERIÁL (Logika hustoty a akosti + manuálny vstup) ---
st.subheader("3. Materiálové parametre")
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    list_mat = sorted(df_mat['material'].dropna().unique().tolist()) if not df_mat.empty else []
    material = st.selectbox("Materiál", list_mat)

with col_m2:
    df_f = df_mat[df_mat['material'] == material]
    # Pridáme možnosť "Iná akosť" do zoznamu
    list_ako = sorted(df_f['akost'].dropna().unique().tolist()) + ["Iná akosť (zadať manuálne)"]
    vyber_ako = st.selectbox("Akosť", list_ako)

# Inicializácia premenných pre akosť a hustotu
akost = ""
hustota = 0.0

if vyber_ako == "Iná akosť (zadať manuálne)":
    akost = st.text_input("Názov novej akosti", placeholder="napr. S355 J2")
    hustota = st.number_input("Hustota novej akosti [kg/m³]", min_value=0.0, step=1.0, value=0.0)
else:
    akost = vyber_ako
    # Štandardná logika výpočtu hustoty
    if material == "NEREZ":
        hustota = 8000.0
    elif material == "OCEĽ":
        hustota = 7900.0
    elif material == "PLAST":
        try:
            val = df_f[df_f['akost'] == akost]['hustota'].iloc[0]
            if isinstance(val, str): val = val.replace(',', '').strip()
            hustota = float(val)
        except:
            hustota = 0.0
    elif material == "FAREBNÉ KOVY":
        a_str = str(akost)
        if a_str.startswith("3.7"): hustota = 4500.0
        elif a_str.startswith("3."): hustota = 2900.0
        elif a_str.startswith("2."): hustota = 9000.0

with col_m3:
    st.metric("Hustota (kg/m³)", f"{hustota}")

st.divider()

# --- 5. SEKCIU: TECHNICKÉ PARAMETRE ---
st.subheader("4. Rozmery a náročnosť")
col_p1, col_p2, col_p3 = st.columns(3)

with col_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.0, step=0.1, format="%.2f")
with col_p2:
    l = st.number_input("Dĺžka l [mm]", min_value=0.0, step=0.1, format="%.2f")
with col_p3:
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, step=1, value=1)

# --- 6. SEKCIU: TECHNICKÉ VÝPOČTY (Presne podľa tvojich modelov) ---
# 1. Plocha prierezu (z Modelu 1)
plocha_prierezu = (math.pi * (d**2)) / 4

# 2. Plocha plášťa (z Modelu 1)
plocha_plasta = math.pi * d * l

# 3. Hmotnosť v kg (z Modelu 2)
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

st.divider()
st.subheader("5. Vypočítané technické parametre")
res1, res2, res3 = st.columns(3)
res1.metric("Plocha prierezu", f"{plocha_prierezu:.2f} mm²")
res2.metric("Plocha plášťa", f"{plocha_plasta:.2f} mm²")
res3.metric("Hmotnosť 1 kusu", f"{hmotnost:.3f} kg")

# --- 7. KONTROLNÝ SÚHRN ---
st.divider()
if st.checkbox("Zobraziť súhrnnú tabuľku všetkých premenných"):
    prehlad_dat = {
        "Premenná": [
            "Dátum", "Ponuka", "Item", "Zákazník", "Krajina", 
            "Lojalita", "Materiál", "Akosť", "Hustota", 
            "Priemer (d)", "Dĺžka (l)", "Náročnosť", "Počet kusov",
            "Plocha prierezu", "Plocha plášťa", "Hmotnosť (kg)"
        ],
        "Hodnota": [
            datum, ponuka, item, zakaznik, krajina, 
            lojalita, material, akost, hustota, 
            d, l, narocnost, pocet_kusov,
            plocha_prierezu, plocha_plasta, hmotnost
        ]
    }
    st.table(pd.DataFrame(prehlad_dat))
