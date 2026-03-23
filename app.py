import streamlit as st
import pandas as pd
import math
from datetime import date
import re
import numpy as np
import pickle
from xgboost import XGBRegressor

# 1. premenná - dátum
datum = st.date_input("Dátum", value=date.today())

# 2. premenná - ponuka
ponuka = st.text_input("Číslo ponuky")

# 3. premenná - item
item = st.text_input("Identifikátor položky")

# 4. premenná - pocet_kusov
pocet_kusov = st.number_input("Počet kusov", min_value=1, step=1, format="%d")

# 5. premenná - narocnost
narocnost = st.selectbox("Náročnosť", options=["1", "2", "3", "4", "5"])

# 6. premenná - d
d = st.number_input("Priemer komponentu [mm]", min_value=0.0, step=0.1, format="%.2f")

# 7. premenná - l
l = st.number_input("Dĺžka komponentu [mm]", min_value=0.0, step=0.1, format="%.2f")

# --- SPRÁVNE NAČÍTANIE SHEETU ---
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

@st.cache_data
def load_data(url):
    # Načítame CSV
    data = pd.read_csv(url)
    # Očistíme názvy stĺpcov od medzier (napr. z "hustota " urobí "hustota")
    data.columns = data.columns.str.strip()
    # Očistíme textové hodnoty v stĺpcoch material a akost
    for col in ['material', 'akost']:
        data[col] = data[col].astype(str).str.strip()
    return data

df_materialy = load_data(sheet_url)

# --- 8. PREMENNÁ - Materiál ---
seznam_materialov = sorted(df_materialy['material'].unique())

# Výber materiálu uložíme priamo do pamäte aplikácie (session_state)
st.session_state['material_volba'] = st.selectbox("Materiál", options=seznam_materialov)
material = st.session_state['material_volba'] # Toto zabezpečí, že premenná 'material' existuje

# 9. PREMENNÁ - Akosť (Dostupná pre všetky materiály)
seznam_akosti = list(sorted(df_materialy[df_materialy['material'] == material]['akost'].unique()))
seznam_akosti.append("Iná akosť (zadať ručne)")

akost_vyber = st.selectbox("Akosť", options=seznam_akosti)

# Ak užívateľ zvolí ručné zadanie akosti
if akost_vyber == "Iná akosť (zadať ručne)":
    akost = st.text_input("Zadajte názov novej akosti:")
    if not akost:
        st.warning("Prosím, zadajte názov akosti.")
        st.stop()
else:
    akost = akost_vyber

# 10. PREMENNÁ - HUSTOTA
hustota = 0.0

# A. Logika pre PLAST (hľadá v sheete)
if material == "PLAST":
    if akost_vyber != "Iná akosť (zadať ručne)":
        vyber = df_materialy[(df_materialy['material'] == material) & (df_materialy['akost'] == akost)]
        if not vyber.empty:
            raw_val = str(vyber['hustota'].values[0]).strip()
            temp_val = raw_val.replace(',', '')
            clean_val = re.sub(r'[^0-9.]', '', temp_val)
            try:
                hustota = float(clean_val)
            except ValueError:
                hustota = 0.0
    # Ak je to nová akosť plastu, hustota zostane 0.0 a vypýta si ju ručne nižšie

# B. Logika pre ostatné materiály (podľa tvojich podmienok)
elif material == "NEREZ":
    hustota = 8000.0
elif material == "OCEĽ":
    hustota = 7900.0
elif material == "FAREBNÉ KOVY":
    if akost.startswith("3.7"):
        hustota = 4500.0
    elif akost.startswith("3."):
        hustota = 2900.0
    elif akost.startswith("2."):
        hustota = 9000.0
    # Ak nová akosť farebného kovu nezačína týmito číslami, hustota zostane 0.0

# ZOBRAZENIE / RUČNÉ DOPLNENIE
if hustota <= 0:
    hustota = st.number_input("Hustota nenájdená alebo neznáma. Zadajte manuálne [kg/m3]:", min_value=0.0, format="%.2f")
