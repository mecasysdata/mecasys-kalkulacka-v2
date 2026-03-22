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

# --- 2. IDENTIFIKÁCIA A ZÁKAZNÍK ---
st.subheader("1. Identifikácia a Zákazník")
col_id1, col_id2 = st.columns(2)

with col_id1:
    datum = st.date_input("Dátum vystavenia", value=date.today())
    ponuka = st.text_input("Označenie ponuky", placeholder="CP-2026-XXX")
    item = st.text_input("Názov komponentu (Item)")

with col_id2:
    list_z = ["--- Vyber ---", "Nový zákazník (manual)"]
    if not df_zakaznici.empty:
        list_z += sorted(df_zakaznici['zakaznik'].dropna().unique().tolist())
    
    vyber_z = st.selectbox("Zákazník", list_z)

    zakaznik = ""
    krajina = ""
    lojalita = 0.0

    if vyber_z == "Nový zákazník (manual)":
        zakaznik = st.text_input("Meno nového zákazníka")
        krajina = st.text_input("Krajina")
        lojalita = 0.5
        st.warning(f"⚠️ Doplniť údaje! Automatická lojalita: {lojalita}")
    elif vyber_z != "--- Vyber ---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik = vyber_z
        krajina = str(dz['krajina'])
        lojalita = float(dz['lojalita'])
        st.info(f"✅ Zákazník: {krajina} | Lojalita: {lojalita}")

st.divider()

# --- 3. MATERIÁL A HUSTOTA ---
st.subheader("2. Materiálové parametre")
col_m1, col_m2 = st.columns(2)

with col_m1:
    list_mat = sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else []
    material = st.selectbox("Materiál", list_mat)
    
    df_f = df_mat[df_mat['material'] == material]
    list_ako = sorted(df_f['akost'].unique().tolist()) + ["Iná akosť (manual)"]
    vyber_ako = st.selectbox("Akosť", list_ako)

hustota = 0.0
akost = ""

with col_m2:
    if vyber_ako == "Iná akosť (manual)":
        akost = st.text_input("Zadaj názov novej akosti")
        hustota = st.number_input("Zadaj hustotu!", min_value=0.0)
        if hustota == 0:
            st.error("❌ Zadaj hustotu! Musí zadať technológ.")
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
        
        st.metric("Hustota (kg/m³)", f"{hustota}")
        if hustota == 0:
            st.error("❌ Zadaj hustotu! V databáze chýba.")

st.divider()

# --- 4. ROZMERY A GEOMETRIA ---
st.subheader("3. Technické parametre")
col_p1, col_p2 = st.columns(2)

with col_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.0, format="%.2f")
    l = st.number_input("Dĺžka l [mm]", min_value=0.0, format="%.2f")

with col_p2:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1)
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

# Výpočty
plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

st.divider()

# --- 5. EKONOMIKA ---
st.subheader("4. Ekonomika")

# 5.1 CENA MATERIÁLU
cena_material = 0.0
res_mat = df_cennik[(df_cennik['material'] == material) & (df_cennik['akost'] == akost) & (df_cennik['d'] >= d)]

if not res_mat.empty:
    row_m = res_mat.sort_values('d').iloc[0]
    cena_material = (float(row_m['cena']) * l) / 1000
    st.success(f"✅ Materiál nájdený (polotovar d={row_m['d']} mm): {cena_material:.4f} €/ks")
else:
    cena_material = st.number_input("Zadaj cenu materiálu na 1ks manuálne [€]", min_value=0.0)

# 5.2 CENA KOOPERÁCIE
ma_koop = st.radio("Vyžaduje diel kooperáciu?", ["Nie", "Áno"], horizontal=True)
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
        jednotka_koop = str(rk['jednotka']).strip().lower()
        
        odhad = (tarifa * hmotnost) if jednotka_koop == 'kg' else (tarifa * plocha_plasta / 10000)
        
        if (odhad * pocet_kusov) < min_zak:
            cena_kooperacia = min_zak / pocet_kusov
            st.warning(f"Uplatnená minimálna zákazka ({min_zak} €)")
        else:
            cena_kooperacia = odhad
    else:
        cena_kooperacia = st.number_input("Zadaj cenu kooperácie na 1ks manuálne [€]", min_value=0.0)
        vybrany_druh_koop = "Manuálne zadaná"

# 5.3 VSTUPNÉ NÁKLADY
vstupne_naklady = cena_material + cena_kooperacia

# --- 6. TABUĽKA PREHĽADU ---
st.divider()
st.subheader("5. Prehľad všetkých vytvorených premenných")

data_final = {
    "Premenná": [
        "Označenie ponuky", "Item", "Dátum", "Zákazník", "Krajina", "Lojalita",
        "Materiál", "Akosť", "Hustota [kg/m³]", "Priemer d [mm]", "Dĺžka l [mm]",
        "Počet kusov", "Náročnosť", "Plocha prierezu [mm²]", "Plocha plášťa [mm²]",
        "Hmotnosť [kg]", "Cena materiálu [€/ks]", "Druh kooperácie", 
        "Cena kooperácie [€/ks]", "VSTUPNÉ NÁKLADY [€/ks]"
    ],
    "Hodnota": [
        ponuka, item, datum, zakaznik, krajina, lojalita,
        material, akost, hustota, d, l,
        pocet_kusov, narocnost, round(plocha_prierezu, 2), round(plocha_plasta, 2),
        round(hmotnost, 4), round(cena_material, 4), vybrany_druh_koop,
        round(cena_kooperacia, 4), round(vstupne_naklady, 4)
    ]
}

st.table(pd.DataFrame(data_final))


