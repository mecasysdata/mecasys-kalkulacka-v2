import streamlit as st
import pandas as pd
from xgboost import XGBRegressor
import pickle

st.set_page_config(page_title="TEST – Overenie dát a modelov", layout="wide")

st.title("TEST APLIKÁCIE – KROK 1")
st.write("Overíme načítanie Google Sheets, modelov a vstupných premenných.")

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

# Vyberieme hlavný dataset pre analýzu vstupov
df_main = loaded_sheets.get("databaza_ponuk")

if df_main is None:
    st.error("❌ Hlavný sheet 'databaza_ponuk' sa nepodarilo načítať. Nie je možné analyzovať vstupy.")
else:
    st.success("Hlavný dataset načítaný – môžeme analyzovať vstupy modelov.")

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

# Analýza vstupov M1
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

# Analýza vstupov M2
if df_main is not None:
    analyze_input_columns(df_main, cols_m2, "Model M2 (cena)")