else:
    # Ak sa hustota určila automaticky (napr. 7900 pre Oceľ), tu sa zobrazí a dá sa prepísať
    hustota = st.number_input("Hustota materiálu [kg/m3]:", value=hustota, format="%.2f")

# Validácia
if hustota <= 0:
    st.warning("Pre pokračovanie je potrebné určiť hustotu materiálu.")
    st.stop()
# --- NAČÍTANIE SHEETU ZÁKAZNÍKOV ---
sheet_zakaznici_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"

@st.cache_data
def load_customers(url):
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    # Vyčistíme textové stĺpce
    for col in data.columns:
        if data[col].dtype == 'object':
            data[col] = data[col].astype(str).str.strip()
    return data

df_zakaznici = load_customers(sheet_zakaznici_url)

st.subheader("Informácie o zákazníkovi")

# 11. PREMENNÁ - zakaznik
# Do zoznamu pridáme možnosť pre nového zákazníka
seznam_zakaznikov = list(sorted(df_zakaznici['zakaznik'].unique()))
seznam_zakaznikov.append("Nový zákazník (zadať ručne)")

zakaznik_vyber = st.selectbox("Vyberte zákazníka", options=seznam_zakaznikov)

# Inicializácia premenných
zakaznik = ""
krajina = ""
lojalita = 0.0

if zakaznik_vyber == "Nový zákazník (zadať ručne)":
    # Ručné zadanie mena a krajiny
    zakaznik = st.text_input("Zadajte meno nového zákazníka:")
    krajina = st.text_input("Zadajte krajinu zákazníka:")
    # 13. PREMENNÁ - lojalita pre nového zákazníka je automaticky 0.5
    lojalita = 0.5
    
    if not zakaznik or not krajina:
        st.warning("Prosím, vyplňte meno aj krajinu zákazníka.")
        st.stop()
else:
    # 11. PREMENNÁ - zakaznik (zo zoznamu)
    zakaznik = zakaznik_vyber
    data_zakaznika = df_zakaznici[df_zakaznici['zakaznik'] == zakaznik]
    
    if not data_zakaznika.empty:
        # 12. PREMENNÁ - krajina (zo sheetu)
        krajina = str(data_zakaznika['krajina'].values[0])
        
        # 13. PREMENNÁ - lojalita (zo sheetu)
        raw_lojalita = str(data_zakaznika['lojalita'].values[0])
        clean_lojalita = re.sub(r'[^0-9.]', '', raw_lojalita.replace(',', '.'))
        try:
            lojalita = float(clean_lojalita)
        except ValueError:
            lojalita = 0.0
    else:
        st.error("Dáta sa nepodarilo načítať.")
        st.stop()

# Zobrazenie výsledných hodnôt pre kontrolu
st.info(f"Zákazník: **{zakaznik}** | Krajina: **{krajina}** | Lojalita: **{lojalita}**")

# --- NAČÍTANIE SHEETU CENA MATERIÁLU ---
sheet_cena_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv"

@st.cache_data
def load_material_prices(url):
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    # Očistíme texty pre presné párovanie
    for col in ['material', 'akost']:
        if col in data.columns:
            data[col] = data[col].astype(str).str.strip()
    return data

df_ceny = load_material_prices(sheet_cena_url)

st.subheader("Cena materiálu")

# Inicializácia premenných pre výpočet
cena_za_meter = 0.0
pouzite_d_zo_sheetu = None

# 1. Pokus o nájdenie v tabuľke
mask = (df_ceny['material'] == material) & (df_ceny['akost'] == akost)
dostupne_rozmery = df_ceny[mask].copy()

