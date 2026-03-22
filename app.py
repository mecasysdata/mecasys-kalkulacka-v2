import streamlit as st
import pandas as pd
import math
from datetime import date

# --- 1. NAČÍTANIE DÁT ---
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
SHEET_ZAKAZNICI = f"{URL_BASE}gid=324957857&single=true&output=csv"
SHEET_MATERIALY = f"{URL_BASE}gid=1281008948&single=true&output=csv"
SHEET_CENNIK    = f"{URL_BASE}gid=901617097&single=true&output=csv"
SHEET_KOOPERACIE= f"{URL_BASE}gid=1180392224&single=true&output=csv"

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
df_koop_cennik = load_data(SHEET_KOOPERACIE)

st.set_page_config(page_title="Kalkulačná aplikácia", layout="wide")
st.title("⚙️ Kompletný prehľad všetkých premenných")

# --- 2. ZÁKAZNÍK ---
st.subheader("1. Identifikácia a Zákazník")
list_z = ["--- Vyber ---", "Nový zákazník (manual)"] + (sorted(df_zakaznici['zakaznik'].unique().tolist()) if not df_zakaznici.empty else [])
vyber_z = st.selectbox("Zákazník", list_z)

zakaznik, krajina, lojalita = "", "", 0.0

if vyber_z == "Nový zákazník (manual)":
    zakaznik = st.text_input("Meno nového zákazníka")
    krajina = st.text_input("Krajina")
    lojalita = 0.5
    st.warning(f"Doplniť údaje! Automatická lojalita: {lojalita}")
elif vyber_z != "--- Vyber ---":
    dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
    zakaznik, krajina, lojalita = vyber_z, str(dz['krajina']), float(dz['lojalita'])

ponuka = st.text_input("Označenie ponuky", placeholder="CP-2026-XXX")
item = st.text_input("Názov komponentu (Item)")

# --- 3. MATERIÁL A HUSTOTA ---
st.divider()
st.subheader("2. Materiálové parametre")
material = st.selectbox("Materiál", sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else [])
df_f = df_mat[df_mat['material'] == material]
list_ako = sorted(df_f['akost'].unique().tolist()) + ["Iná akosť (manual)"]
vyber_ako = st.selectbox("Akosť", list_ako)

hustota = 0.0
akost = ""

if vyber_ako == "Iná akosť (manual)":
    akost = st.text_input("Zadaj názov novej akosti")
    hustota = st.number_input("Zadaj hustotu!", min_value=0.0)
    if hustota == 0:
        st.error("Zadaj hustotu! Musí zadať technológ.")
else:
    akost = vyber_ako
    if material == "NEREZ": hustota = 8000.0
    elif material == "OCEĽ": hustota = 7900.0
    elif material == "PLAST":
        try:
            hustota = float(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
        except:
            hustota = 0.0
    elif material == "FAREBNÉ KOVY":
        ako_s = str(akost)
        if ako_s.startswith("3.7"): hustota = 4500.0
        elif ako_s.startswith("3."): hustota = 2900.0
        else: hustota = 9000.0
    
    if hustota == 0:
        st.error("Zadaj hustotu! V databáze chýba.")

# --- 4. ROZMERY A VÝPOČTY GEOMETRIE ---
st.divider()
st.subheader("3. Technické parametre")
col_dim1, col_dim2 = st.columns(2)
with col_dim1:
    d = st.number_input("Priemer d [mm]", min_value=0.0)
    l = st.number_input("Dĺžka l [mm]", min_value=0.0)
with col_dim2:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

# Výpočty
plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

# --- 5. EKONOMIKA ---
st.divider()
st.subheader("4. Ekonomika")

# CENA MATERIÁLU
cena_material = 0.0
res_mat = df_cennik[(df_cennik['material'] == material) & (df_cennik['akost'] == akost) & (df_cennik['d'] >= d)]

if not res_mat.empty:
    row_m = res_mat.sort_values('d').iloc[0]
    cena_material = (float(row_m['cena']) * l) / 1000
    st.success(f"Materiál nájdený: {row_m['d']} mm")
else:
    cena_material = st.number_input("Zadaj cenu materiálu na 1ks manuálne [€]", min_value=0.0)

# CENA KOOPERÁCIE
ma_koop = st.radio("Vyžaduje diel kooperáciu?", ["Nie", "Áno"])
cena_kooperacia = 0.0
vybrany_druh_koop = "Žiadna"

if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
    list_k = sorted(df_k_f['druh'].unique().tolist()) if not df_k_f.empty else []
    
    if list_k:
        vybrany_druh_koop = st.selectbox("Druh kooperácie", list_k)
        rk = df_k_f[df_k_f['druh'] == vybrany_druh_koop].iloc[0]
        
        tarifa = float(rk['tarifa'])
        min_zak = float(rk['minimalna_zakazka'])
        jednotka_koop = str(rk['jednotka'])
        
        odhad = (tarifa * hmotnost) if jednotka_koop == 'kg' else (tarifa * plocha_plasta / 10000)
        
        if (odhad * pocet_kusov) < min_zak:
            cena_kooperacia = min_zak / pocet_kusov
        else:
            cena_kooperacia = odhad
    else:
        cena_kooperacia = st.number_input("Zadaj cenu kooperácie na 1ks manuálne [€]", min_value=0.0)
        vybrany_druh_koop = "Manuálne zadaná"

# FINÁLNY SÚČET
vstupne_naklady = cena_material + cena_kooperacia

# --- 6. KOMPLETNÝ PREHĽAD VŠETKÝCH PREMENNÝCH ---
st.divider()
st.subheader("5. Prehľad všetkých vytvorených premenných")

vsetky_premenne = {
    "Kategória": [
        "Identifikácia", "Identifikácia", "Identifikácia", 
        "Zákazník", "Zákazník", "Zákazník",
        "Materiál", "Materiál", "Materiál",
        "Rozmery", "Rozmery", "Rozmery", "Rozmery",
        "Geometria", "Geometria", "Geometria",
        "Ekonomika", "Ekonomika", "Ekonomika", "Ekonomika"
    ],
    "Premenná (Kód)": [
        "ponuka", "item", "datum",
        "zakaznik", "krajina", "lojalita",
        "material", "akost", "hustota",
        "d", "l", "pocet_kusov", "narocnost",
        "plocha_prierezu", "plocha_plasta", "hmotnost",
        "cena_material", "vybrany_druh_koop", "cena_kooperacia", "vstupne_naklady"
    ],
    "Hodnota": [
        ponuka, item, datum,
        zakaznik, krajina, lojalita,
        material, akost, hustota,
        d, l, pocet_kusov, narocnost,
        f"{plocha_prierezu:.2f} mm²", f"{plocha_plasta:.2f} mm²", f"{hmotnost:.4f} kg",
        f"{cena_material:.4f} €", vybrany_druh_koop, f"{cena_kooperacia:.4f} €", f"{vstupne_naklady:.4f} €"
    ]
}

df_prehlad = pd.DataFrame(vsetky_premenne)
st.table(df_prehlad)

st.metric("Celkové vstupné náklady na kus", f"{vstupne_naklady:.2f} €")
