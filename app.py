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

# --- 2. IDENTIFIKÁCIA ZÁKAZNÍKA ---
st.subheader("1. Identifikácia a Zákazník")
col_id1, col_id2, col_id3 = st.columns(3)

with col_id1:
    datum = st.date_input("Dátum vystavenia", value=date.today())
    ponuka = st.text_input("Označenie ponuky", placeholder="CP-2026-XXX")

with col_id2:
    item = st.text_input("Názov komponentu (Item)", placeholder="Názov dielu")
    list_z = ["--- Vyber zo zoznamu ---", "Nový zákazník (zadať manuálne)"]
    if not df_zakaznici.empty:
        list_z += sorted(df_zakaznici['zakaznik'].dropna().unique().tolist())
    vyber_z = st.selectbox("Zákazník", list_z)

zakaznik, krajina, lojalita = "", "", 0.0

with col_id3:
    if vyber_z == "Nový zákazník (zadať manuálne)":
        zakaznik = st.text_input("Meno nového zákazníka")
        krajina = st.text_input("Krajina")
        lojalita = 0.5
        st.warning(f"⚠️ Nový zákazník: Lojalita nastavená na {lojalita}")
    elif vyber_z != "--- Vyber zo zoznamu ---":
        dz = df_zakaznici[df_zakaznici['zakaznik'] == vyber_z].iloc[0]
        zakaznik, krajina, lojalita = vyber_z, str(dz['krajina']), float(dz['lojalita'])
        st.info(f"✅ Zákazník: {krajina} (Lojalita: {lojalita})")

st.divider()

# --- 3. MATERIÁL A HUSTOTA ---
st.subheader("2. Materiálové parametre")
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    material_list = sorted(df_mat['material'].unique().tolist()) if not df_mat.empty else []
    material = st.selectbox("Materiál", material_list)

with col_m2:
    df_f = df_mat[df_mat['material'] == material]
    list_ako = sorted(df_f['akost'].unique().tolist()) + ["Iná akosť (zadať manuálne)"]
    vyber_ako = st.selectbox("Akosť", list_ako)

hustota = 0.0
akost = ""

if vyber_ako == "Iná akosť (zadať manuálne)":
    akost = st.text_input("Názov novej akosti")
    hustota = st.number_input("ZADAJ HUSTOTU! [kg/m³]", min_value=0.0, step=1.0)
    if hustota == 0:
        st.error("❌ CHYBA: Hustota musí byť zadaná technológom!")
else:
    akost = vyber_ako
    if material == "NEREZ": hustota = 8000.0
    elif material == "OCEĽ": hustota = 7900.0
    elif material == "PLAST":
        try:
            val = df_f[df_f['akost'] == akost]['hustota'].iloc[0]
            hustota = float(str(val).replace(',', '.'))
        except: hustota = 0.0
    elif material == "FAREBNÉ KOVY":
        if str(akost).startswith("3.7"): hustota = 4500.0
        elif str(akost).startswith("3."): hustota = 2900.0
        else: hustota = 9000.0

    if hustota == 0:
        st.error("❌ CHYBA: Hustota v databáze chýba! Vyberte 'Inú akosť' a zadajte ju manuálne.")

with col_m3:
    st.metric("Hustota (kg/m³)", f"{hustota}")

st.divider()

# --- 4. TECHNICKÉ PARAMETRE A GEOMETRIA ---
st.subheader("3. Rozmery a náročnosť")
col_p1, col_p2, col_p3 = st.columns(3)

with col_p1:
    d = st.number_input("Priemer d [mm]", min_value=0.0, format="%.2f")
    l = st.number_input("Dĺžka l [mm]", min_value=0.0, format="%.2f")

with col_p2:
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, step=1)
    narocnost = st.select_slider("Náročnosť výroby", options=["1", "2", "3", "4", "5"], value="3")

# Výpočty geometrie
plocha_prierezu = (math.pi * (d**2)) / 4
plocha_plasta = math.pi * d * l
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

with col_p3:
    st.write("**Vypočítaná geometria:**")
    st.write(f"Hmotnosť: {hmotnost:.3f} kg")
    st.write(f"Plocha plášťa: {plocha_plasta:.1f} mm²")