if not dostupne_rozmery.empty:
    # Hľadáme najbližšie d >= zadatému d (6. premenná)
    vhodne_riadky = dostupne_rozmery[dostupne_rozmery['d'] >= d]
    
    if not vhodne_riadky.empty:
        # Zoradíme a vezmeme najmenší vyhovujúci priemer
        najblizsi = vhodne_riadky.sort_values(by='d').iloc[0]
        cena_za_meter = float(najblizsi['cena'])
        pouzite_d_zo_sheetu = najblizsi['d']
        st.success(f"Automaticky nájdená cena v cenníku (pre d={pouzite_d_zo_sheetu} mm): **{cena_za_meter:.2f} €/m**")

# 2. Ak sa v tabuľke nič nenašlo (alebo nie je dosť veľké d), užívateľ zadáva ručne
if cena_za_meter <= 0:
    st.info("Materiál, akosť alebo vyhovujúci priemer sa v cenníku nenachádza.")
    cena_za_meter = st.number_input("Zadajte cenu materiálu za meter (hodnota zo stĺpca 'cena') [€/m]:", min_value=0.0, format="%.2f")

# 3. FINÁLNY VÝPOČET: 14. PREMENNÁ cena_material
# Vzorec: cena_material = cena * l / 1000
cena_material = cena_za_meter * (l / 1000)

if cena_material > 0:
    st.metric("Vypočítaná cena materiálu na 1 kus", f"{cena_material:.2f} €")
else:
    st.warning("Zadajte cenu materiálu pre pokračovanie.")
    st.stop()

# 15. PREMENNÁ - Hmotnosť kusu
# Používame premenné d (6.) a l (7.), ktoré už máš definované vyššie
hmotnost = hustota * (math.pi / 4) * (d / 1000)**2 * (l / 1000)

# Zobrazenie výsledku pre kontrolu
st.write(f"**Hmotnosť 1 kusu:** {hmotnost:.4f} kg")

# 16. PREMENNÁ - Plocha prierezu v mm2
plocha_prierezu = (math.pi * d**2) / 4

# Zobrazenie výsledku
st.write(f"**Plocha prierezu:** {plocha_prierezu:.2f} mm²")

# 17. PREMENNÁ - Plocha prierezu v dm2
# Prevod z mm2 na dm2 (delíme 10 000)
plocha_prierez_dm2 = plocha_prierezu / 10000

# Zobrazenie výsledku
st.write(f"**Plocha prierezu v dm²:** {plocha_prierez_dm2:.4f} dm²")

# 18. PREMENNÁ - Plocha plášťa v mm2
# Vzorec: obvod kruhu (pi * d) vynásobený dĺžkou (l)
plocha_plasta = math.pi * d * l

# Zobrazenie výsledku
st.write(f"**Plocha plášťa:** {plocha_plasta:.2f} mm²")

# --- NOVÉ NAČÍTANIE SHEETU KOOPERÁCIE (GID 1180392224) ---
sheet_koop_cennik_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv"

@st.cache_data
def load_koop_cennik(url):
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    # Vyčistíme texty pre presné párovanie
    for col in ['druh', 'material', 'jednotka']:
        if col in data.columns:
            data[col] = data[col].astype(str).str.strip()
    return data

df_koop_cennik = load_koop_cennik(sheet_koop_cennik_url)

# --- 19. PREMENNÁ: KOOPERÁCIA (OPRAVENÁ) ---
st.subheader("Kooperácia")

je_kooperacia = st.checkbox("Vyžaduje tento diel kooperáciu?", value=False, key="chk_koop_final")
cena_kooperacia = 0.0 

