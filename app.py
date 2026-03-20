import streamlit as st
import pandas as pd
from xgboost import XGBRegressor
import pickle
import requests

st.set_page_config(page_title="TEST – Overenie dát, modelov a zápisu", layout="wide")

st.title("TEST APLIKÁCIE – KROK 1")
st.write("Overíme načítanie Google Sheets, modelov, vstupov a zápis do databázy.")

# -----------------------------------------
# Cesty k modelom a vstupným súborom
# -----------------------------------------
M1_MODEL_PATH = "MECASYS_APP/finalny_model.json"
M1_COLUMNS_PATH = "MECASYS_APP/stlpce_modelu.pkl"

M2_MODEL_PATH = "MECASYS_APP/xgb_model_cena.json"
M2_COLUMNS_PATH = "MECASYS_APP/model_columns.pkl"

# -----------------------------------------
# Google Sheets URL
# -----------------------------------------
URLS = {
    "databaza_ponuk": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=0&single=true&output=csv",
    "kooperacie_cennik": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv",
    "material_akost_hustota": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv",
    "material_cena": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv",
    "zakaznik_lojalita": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv",
}

# -----------------------------------------
# Funkcia na analýzu vstupov modelu
# -----------------------------------------
def analyze_input_columns(df, column_list, title):
    st.subheader(f"🔍 Analýza vstupov pre {title}")

    info = []

    for col in column_list:
        if col not in df.columns:
            info.append({
                "Premenná": col,
                "Typ": "❌ CHÝBA",
                "Dtype": "-",
                "Ukážka hodnôt": "-"
            })
            continue

        dtype = df[col].dtype

        if dtype == "object":
            col_type = "KATEGORICKÁ"
            unique_vals = df[col].unique()[:10]
        else:
            col_type = "NUMERICKÁ"
            unique_vals = "-"

        info.append({
            "Premenná": col,
            "Typ": col_type,
            "Dtype": str(dtype),
            "Ukážka hodnôt": unique_vals
        })

    st.dataframe(pd.DataFrame(info))


# -----------------------------------------
# 1️⃣ Test načítania Google Sheets
# -----------------------------------------
st.header("1️⃣ Test načítania Google Sheets")

loaded_sheets = {}

for name, url in URLS.items():
    st.subheader(f"Sheet: **{name}**")
    try:
        df = pd.read_csv(url)
        loaded_sheets[name] = df

        st.success(f"Načítané OK – {len(df)} riadkov")
        st.write("### Stĺpce:", list(df.columns))
        st.write("### Prvých 5 riadkov:")
        st.dataframe(df.head())
        st.write("### Typy stĺpcov:")
        st.write(df.dtypes)

    except Exception as e:
        st.error(f"Chyba pri načítaní {name}: {e}")

df_main = loaded_sheets.get("databaza_ponuk")

# -----------------------------------------
# 2️⃣ Test načítania modelu M1
# -----------------------------------------
st.header("2️⃣ Test načítania modelu M1 (čas)")

try:
    m1 = XGBRegressor()
    m1.load_model(M1_MODEL_PATH)
    st.success("Model M1 načítaný!")
except Exception as e:
    st.error(f"Chyba pri načítaní modelu M1: {e}")

try:
    with open(M1_COLUMNS_PATH, "rb") as f:
        cols_m1 = pickle.load(f)
    st.success("Stĺpce M1 načítané!")
    st.write(cols_m1)
except Exception as e:
    st.error(f"Chyba pri načítaní stĺpcov M1: {e}")

if df_main is not None:
    analyze_input_columns(df_main, cols_m1, "Model M1 (čas)")

# -----------------------------------------
# 3️⃣ Test načítania modelu M2
# -----------------------------------------
st.header("3️⃣ Test načítania modelu M2 (cena)")

try:
    m2 = XGBRegressor()
    m2.load_model(M2_MODEL_PATH)
    st.success("Model M2 načítaný!")
except Exception as e:
    st.error(f"Chyba pri načítaní modelu M2: {e}")

try:
    with open(M2_COLUMNS_PATH, "rb") as f:
        cols_m2 = pickle.load(f)
    st.success("Stĺpce M2 načítané!")
    st.write(cols_m2)
