import streamlit as st
import pandas as pd
import math
from datetime import date
import re
import numpy as np
import pickle
from xgboost import XGBRegressor
import requests
import datetime
from fpdf import FPDF
import io

# --- INICIALIZÁCIA KOŠÍKA (SESSION STATE) ---
finalna_cena_na_zapis = 0.0  # Štartovacia hodnota
if 'polozky_ponuky' not in st.session_state:
    st.session_state.polozky_ponuky = []
def pridat_polozku():
    nova_polozka = {
        "Materiál": material,
        "Akosť": akost,
        "Rozmer (d x l)": f"{d} x {l} mm",
        "Kusov": pocet_kusov,
        "Čas (M1)": f"{cas:.2f} min",
        "Cena/ks (M2)": f"{finalna_cena_na_zapis:.2f} EUR", 
        "Spolu": f"{finalna_cena_na_zapis * pocet_kusov:.2f} EUR",
        # TIETO DVA RIADKY SÚ KĽÚČOVÉ PRE PDF:
        "mat_na_kus": cena_material,
        "koop_na_kus": cena_kooperacia,
        "predikovany_cas": cas
    }
    st.session_state.polozky_ponuky.append(nova_polozka)
    st.toast("Položka pridaná do ponuky! ✅")


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

# --- 14. PREMENNÁ: CENA MATERIÁLU (S MOŽNOSŤOU RUČNEJ ÚPRAVY) ---
st.subheader("Cena materiálu")

# 1. KROK: Inicializácia základnej ceny na 0.0
nalezena_cena = 0.0
pouzite_d_zo_sheetu = None

# 2. KROK: Pokus o automatické vyhľadanie v cenníku
mask = (df_ceny['material'] == material) & (df_ceny['akost'] == akost)
dostupne_rozmery = df_ceny[mask].copy()

if not dostupne_rozmery.empty:
    vhodne_riadky = dostupne_rozmery[dostupne_rozmery['d'] >= d]
    if not vhodne_riadky.empty:
        najblizsi = vhodne_riadky.sort_values(by='d').iloc[0]
        try:
            # Očistíme a načítame cenu z tabuľky
            nalezena_cena = float(str(najblizsi['cena']).replace(',', '.'))
            pouzite_d_zo_sheetu = najblizsi['d']
            st.info(f"V cenníku nájdená cena: {nalezena_cena:.2f} EUR/m (pre d={pouzite_d_zo_sheetu} mm)")
        except:
            nalezena_cena = 0.0
    else:
        st.warning("V cenníku nie je dostatočne veľký priemer (d).")
else:
    st.warning("Materiál/akost sa v cenníku nenachádza.")

# 3. KROK: Interaktívne políčko (Widget)
# Ak kód našiel cenu, dosadí ju ako default (value). Ak nie, bude tam 0.0.
# Užívateľ ju môže kedykoľvek prepísať.
cena_za_meter = st.number_input(
    "Potvrďte alebo upravte cenu materiálu za meter [EUR/m]:", 
    min_value=0.0, 
    value=nalezena_cena, 
    format="%.2f", 
    key="final_price_input"
)

# 4. KROK: Finálny výpočet na kus
cena_material = cena_za_meter * (l / 1000)

if cena_material > 0:
    st.metric("Vypočítaná cena materiálu na 1 kus", f"{cena_material:.2f} EUR")
else:
    st.error("Pre pokračovanie musí byť cena materiálu vyššia ako 0.")
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

    st.metric("Výsledná cena kooperácie na kus", f"{cena_kooperacia:.2f} EUR")
else:
    st.info("Diel je bez kooperácie.")
    cena_kooperacia = 0.0

# 20. PREMENNÁ - Vstupné náklady na 1 kus
# Sčítame cenu materiálu (14. premenná) a cenu kooperácie (19. premenná)
vstupne_naklady = cena_material + cena_kooperacia

# Zobrazenie pre kontrolu
st.subheader("Súčet vstupných nákladov")
col1, col2 = st.columns(2)
col1.metric("Materiál", f"{cena_material:.2f} EUR")
col2.metric("Kooperácia", f"{cena_kooperacia:.2f} EUR")

