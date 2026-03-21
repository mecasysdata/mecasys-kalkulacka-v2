import math
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st
from xgboost import XGBRegressor

# ==========================
# CESTY K MODELom
# ==========================

M1_MODEL_PATH = "finalny_model.json"
M1_COLS_PATH = "stlpce_modelu.pkl"

M2_MODEL_PATH = "xgb_model_cena.json"
M2_COLS_PATH = "model_columns.pkl"

# ==========================
# GOOGLE SHEETS
# ==========================

URLS = {
    "material_cena": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv",
    "zakaznik_lojalita": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv",
    "kooperacie": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv",
    "hustota": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv",
}

API_URL = "https://script.google.com/macros/s/AKfycbwxzha-vpADu7Q8hRKplV3i0p4Uo22ssaTCRzwTzqOWLNmvWPUJPnnsZbvpf08YRqTmFA/exec"

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

@st.cache_data
def load_csv(key):
    df = pd.read_csv(URLS[key])
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
    df["akost"] = df["akost"].str.upper()
    df["d"] = df["d"].astype(float)

    subset = df[df["akost"] == akost.upper()]
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
# APPS SCRIPT
# ==========================

def send_to_gs(data):
    try:
        r = requests.post(API_URL, json=data, timeout=10)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

# ==========================
# MAIN APP
# ==========================

def main():
    st.title("Cenová ponuka – M1 & M2")

    m1, m1_cols = load_m1()
    m2, m2_cols = load_m2()

    df_mat = load_csv("material_cena")
    df_zak = load_csv("zakaznik_lojalita")
    df_koop = load_csv("kooperacie")
    df_hust = load_csv("hustota")

    if "kosik" not in st.session_state:
        st.session_state["kosik"] = []

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

    st.subheader("Položka")
    item = st.text_input("ITEM")
    d = st.number_input("Priemer d", 1.0)
    l = st.number_input("Dĺžka l", 1.0)
    ks = st.number_input("Počet kusov", 1)
    material = st.selectbox("Materiál", ["OCEĽ", "NEREZ", "PLAST", "FAREBNÉ KOVY"])
    akost = st.text_input("Akosť")
    narocnost = st.selectbox("Náročnosť", ["1", "2", "3", "4", "5"])

    koop = st.checkbox("Kooperácia")
    if koop:
        nazov_koop = st.selectbox("Typ kooperácie", df_koop["nazov"].unique())
    else:
        nazov_koop = None

    if st.button("Pridať do košíka"):
        hustota = get_hustota(material, akost, df_hust)
        cas, plocha_prierezu, plocha_plasta = pred_m1(m1, m1_cols, d, l, ks, material, akost, narocnost)
        hmotnost = hustota * (math.pi/4) * (d/1000)**2 * (l/1000)
        naklad_mat = compute_material(df_mat, akost, d, l)
        naklad_koop = compute_kooperacia(df_koop, nazov_koop, hmotnost, plocha_plasta, ks) if koop else 0
        vstup = naklad_mat + naklad_koop
        jcena = pred_m2(m2, m2_cols, cas, hmotnost, plocha_prierezu, vstup, lojalita, ks, krajina)
        cena_spolu = jcena * ks

        st.session_state["kosik"].append({
            "item": item,
            "ks": ks,
            "jcena": jcena,
            "spolu": cena_spolu
        })

        st.success("Položka pridaná.")

    st.subheader("Košík")
    if st.session_state["kosik"]:
        df = pd.DataFrame(st.session_state["kosik"])
        st.dataframe(df)
        st.write("Celkom:", df["spolu"].sum(), "€")

        if st.button("Odoslať do databázy"):
            status, text = send_to_gs({
                "cislo_cp": cislo,
                "datum_cp": str(datum),
                "zakaznik": zak,
                "krajina": krajina,
                "lojalita": lojalita,
                "polozky": st.session_state["kosik"],
                "celkova_cena": df["spolu"].sum()
            })
            st.write("Odpoveď:", text)

if __name__ == "__main__":
    main()