if je_kooperacia:
    # Používame df_koop_cennik (názov musí sedieť s tým, čo si načítala cez pandas)
    zoznam_druhov = sorted(df_koop_cennik['druh'].unique())
    vybrany_druh = st.selectbox("Vyberte druh kooperácie", options=zoznam_druhov, key="sb_druh_final")
    
    mats_pre_druh = sorted(df_koop_cennik[df_koop_cennik['druh'] == vybrany_druh]['material'].unique())
    vybrany_mat_koop = st.selectbox("Potvrďte materiál kooperácie", options=mats_pre_druh, key="sb_mat_final")
    
    # Vytiahnutie konkrétneho riadku
    riadok_koop = df_koop_cennik[(df_koop_cennik['druh'] == vybrany_druh) & (df_koop_cennik['material'] == vybrany_mat_koop)].iloc[0]
    
    tarifa = float(riadok_koop['tarifa'])
    jednotka = str(riadok_koop['jednotka']).strip().lower()
    minimum_objednavka = float(riadok_koop['minimum'])
    
    vypocitana_jednotkova_cena = 0.0
    if jednotka == "kg":
        vypocitana_jednotkova_cena = tarifa * hmotnost
    elif jednotka == "dm2":
        vypocitana_jednotkova_cena = tarifa * plocha_prierez_dm2
        
    celkova_suma_v_davke = pocet_kusov * vypocitana_jednotkova_cena
    
    if celkova_suma_v_davke < minimum_objednavka:
        cena_kooperacia = minimum_objednavka / pocet_kusov
        st.warning(f"Suma kooperácie nedosiahla limit. Cena na kus bola prepočítaná z minima.")
    else:
        cena_kooperacia = vypocitana_jednotkova_cena

    st.metric("Výsledná cena kooperácie na kus", f"{cena_kooperacia:.2f} €")
else:
    st.info("Diel je bez kooperácie.")
    cena_kooperacia = 0.0

# 20. PREMENNÁ - Vstupné náklady na 1 kus
# Sčítame cenu materiálu (14. premenná) a cenu kooperácie (19. premenná)
vstupne_naklady = cena_material + cena_kooperacia

# Zobrazenie pre kontrolu
st.subheader("Súčet vstupných nákladov")
col1, col2 = st.columns(2)
col1.metric("Materiál", f"{cena_material:.2f} €")
col2.metric("Kooperácia", f"{cena_kooperacia:.2f} €")

st.metric("CELKOVÉ VSTUPNÉ NÁKLADY (na kus)", f"{vstupne_naklady:.2f} €")

# --- 21. PREMENNÁ: MODEL 1 (PREDIKCIA ČASU) ---
st.subheader("Predikcia výrobného času (Model 1)")

try:
    # 1. Načítanie súborov z podpriecinka MECASYS_APP
    # Upravené cesty k súborom:
    with open('MECASYS_APP/stlpce_modelu.pkl', 'rb') as f:
        model_columns = pickle.load(f)

    loaded_model = XGBRegressor()
    loaded_model.load_model('MECASYS_APP/finalny_model.json')

    # 2. Vytvorenie prázdneho riadku
    input_df = pd.DataFrame(0, index=[0], columns=model_columns)

    # 3. Transformácia vstupov
    input_df['pocet_kusov'] = np.log1p(pocet_kusov)
    input_df['d'] = d
    input_df['l'] = l
    input_df['plocha_prierezu'] = plocha_prierezu
    input_df['plocha_plasta'] = plocha_plasta

    # 4. Kategórie (One-Hot Encoding)
    for prefix, value in {'material': material, 'akost': akost, 'narocnost': narocnost}.items():
        col_name = f"{prefix}_{value}"
        if col_name in input_df.columns:
            input_df[col_name] = 1

    # 5. Predikcia a inverzná transformácia
    log_predikcia = loaded_model.predict(input_df)[0]
    cas = np.expm1(log_predikcia)

    # 6. Zobrazenie
    if cas > 0:
        st.success(f"Výrobný čas bol úspešne predikovaný.")
        c1, c2 = st.columns(2)
        c1.metric("Čas na 1 kus", f"{cas:.2f} min")
        c2.metric("Celkový čas dávky", f"{cas * pocet_kusov:.1f} min")
    else:
        st.error("Model vrátil neplatný čas.")

except Exception as e:
    # Ak súbory stále nevidí, vypíše sa presná cesta, ktorú Python hľadá
    st.warning(f"Model 1 zatiaľ nie je pripravený alebo chýbajú súbory. (Chyba: {e})")