st.metric("CELKOVÉ VSTUPNÉ NÁKLADY (na kus)", f"{vstupne_naklady:.2f} EUR")

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

# --- 22. PREMENNÁ: MODEL 2 (PREDIKCIA CENY) ---
st.subheader("Predikcia výslednej ceny (Model M2)")

# Používame tvoju 12. premennú 'krajina'
# Ak ju máš v kóde definovanú vyššie, tu ju len prevezmeme.

try:
    # 1. Načítanie súborov z podpriecinka MECASYS_APP
    # model_columns.pkl (stĺpce) a xgb_model_cena.json (model)
    with open('MECASYS_APP/model_columns.pkl', 'rb') as f:
        m2_columns = pickle.load(f)

    model_m2 = XGBRegressor()
    model_m2.load_model('MECASYS_APP/xgb_model_cena.json')

    # 2. Príprava vstupného riadku (všetko na nulu)
    input_m2 = pd.DataFrame(0, index=[0], columns=m2_columns)

    # 3. Naplnenie číselných hodnôt (Inžiniering)
    # cas (z Modelu 1 v minútach), hmotnost, plocha_prierezu a hustota
    if 'cas' in input_m2.columns:
        input_m2['cas'] = cas
    
    if 'hmotnost' in input_m2.columns:
        input_m2['hmotnost'] = hmotnost
        
    if 'plocha_prierezu' in input_m2.columns:
        input_m2['plocha_prierezu'] = plocha_prierezu
        
    if 'hustota' in input_m2.columns:
        input_m2['hustota'] = hustota

    # 4. Kategorické vstupy (Krajina z 12. premennej)
    # Model pri One-Hot Encodingu očakáva stĺpec v tvare 'krajina_Názov'
    col_krajina = f"krajina_{krajina}"
    
    if col_krajina in input_m2.columns:
        input_m2[col_krajina] = 1
    else:
        # Ak by užívateľ zadal krajinu, ktorú model nikdy nevidel, 
        # model bude predikovať "neutrálnu" cenu (všetky krajiny = 0)
        pass

    # 5. Predikcia (Inverzná transformácia logaritmu)
    log_pred_m2 = model_m2.predict(input_m2)[0]
    predikovana_cena_m2 = np.expm1(log_pred_m2)

    # 6. Zobrazenie výsledku
    if predikovana_cena_m2 > 0:
        st.success(f"Model M2 úspešne predikoval cenu pre krajinu: **{krajina}**")
        st.metric("Predikovaná trhová cena", f"{predikovana_cena_m2:.2f} EUR")
    else:
        st.error("Model M2 vrátil neplatný výsledok.")

except Exception as e:
    # Ak súbory na Gite nie sú v správnom priečinku, tu uvidíš chybu
    st.warning(f"Model M2 nie je k dispozícii. (Chyba: {e})")

# zaciatok upravy ceny
# --- TVOJA NOVÁ LOGIKA POROVNANIA ---
# Definujeme si výslednú cenu. Na začiatku je to tá z modelu.
finalna_cena_na_zapis = predikovana_cena_m2

# Ak sú náklady vyššie ako predikcia modelu
if vstupne_naklady > predikovana_cena_m2:
    st.error(f"⚠️ NÁKLADY ({vstupne_naklady:.2f} EUR) SÚ VYŠŠIE AKO PREDIKCIA ({predikovana_cena_m2:.2f} EUR)!")
    
    # Otvorí sa okno a ty ručne zadáš hodnotu. Žiaden vzorec, čistý tvoj vstup.
    finalna_cena_na_zapis = st.number_input(
        "ZADAJTE RUČNE PREDAJNÚ CENU [EUR]:", 
        min_value=0.0, 
        format="%.2f",
        key="manual_price_input"
    )
else:
    # Ak je model v poriadku, len vypíšeme info
    st.success(f"✅ Model M2 je ziskový (Predikcia: {predikovana_cena_m2:.2f} EUR).")

# Zobrazenie ceny, ktorá sa reálne použije
st.metric("VÝSLEDNÁ CENA", f"{finalna_cena_na_zapis:.2f} EUR")
# koniec upravy ceny 

