import streamlit as st
import pandas as pd
from datetime import date
import re
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

# 8. PREMENNÁ - Materiál
seznam_materialov = sorted(df_materialy['material'].unique())
material = st.selectbox("Materiál", options=seznam_materialov)

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
