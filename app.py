import math
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st
from xgboost import XGBRegressor

# ==========================
# KONŠTANTY
# ==========================

API_URL = "https://script.google.com/macros/s/AKfycbwxzha-vpADu7Q8hRKplV3i0p4Uo22ssaTCRzwTzqOWLNmvWPUJPnnsZbvpf08YRqTmFA/exec"

URL_MATERIAL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv"
URL_LOJALITA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"
URL_KOOP = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv"
URL_HUST = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

M1_MODEL_PATH = "finalny_model.json"
M1_COLS_PATH = "stlpce_modelu.pkl"

M2_MODEL_PATH = "xgb_model_cena.json"
M2_COLS_PATH = "model_columns.pkl"

# ==========================
# LOAD MODELS
# ==========================

@st.cache_resource
def load_m1():
    model = XGBRegressor()
    model.load_model(M1_MODEL_PATH)
    cols = pickle.load(open(M1_COLS_PATH, "rb"))
    return model, cols

@st.cache_resource
def load_m2():
    model = XGBRegressor()
    model.load_model(M2_MODEL_PATH)
    cols = pickle.load(open(M2_COLS_PATH, "rb"))
    return model, cols

# ==========================
# LOAD CSV
# ==========================

@st.cache_data
def load_csv(url):
    df = pd.read_csv(url)
    df.columns = df.columns.astype(str).str.strip()
    return df

# ==========================
# HUSTOTA
# ==========================

def get_hustota(material, akost, hustota_tab):
    m = material.upper()
    a = akost.upper()

    if m in ["OCEĽ", "OCEL"]: return 7900
    if m == "NEREZ": return 8000
    if m == "FAREBNÉ KOVY":
        if a.startswith("3.7"): return 4500
        if a.startswith("3."): return 2900
        if a.startswith("2."): return 9000

    if m == "PLAST":
        row = hustota_tab[hustota_tab["akost"].str.upper() == a]
        if not row.empty:
            return float(row["hustota"].iloc[0])

    raise ValueError("Hustota nenájdená.")

# ==========================
# CENA MATERIÁLU
# ==========================

def compute_material(material_df, akost, d, l):
    df = material_df.copy()
    df["akost_clean"] = df["akost"].str.upper()
    df["d"] = df["d"].astype(float)

    subset = df[df["akost_clean"] == akost.upper()]
    if subset.empty:
        raise ValueError("Akosť nenájdená.")

    exact = subset[subset["d"] == float(d)]
    if not exact.empty:
        cena = float(exact["cena_za_m"].iloc[0])
    else:
        higher = subset[subset["d"] > float(d)].sort_values("d")
        cena = float(higher["cena_za_m"].iloc[0])

    return (l / 1000) * cena

# ==========================
# KOOPERÁCIA
# ==========================

def compute_kooperacia(df, nazov, hmotnost, plocha_plasta, ks):
    if not nazov:
        return 0.0

    row = df[df["nazov"].str.upper() == nazov.upper()].iloc[0]
    tarifa = float(row["tarifa"])
    jednotka = row["jednotka"].lower()
    min_zak = float(row["minimalna_zakazka"])

    if jednotka == "kg":
        odhad = tarifa * hmotnost
    else:
        odhad = (plocha_plasta / 10000) * tarifa

    celkom = odhad * ks
    return max(celkom, min_zak) / ks

# ==========================
# M1 – PREDIKCIA ČASU
# ==========================

def pred_m1(model, cols, d, l, ks, material, akost, narocnost):
    plocha_prierezu = math.pi * d**2 / 4
    plocha_plasta = math.pi * d * l

    df = pd.DataFrame([{
        "d": d,
        "l": l,
        "pocet_kusov_log": np.log1p(ks),
        "plocha_prierezu": plocha_prierezu,
        "plocha_plasta": plocha_plasta,
        "material": material.upper(),
        "akost": akost.upper(),
        "narocnost": narocnost.upper()
    }])

    df = pd.get_dummies(df).reindex(columns=cols, fill_value=0)
    cas = float(np.expm1(model.predict(df)[0]))
    return cas, plocha_prierezu, plocha_plasta