except Exception as e:
    st.error(f"Chyba pri načítaní stĺpcov M2: {e}")

if df_main is not None:
    analyze_input_columns(df_main, cols_m2, "Model M2 (cena)")

# -----------------------------------------
# 4️⃣ Zápis do databaza_ponuk cez Apps Script
# -----------------------------------------
st.header("4️⃣ Zápis do databaza_ponuk cez Apps Script")

API_URL = "https://script.google.com/macros/s/AKfycbwxzha-vpADu7Q8hRKplV3i0p4Uo22ssaTCRzwTzqOWLNmvWPUJPnnsZbvpf08YRqTmFA/exec"

st.subheader("Formulár na zápis")

with st.form("formular_zapis"):
    datum_cp = st.date_input("Dátum CP")
    cislo_cp = st.text_input("Číslo CP")
    zakaznik = st.text_input("Zákazník")
    krajina = st.text_input("Krajina")
    lojalita = st.text_input("Lojalita")
    item = st.text_input("ITEM")
    material = st.text_input("Materiál")
    akost = st.text_input("Akosť")
    d = st.number_input("d", step=0.1)
    l = st.number_input("l", step=0.1)
    hustota = st.number_input("Hustota", step=0.01)
    hmotnost = st.number_input("Hmotnosť", step=0.01)
    narocnost = st.text_input("Náročnosť")
    j_cena_materialu = st.number_input("J.cena materiálu", step=0.01)
    naklad_material = st.number_input("Náklad materiál", step=0.01)
    naklad_kooperacia = st.number_input("Náklad kooperácia", step=0.01)
    vstupne_naklady = st.number_input("Vstupné náklady", step=0.01)
    cas_min = st.number_input("Čas (min)", step=1)
    jednotkova_cena = st.number_input("Jednotková cena", step=0.01)
    pocet_kusov = st.number_input("Počet kusov", step=1)
    cena_polozky_spolu = st.number_input("Cena položky spolu", step=0.01)

    submit_zapis = st.form_submit_button("Odoslať do databázy")

if submit_zapis:
    data = {
        "datum_cp": str(datum_cp),
        "cislo_cp": cislo_cp,
        "zakaznik": zakaznik,
        "krajina": krajina,
        "lojalita": lojalita,
        "item": item,
        "material": material,
        "akost": akost,
        "d": d,
        "l": l,
        "hustota": hustota,
        "hmotnost": hmotnost,
        "narocnost": narocnost,
        "j_cena_materialu": j_cena_materialu,
        "naklad_material": naklad_material,
        "naklad_kooperacia": naklad_kooperacia,
        "vstupne_naklady": vstupne_naklady,
        "cas_min": cas_min,
        "jednotkova_cena": jednotkova_cena,
        "pocet_kusov": pocet_kusov,
        "cena_polozky_spolu": cena_polozky_spolu
    }

    r = requests.post(API_URL, json=data)

    if r.text == "OK":
        st.success("Úspešne zapísané do databaza_ponuk!")
    else:
        st.error("Chyba pri zápise")
        st.write("Odpoveď servera:", r.text)

# -----------------------------------------
# 5️⃣ Testovací zápis
# -----------------------------------------
st.header("5️⃣ Testovací zápis")

if st.button("Odoslať testovací riadok"):
    test_data = {
        "datum_cp": "2024-03-20",
        "cislo_cp": "TEST-001",
        "zakaznik": "Eva",
        "krajina": "SK",
        "lojalita": "Áno",
        "item": "ITEM-TEST",
        "material": "Oceľ",
        "akost": "A",
        "d": 10,
        "l": 200,
        "hustota": 7.85,
        "hmotnost": 15.7,
        "narocnost": "stredná",
        "j_cena_materialu": 5.20,
        "naklad_material": 81.64,
        "naklad_kooperacia": 12.00,
        "vstupne_naklady": 3.50,
        "cas_min": 12,
        "jednotkova_cena": 9.80,
        "pocet_kusov": 100,
        "cena_polozky_spolu": 980
    }

    r = requests.post(API_URL, json=test_data)

    if r.text == "OK":
        st.success("Testovací riadok úspešne zapísaný!")
    else:
        st.error("Test zlyhal")
        st.write(r.text)