st.divider()

# --- 5. EKONOMIKA (Cena materiál + Kooperácia) ---
st.subheader("4. Ekonomické vstupy")

# --- 5.1 CENA MATERIÁLU ---
cena_material = 0.0
found_mat = False

if vyber_ako != "Iná akosť (zadať manuálne)" and not df_cennik.empty:
    res = df_cennik[(df_cennik['material'] == material) & 
                    (df_cennik['akost'] == akost) & 
                    (df_cennik['d'] >= d)]
    if not res.empty:
        row_mat = res.sort_values(by='d').iloc[0]
        cena_material = (float(row_mat['cena']) * l) / 1000
        found_mat = True

if not found_mat:
    st.error("⚠️ Rozmer/Akosť nenájdená v cenníku!")
    cena_material = st.number_input("RUČNÝ VSTUP: Cena materiálu na 1ks [€]", min_value=0.0, key="c_mat_man")
else:
    st.success(f"✅ Cena materiálu z cenníka: {cena_material:.2f} € (použitý priemer {row_mat['d']} mm)")

# --- 5.2 CENA KOOPERÁCIE ---
st.write("---")
ma_koop = st.radio("Vyžaduje diel kooperáciu?", ["Nie", "Áno"], horizontal=True)
cena_kooperacia = 0.0

if ma_koop == "Áno":
    df_k_f = df_koop_cennik[df_koop_cennik['material'] == material] if not df_koop_cennik.empty else pd.DataFrame()
    list_druhy = sorted(df_k_f['druh'].unique().tolist()) if not df_k_f.empty else []
    
    if list_druhy:
        vybrany_druh = st.selectbox("Druh kooperácie", list_druhy)
        rk = df_k_f[df_k_f['druh'] == vybrany_druh].iloc[0]
        
        tarifa = float(rk['tarifa'])
        jednotka = str(rk['jednotka']).strip().lower()
        min_zakazka = float(rk['minimalna_zakazka'])
        
        # Výpočet odhadu na 1 kus
        odhad_ks = (tarifa * hmotnost) if jednotka == "kg" else (tarifa * plocha_plasta / 10000)
        
        # Ochranná podmienka na minimálnu zákazku
        if (odhad_ks * pocet_kusov) < min_zakazka:
            cena_kooperacia = min_zakazka / pocet_kusov
            st.warning(f"Aplikovaná minimálna zákazka: {min_zakazka} €")
        else:
            cena_kooperacia = odhad_ks
        
        st.info(f"Vypočítaná kooperácia: {cena_kooperacia:.2f} €/ks")
    else:
        st.error("❌ Pre tento materiál nie je v cenníku žiadna kooperácia!")
        cena_kooperacia = st.number_input("Zadajte cenu kooperácie na 1ks manuálne [€]", min_value=0.0)

# --- 5.3 VSTUPNÉ NÁKLADY ---
vstupne_naklady = cena_material + cena_kooperacia

st.divider()

# --- 6. FINÁLNY SÚHRN ---
st.subheader("5. Výsledné parametre")
res_col1, res_col2, res_col3 = st.columns(3)

with res_col1:
    st.metric("Vstupné náklady / ks", f"{vstupne_naklady:.2f} €")

with res_col2:
    st.metric("Vstupné náklady celkom", f"{vstupne_naklady * pocet_kusov:.2f} €")

with res_col3:
    st.metric("Hmotnosť celkom", f"{hmotnost * pocet_kusov:.2f} kg")

# TABUĽKA PRE XGBOOST (Kontrola dát)
if st.checkbox("Zobraziť tabuľku všetkých premenných pre model"):
    data_pre_model = {
        "Premenná": ["Lojalita", "Hustota", "d", "l", "Náročnosť", "Kusy", "Plocha plášťa", "Hmotnosť", "Cena mat.", "Cena koop.", "Vstupné náklady"],
        "Hodnota": [lojalita, hustota, d, l, narocnost, pocet_kusov, round(plocha_plasta, 2), round(hmotnost, 3), round(cena_material, 2), round(cena_kooperacia, 2), round(vstupne_naklady, 2)]
    }
    st.table(pd.DataFrame(data_pre_model))