st.divider()
st.subheader("📦 Aktuálna cenová ponuka")

# Tlačidlo na pridanie
st.button("➕ Pridať aktuálny výpočet do ponuky", on_click=pridat_polozku)

if st.session_state.polozky_ponuky:
    # Zobrazenie tabuľky s položkami
    df_ponuka = pd.DataFrame(st.session_state.polozky_ponuky)
    st.table(df_ponuka)
    

    # Výpočet celkovej sumy (odolný voči chybám)
celkova_suma = 0
for i in st.session_state.polozky_ponuky:
    try:
        # Odstránime EUR, €, medzery a zmeníme čiarku na bodku
        hodnota_str = str(i['Spolu']).replace('EUR', '').replace('€', '').replace(',', '.').strip()
        celkova_suma += float(hodnota_str)
    except Exception as e:
        st.error(f"Chyba pri výpočte sumy v položke: {i['Spolu']}")

st.metric("CELKOVÁ CENA PONUKY", f"{celkova_suma:.2f} EUR")
    
    
    # Tlačidlo na vymazanie
    if st.button("🗑️ Vymazať celú ponuku"):
        st.session_state.polozky_ponuky = []
        st.rerun()
else:
    st.info("Ponuka je prázdna. Pridajte prvú položku pomocou tlačidla vyššie.")

# --- EXPORT DO GOOGLE SHEET (CEZ APPS SCRIPT) ---
st.divider()

if st.session_state.polozky_ponuky:
    st.subheader("🚀 Odoslanie do databázy")
    
    if st.button("Zapísať celú ponuku do Google Sheet"):
        # Tvoja URL z Apps Scriptu
        url_scriptu = "https://script.google.com/macros/s/AKfycbwjChtJjHiZZyU8nVVpHKhcRj2z77pqrJNTw6rDm9dy_WzFaX6Yj0zzbmCSeHU7r8UUyA/exec"
        
        # Príprava balíka dát
        data_na_odoslanie = {
            "items": []
        }
        
        # Vygenerujeme jedno číslo CP pre celú túto dávku
        cislo_cp = "CP-" + datetime.datetime.now().strftime("%Y%m%d-%H%M")
        dnesny_datum = datetime.date.today().strftime("%d.%m.%Y")

        try:
            # Prechádzame položky v košíku a mapujeme ich na stĺpce v Sheete
            for i, item in enumerate(st.session_state.polozky_ponuky):
                
                # OŠETRENIE DÁT: Prevod textových hodnôt z tabuľky na čisté čísla
                # Odstránime " min" a " €", aby sme mohli použiť float()
                cisty_cas = float(str(item["Čas (M1)"]).replace(' min', '').replace(',', '.').strip())
                cista_jednotkova_cena = float(str(item["Cena/ks (M2)"]).replace(' €', '').replace(',', '.').strip())
                cista_suma_polozky = float(str(item["Spolu"]).replace(' €', '').replace(',', '.').strip())
                cisty_pocet_kusov = int(item["Kusov"])

                data_na_odoslanie["items"].append({
                    "datum": dnesny_datum,
                    "cislo_cp": cislo_cp,
                    "zakaznik": zakaznik,      # Premenná 13
                    "krajina": krajina,        # Premenná 12
                    "lojalita": lojalita if 'lojalita' in locals() else "N/A",
                    "item_nazov": f"Item {i+1}", 
                    "material": item["Materiál"],
                    "akost": item["Akosť"],
                    "d": d,
                    "l": l,
                    "hustota": hustota,
                    "hmotnost": hmotnost,
                    "narocnost": "Štandard",
                    "j_cena_mat": cena_za_meter,
                    "naklad_mat": cena_material,
                    "naklad_koop": cena_kooperacia,
                    "vstupne_naklady": cena_material + cena_kooperacia,
                    "cas": cisty_cas,
                    "jednotkova_cena": cista_jednotkova_cena,
                    "pocet_kusov": cisty_pocet_kusov,
                    "cena_spolu": cista_suma_polozky
                })

            # Odoslanie requestu
            with st.spinner("Odosielam dáta do Google Sheet..."):
                response = requests.post(url_scriptu, json=data_na_odoslanie, timeout=10)
                
            if response.status_code == 200:
                st.success(f"✅ Ponuka {cislo_cp} bola úspešne zapísaná do databázy!")
                # Voliteľné: Ak chceš po úspešnom zápise vymazať košík, odkomentuj riadky nižšie:
                # st.session_state.polozky_ponuky = []
                # st.rerun()
            else:
                st.error(f"Chyba servera (Apps Script): {response.status_code}")
                
        except KeyError as e:
            st.error(f"Chyba v názve stĺpca: {e}. Skontroluj, či sa názvy v tabuľke zhodujú s kódom.")
        except Exception as e:
            st.error(f"Nepodarilo sa spojiť s Google Scriptom: {e}")