# ==========================
# M2 – PREDIKCIA CENY
# ==========================

def pred_m2(model, cols, cas, hmotnost, plocha_prierezu, vstup, lojalita, ks, krajina):
    df = pd.DataFrame([{
        "cas": cas,
        "hmotnost": hmotnost,
        "plocha_prierezu": plocha_prierezu,
        "vstupne_naklady": vstup,
        "lojalita": lojalita,
        "pocet_kusov_log": np.log1p(ks),
        "krajina": krajina.upper()
    }])

    df = pd.get_dummies(df).reindex(columns=cols, fill_value=0)
    return float(np.expm1(model.predict(df)[0]))

# ==========================
# GOOGLE SCRIPT
# ==========================

def send_to_gs(payload):
    try:
        r = requests.post(API_URL, json=payload, timeout=10)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

# ==========================
# MAIN
# ==========================

def main():
    st.title("Cenová ponuka – predikcia času a ceny")

    # MODELY
    m1, m1_cols = load_m1()
    m2, m2_cols = load_m2()

    # DÁTA
    df_mat = load_csv(URL_MATERIAL)
    df_zak = load_csv(URL_LOJALITA)
    df_koop = load_csv(URL_KOOP)
    df_hust = load_csv(URL_HUST)

    if "kosik" not in st.session_state:
        st.session_state["kosik"] = []

    # HLAVIČKA
    st.sidebar.header("Hlavička CP")
    datum = st.sidebar.date_input("Dátum", value=datetime.today())
    cislo = st.sidebar.text_input("Číslo CP")

    exist = st.sidebar.checkbox("Existujúci zákazník", True)

    if exist:
        zak = st.sidebar.selectbox("Zákazník", df_zak["zakaznik"].unique())
        row = df_zak[df_zak["zakaznik"] == zak].iloc[0]
        lojalita = float(row["lojalita"])
        krajina = row["krajina"]
    else:
        zak = st.sidebar.text_input("Nový zákazník")
        krajina = st.sidebar.text_input("Krajina", "SK")
        lojalita = st.sidebar.number_input("Lojalita", 1.0)

    # POLOŽKA
    st.subheader("Položka")
    item = st.text_input("ITEM")
    d = st.number_input("Priemer d", 1.0)
    l = st.number_input("Dĺžka l", 1.0)
    ks = st.number_input("Počet kusov", 1)
    material = st.selectbox("Materiál", ["OCEĽ", "NEREZ", "PLAST", "FAREBNÉ KOVY"])
    akost = st.text_input("Akosť")
    narocnost = st.selectbox("Náročnosť", ["1", "2", "3", "4", "5"])

    koop = st.checkbox("Kooperácia")
    nazov_koop = st.selectbox("Typ kooperácie", df_koop["nazov"].unique()) if koop else None

    if st.button("Pridať do košíka"):
        h = get_hustota(material, akost, df_hust)
        cas, pp, ppl = pred_m1(m1, m1_cols, d, l, ks, material, akost, narocnost)
        hmotnost = h * (math.pi/4) * (d/1000)**2 * (l/1000)
        naklad_mat = compute_material(df_mat, akost, d, l)
        naklad_koop = compute_kooperacia(df_koop, nazov_koop, hmotnost, ppl, ks)
        vstup = naklad_mat + naklad_koop
        jcena = pred_m2(m2, m2_cols, cas, hmotnost, pp, vstup, lojalita, ks, krajina)
        spolu = jcena * ks

        st.session_state["kosik"].append({
            "item": item,
            "ks": ks,
            "jcena": jcena,
            "spolu": spolu
        })

        st.success("Položka pridaná.")

    # KOŠÍK
    st.subheader("Košík")
    if st.session_state["kosik"]:
        df = pd.DataFrame(st.session_state["kosik"])
        st.dataframe(df)
        st.write("Celkom:", df["spolu"].sum(), "€")

if __name__ == "__main__":
    main()
