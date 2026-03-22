import streamlit as st
import pandas as pd
import math
from datetime import date

# --- 1. KONFIGURÁCIA A NAČÍTANIE DÁT ---
st.set_page_config(page_title="Kalkulačný systém", layout="wide")

URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?"
SHEET_ZAKAZNICI = f"{URL_BASE}gid=324957857&single=true&output=csv"
SHEET_MATERIALY = f"{URL_BASE}gid=1281008948&single=true&output=csv"
SHEET_CENNIK    = f"{URL_BASE}gid=901617097&single=true&output=csv"
SHEET_KOOPERACIE= f"{URL_BASE}gid=1180392224&single=true&output=csv"

# Pomocná funkcia na čistenie čísiel z Google Sheets
def safe_float(val):
    if pd.isna(val) or val == "": return 0.0
    try:
        # Odstráni medzery, € a zmení čiarku na bodku
        s = str(val).replace(' ', '').replace('€', '').replace(',', '.')
        return float(s)
    except:
        return 0.0

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

st.title("⚙️ Komplexný kalkulačný systém")

# --- 2. IDENTIFIKÁCIA (Skrátené pre prehľadnosť) ---
st.subheader("1. Identifikácia a Zákazník")
col_id1, col_id2 = st.columns(2)
with col_id1:
    datum = st.date_input("Dátum vystavenia", value=date.today())
    ponuka = st.text_input("Označenie ponuky", "CP-2026-001")
    item = st.text_input("Názov komponentu (Item)")
with col_id2:
    list_z = ["--- Vyber ---"]
    if not df_zakaznici.empty: list_z += sorted(df_zakaznici['zakaznik'].dropna().unique().tolist())
    vyber_z = st.selectbox("Zákazník", list_z)
    zakaznik, krajina, lojalita = "", "", 0.0
    if vyber_z != "--- Vyber ---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik, krajina, lojalita = vyber_z, str(dz['krajina']), safe_float(dz['lojalita'])

st.divider()

# --- 3. MATERIÁL A ROZMERY ---
col_m1, col_m2 = st.columns(2)
with col_m1:
    material = st.selectbox("Materiál", sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else [])
    df_f = df_mat[df_mat['material'] == material]
    akost = st.selectbox("Akosť", sorted(df_f['akost'].unique().tolist()) if not df_f.empty else [])
    d = st.number_input("Priemer d [mm]", min_value=0.1, value=20.0, format="%.2f")
    l = st.number_input("Dĺžka l [mm]", min_value=0.1, value=50.0, format="%.2f")
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

# HUSTOTA LOGIKA
hustota = 0.0
if material == "NEREZ": hustota = 8000.0
elif material == "OCEĽ": hustota = 7900.0
elif material == "PLAST":
    try: hustota = safe_float(df_f[df_f['akost'] == akost]['hustota'].iloc[0])
    except: hustota = 1200.0
elif material == "FAREBNÉ KOVY":
    if str(akost).startswith("3.7"): hustota = 4500.0
    elif str(akost).startswith("3."): hustota = 2900.0
    else: hustota = 9000.0

# VÝPOČTY GEOMETRIE
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

with col_m2:
    st.metric("Hustota", f"{hustota} kg/m³")
    st.metric("Hmotnosť kusu", f"{round(hmotnost, 4)} kg")

st.divider()

# --- 4. EKONOMIKA (TU BOLA CHYBA) ---
st.subheader("4. Ekonomika")

# 4.1 CENA MATERIÁLU - OPRAVENÉ FILTROVANIE
cena_material = 0.0
if not df_cennik.empty:
    # Prevedieme stĺpce v cenníku na čísla, aby sme mohli porovnávať s d (priemerom)
    df_cennik['d_num'] = df_cennik['d'].apply(safe_float)
    df_cennik['cena_num'] = df_cennik['cena'].apply(safe_float)
    
    # Hľadáme zhodu materiálu, akosti a vhodný priemer polotovaru
    res_mat = df_cennik[
        (df_cennik['material'].astype(str).str.strip() == material) & 
        (df_cennik['akost'].astype(str).str.strip() == akost) & 
        (df_cennik['d_num'] >= d)
    ]

    if not res_mat.empty:
        # Zoradíme podľa priemeru a vezmeme najmenší možný polotovar
        row_m = res_mat.sort_values('d_num').iloc[0]
        cena_polotovaru = row_m['cena_num']
        cena_material = (cena_polotovaru * l) / 1000
        st.success(f"✅ Materiál nájdený (polotovar d={row_m['d_num']} mm, cena={cena_polotovaru} €/m)")
    else:
        st.error("❌ Materiál s týmto priemerom nenájdený v cenníku!")
        cena_material = st.number_input("Zadaj cenu materiálu na 1ks manuálne [€]", min_value=0.0)

# 4.2 CENA KOOPERÁCIE
ma_koop = st.radio("Vyžaduje diel kooperáciu?", ["Nie", "Áno"], horizontal=True)
cena_kooperacia = 0.0
vybrany_druh_koop = "Žiadna"

if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material]
    if not df_k_f.empty:
        vybrany_druh_koop = st.selectbox("Druh kooperácie", sorted(df_k_f['druh'].unique()))
        rk = df_k_f[df_k_f['druh'] == vybrany_druh_koop].iloc[0]
        
        tarifa = safe_float(rk['tarifa'])
        min_zak = safe_float(rk['minimalna_zakazka'])
        jednotka_koop = str(rk['jednotka']).strip().lower()
        
        odhad = (tarifa * hmotnost) if 'kg' in jednotka_koop else (tarifa * plocha_plasta / 10000)
        
        # Ošetrenie minimálnej zákazky
        if (odhad * pocet_kusov) < min_zak:
            cena_kooperacia = min_zak / pocet_kusov
        else:
            cena_kooperacia = odhad
    else:
        cena_kooperacia = st.number_input("Manuálna cena kooperácie na 1ks", min_value=0.0)

# 4.3 VSTUPNÉ NÁKLADY
vstupne_naklady = cena_material + cena_kooperacia

# --- 5. FINÁLNY PREHĽAD ---
st.metric("VSTUPNÉ NÁKLADY CELKOM", f"{round(vstupne_naklady, 4)} € / ks")

# Zobrazenie premenných pre tvoju kontrolu
with st.expander("🔍 Detailný výpis premenných"):
    data_final = {
        "Materiál na kus": f"{round(cena_material, 4)} €",
        "Kooperácia na kus": f"{round(cena_kooperacia, 4)} €",
        "Vstupné náklady": f"{round(vstupne_naklady, 4)} €"
    }
    st.json(data_final)