else:
    st.info("Pridajte položky do ponuky, aby ste ich mohli exportovať.")


# --- GENEROVANIE PDF ---
import datetime

pdf = FPDF(orientation='L', unit='mm', format='A4') # 'L' je na šírku, aby sa ti tam tie stĺpce zmestili
pdf.add_page()
pdf.set_font("Helvetica", "B", 14)

# Hlavička s označením a dátumom
pdf.cell(0, 10, f"CENOVÁ PONUKA: {ponuka}", ln=True, align='L')
pdf.set_font("Helvetica", "", 10)
pdf.cell(0, 8, f"Dátum vystavenia: {datetime.date.today().strftime('%d.%m.%Y')}", ln=True, align='L')
pdf.ln(5)

# Definícia šírok stĺpcov (spolu 275mm pre A4 na šírku)
# Poradie: Názov/Rozmer | Čas | Mat/ks | Koop/ks | Cena/ks | Kusy | Spolu
widths = [80, 30, 35, 35, 35, 20, 40]

# Hlavná hlavička tabuľky
pdf.set_font("Helvetica", "B", 9)
headers = ["Položka (Názov a Rozmer)", "Predik. čas", "Mat. / kus", "Koop. / kus", "Cena / kus", "Ks", "Spolu"]
for i, h in enumerate(headers):
    pdf.cell(widths[i], 8, h, border=1, align='C')
pdf.ln()

def clean(txt):
    t = str(txt)
    reps = {'á':'a','é':'e','í':'i','ó':'o','ú':'u','ý':'y','č':'c','ď':'d','ľ':'l','ň':'n','š':'s','ť':'t','ž':'z','€':'','EUR':''}
    for k, v in reps.items(): t = t.replace(k, v)
    return t.strip()

pdf.set_font("Helvetica", "", 9)
suma_vsetko = 0

for i, p in enumerate(st.session_state.polozky_ponuky):
    # Sčítanie celkovej sumy
    try:
        cista_suma = float(clean(p['Spolu']).replace(',', '.'))
        suma_vsetko += cista_suma
    except: pass

    # Riadok s dátami
    nazov_itemu = f"{item} - {p['Materiál']} ({p['Rozmer (d x l)']})"
    
    pdf.cell(widths[0], 8, clean(nazov_itemu), border=1)
    pdf.cell(widths[1], 8, f"{p.get('predikovany_cas', 0):.2f} min", border=1, align='C')
    pdf.cell(widths[2], 8, f"{p.get('mat_na_kus', 0):.2f} EUR", border=1, align='R')
    pdf.cell(widths[3], 8, f"{p.get('koop_na_kus', 0):.2f} EUR", border=1, align='R')
    pdf.cell(widths[4], 8, clean(p['Cena/ks (M2)']), border=1, align='R')
    pdf.cell(widths[5], 8, str(p['Kusov']), border=1, align='C')
    pdf.cell(widths[6], 8, clean(p['Spolu']), border=1, align='R')
    pdf.ln()

# Výsledná cena cenovej ponuky (Päta)
pdf.ln(5)
pdf.set_font("Helvetica", "B", 11)
pdf.cell(sum(widths[:-1]), 10, "CELKOVÁ SUMA PONUKY (EUR):", border=0, align='R')
pdf.cell(widths[-1], 10, f"{suma_vsetko:.2f} EUR", border=1, align='C')

pdf_output = pdf.output(dest='S').encode('latin-1')
