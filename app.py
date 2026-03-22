import streamlit as st
import pandas as pd
import math
from datetime import date

# --- 1. NAČÍTANIE DÁT Z GOOGLE SHEETS ---
SHEET_ZAKAZNICI = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"
SHEET_MATERIALY = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"
SHEET_CENNIK = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv"

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
df_cennik = load_data(SHEET_CENNIK)

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

# --- 3. SEKCIU: ZÁKAZNÍK ---
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
elif vyber_z != "--- Vyber zo zoznamu ---":
    data_z = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
    zakaznik = vyber_z
    krajina = str(data_z['krajina'])
    lojalita = float(data_z['lojalita'])
    st.info(f"**Lokalita:** {krajina} | **Lojalita:** {lojalita}")

st.divider()

# --- 4. SEKCIU: MATERIÁL ---
st.subheader("3. Materiálové parametre")
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    list_mat = sorted(df_mat['material'].dropna().unique().tolist()) if not df_mat.empty else []
    material = st.selectbox("Materiál", list_mat)

with col_m2:
    df_f = df_mat[df_mat['material'] == material]
    list_ako = sorted(df_f['akost'].dropna().unique().tolist()) + ["Iná akosť (zadať manuálne)"]
    vyber_ako = st.selectbox("Akosť", list_ako)

akost = ""
hustota = 0.0

if vyber_ako == "Iná akosť (zadať manuálne)":
    akost = st.text_input("Názov novej akosti")
    hustota = st.number_input("Hustota novej akosti [kg/m³]", min_value=0.0, step=1.0)
else:
    akost = vyber_ako
    if material == "NEREZ": hustota = 8000.0
    elif material == "OCEĽ": hustota = 7900.0
    elif material == "PLAST":
        try:
            val = df_f[df_f['akost'] == akost]['hustota'].iloc[0]
            if isinstance(val, str): val = val.replace(',', '').strip()
            hustota = float(val)
        except: hustota = 0.0
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
with col_p1: d = st.number_input("Priemer d [mm]", min_value=0.0, step=0.1, format="%.2f")
with col_p2: l = st.number_input("Dĺžka l [mm]", min_value=0.0, step=0.1, format="%.2f")
with col_p3: narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")
pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, step=1, value=1)

# --- VÝPOČTY GEOMETRIE ---
plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

st.divider()

# --- 6. SEKCIU: EKONOMIKA (Cena materiálu a kooperácia) ---
st.subheader("5. Ekonomické vstupy")

cena_material = 0.0
nastal_problem_s_cenou = False

# Pokus o automatický výpočet ceny zo sheetu
if vyber_ako != "Iná akosť (zadať manuálne)" and not df_cennik.empty:
    mask = (df_cennik['material'] == material) & (df_cennik['akost'] == akost)
    df_potencialne = df_cennik[mask]
    
    if not df_potencialne.empty:
        df_vhodne_d = df_potencialne[df_potencialne['d'] >= d]
        if not df_vhodne_d.empty:
            najblizsie_d_row = df_vhodne_d.sort_values(by='d').iloc[0]
            jednotkova_cena = float(najblizsie_d_row['cena'])
            cena_material = (jednotkova_cena * l) / 1000
            st.success(f"Automatická cena z cenníka: {jednotkova_cena} €/m (použitý priemer {najblizsie_d_row['d']} mm)")
        else:
            nastal_problem_s_cenou = True
            st.warning("V cenníku nie je dostatočný priemer.")
    else:
        nastal_problem_s_cenou = True
        st.warning("Akosť sa nenachádza v cenníku.")
else:
    # Ak je zvolená "Iná akosť", rovno vyžadujeme manuálnu cenu
    nastal_problem_s_cenou = True

# Ak sa nepodarilo vypočítať cenu automaticky, užívateľ ju zadá ručne
if nastal_problem_s_cenou:
    cena_material = st.number_input("Zadajte cenu materiálu na 1 kus [€]", min_value=0.0, step=0.01, format="%.2f")

cena_kooperacia = st.number_input("Cena kooperácie na 1 kus [€]", min_value=0.0, step=0.01, format="%.2f")
vstupne_naklady = cena_material + cena_kooperacia

# --- ZOBRAZENIE VÝSLEDKOV ---
st.divider()
st.subheader("6. Výsledné technické a ekonomické parametre")
r1, r2, r3 = st.columns(3)
r1.metric("Hmotnosť kusu", f"{hmotnost:.3f} kg")
r2.metric("Cena materiálu / ks", f"{cena_material:.2f} €")
r3.metric("Vstupné náklady / ks", f"{vstupne_naklady:.2f} €")

# --- SÚHRNNÁ TABUĽKA ---
if st.checkbox("Zobraziť tabuľku všetkých premenných"):
    prehlad = {
        "Premenná": ["Ponuka", "Item", "Zákazník", "Krajina", "Lojalita", "Materiál", "Akosť", "Hustota", "d", "l", "Náročnosť", "Kusy", "Plocha prierezu", "Plocha plášťa", "Hmotnosť", "Cena mat.", "Vstupné náklady"],
        "Hodnota": [ponuka, item, zakaznik, krajina, lojalita, material, akost, hustota, d, l, narocnost, pocet_kusov, plocha_prierezu, plocha_plasta, hmotnost, cena_material, vstupne_naklady]
    }
    st.table(pd.DataFrame(prehlad))
