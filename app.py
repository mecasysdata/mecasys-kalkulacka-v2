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

URL_MATERIAL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv"
URL_LOJALITA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv"
URL_KOOP = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv"
URL_HUST = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

API_URL = "https://script.google.com/macros/s/AKfycbwxzha-vpADu7Q8hRKplV3i0p4Uo22ssaTCRzwTzqOWLNmvWPUJPnnsZbvpf08YRqTmFA/exec"

# ==========================
# LOAD MODELS
# ==========================

@st.cache_resource
def load_m1():
    model = XGBRegressor()
    model.load_model(M1_MODEL_PATH)
    with open(M1_COLS_PATH, "rb") as f:
        cols = pickle.load(f)
    return model, cols

@st.cache_resource
def load_m2():
    model = XGBRegressor()
    model.load_model(M2_MODEL_PATH)
    with open(M2_COLS_PATH, "rb") as f:
        cols = pickle.load(f)
    return model, cols

@st.cache_data
def load_csv(url):
    df = pd.read_csv(url)
    df.columns = df.columns.astype(str).str.strip()
    return df

# ==========================
# HUSTOTA
# ==========================

def get_hustota(material, akost, hustota_tab):
    m = str(material).strip().upper()
    a = str(akost).strip().upper()

    if m in ["OCEĽ", "OCEL"]:
        return 7900.0
    if m == "NEREZ":
        return 8000.0
    if m in ["FAREBNÉ KOVY", "FAREBNE KOVY"]:
        if a.startswith("3.7"):
            return 4500.0
        if a.startswith("3."):
            return 2900.0
        if a.startswith("2."):
            return 9000.0
    if m == "PLAST":
        df = hustota_tab.copy()
        df["akost_clean"] = df["akost"].astype(str).str.strip().str.upper()
        row = df[df["akost_clean"] == a]
        if not row.empty:
            return float(row["hustota"].iloc[0])

    raise ValueError("Hustota nenájdená pre daný materiál/akosť.")

# ==========================
# CENA MATERIÁLU
# ==========================

def compute_material(material_df, akost, d, l):
    df = material_df.copy()
    df["akost_clean"] = df["akost"].astype(str).str.strip().str.upper()
    df["d"] = df["d"].astype(float)

    a = str(akost).strip().upper()
    subset = df[df["akost_clean"] == a]
    if subset.empty:
        raise ValueError("Akosť materiálu nenájdená v cenníku.")

    exact = subset[subset["d"] == float(d)]
    if not exact.empty:
        cena = float(exact["cena_za_m"].iloc[0])
    else:
        higher = subset[subset["d"] > float(d)].sort_values("d")
        if higher.empty:
            raise ValueError("Pre daný priemer nebola nájdená cena materiálu.")
        cena = float(higher["cena_za_m"].iloc[0])

    return (l / 1000.0) * cena

# ==========================
# KOOPERÁCIA
# ==========================

def compute_kooperacia(df_koop, nazov, hmotnost, plocha_plasta, ks):
    if not nazov:
        return 0.0
    df = df_koop.copy()
    df["nazov_clean"] = df["nazov"].astype(str).str.strip().str.upper()
    name = str(nazov).strip().upper()
    row = df[df["nazov_clean"] == name]
    if row.empty:
        raise ValueError("Kooperácia nenájdená v cenníku.")
    row = row.iloc[0]

    tarifa = float(row["tarifa"])
    jednotka = str(row["jednotka"]).strip().lower()
    min_zak = float(row["minimalna_zakazka"])

    if jednotka == "kg":
        odhad = tarifa * hmotnost
    else:
        odhad = (plocha_plasta / 10000.0) * tarifa

    celkom = odhad * ks
    return max(celkom, min_zak) / ks

# ==========================
# M1 – PREDIKCIA ČASU
# ==========================

def pred_m1(model, cols, d, l, ks, material, akost, narocnost):
    plocha_prierezu = math.pi * d**2 / 4.0
    plocha_plasta = math.pi * d * l

    df = pd.DataFrame([{
        "d": float(d),
        "l": float(l),
        "pocet_kusov_log": float(np.log1p(ks)),
        "plocha_prierezu": float(plocha_prierezu),
        "plocha_plasta": float(plocha_plasta),
        "material": str(material).strip().upper(),
        "akost": str(akost).strip().upper(),
        "narocnost": str(narocnost).strip().upper()
    }])

    df_enc = pd.get_dummies(df).reindex(columns=cols, fill_value=0)
    pred_log = model.predict(df_enc)[0]
    cas_min = float(np.expm1(pred_log))
    return cas_min, plocha_prierezu, plocha_plasta

# ==========================
# M2 – PREDIKCIA CENY
# ==========================

def pred_m2(model, cols, cas, hmotnost, plocha_prierezu, vstup, lojalita, ks, krajina):
    df = pd.DataFrame([{
        "cas": float(cas),
        "hmotnost": float(hmotnost),
        "plocha_prierezu": float(plocha_prierezu),
        "vstupne_naklady": float(vstup),
        "lojalita": float(lojalita),
        "pocet_kusov_log": float(np.log1p(ks)),
        "krajina": str(krajina).strip().upper()
    }])

    df_enc = pd.get_dummies(df).reindex(columns=cols, fill_value=0)
    pred_log = model.predict(df_enc)[0]
    return float(np.expm1(pred_log))

# ==========================
# APPS SCRIPT
# ==========================

def send_to_gs(payload):
    try:
        r = requests.post(API_URL, json=payload, timeout=10)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

# ==========================
# MAIN APP
# ==========================

def main():
    st.set_page_config(page_title="Cenová ponuka – M1 & M2", layout="wide")
    st.title("Cenová ponuka – predikcia času a ceny")

    m1, m1_cols = load_m1()
    m2, m2_cols = load_m2()

    df_mat = load_csv(URL_MATERIAL)
    df_zak = load_csv(URL_LOJALITA)
    df_koop = load_csv(URL_KOOP)
    df_hust = load_csv(URL_HUST)

    if "kosik" not in st.session_state:
        st.session_state["kosik"] = []

    st.sidebar.header("Hlavička CP")
    datum = st.sidebar.date_input("Dátum", value=datetime.today())
    cislo = st.sidebar.text_input("Číslo CP")

    exist = st.sidebar.checkbox("Existujúci zákazník", True)

    if exist:
        zak = st.sidebar.selectbox("Zákazník", df_zak["zakaznik"].astype(str).unique())
        row = df_zak[df_zak["zakaznik"] == zak].iloc[0]
        lojalita = float(row["lojalita"])
        krajina = str(row["krajina"]).strip().upper()
    else:
        zak = st.sidebar.text_input("Nový zákazník")
        krajina = st.sidebar.text_input("Krajina", "SK").strip().upper()
        lojalita = st.sidebar.number_input("Lojalita (1.0 = neutrálny)", min_value=0.0, value=1.0, step=0.1)

    st.subheader("Položka")
    item = st.text_input("ITEM")
    d = st.number_input("Priemer d [mm]", min_value=1.0, value=30.0)
    l = st.number_input("Dĺžka l [mm]", min_value=1.0, value=100.0)
    ks = st.number_input("Počet kusov", min_value=1, value=10)
    material = st.selectbox("Materiál", ["OCEĽ", "NEREZ", "PLAST", "FAREBNÉ KOVY"])
    akost = st.text_input("Akosť")
    narocnost = st.selectbox("Náročnosť", ["1", "2", "3", "4", "5"])

    koop = st.checkbox("Kooperácia")
    nazov_koop = None
    if koop:
        nazov_koop = st.selectbox("Typ kooperácie", df_koop["nazov"].astype(str).unique())

    if st.button("Pridať do košíka"):
        try:
            h = get_hustota(material, akost, df_hust)
            cas, pp, ppl = pred_m1(m1, m1_cols, d, l, ks, material, akost, narocnost)
            hmotnost = h * (math.pi / 4.0) * (d / 1000.0) ** 2 * (l / 1000.0)
            naklad_mat = compute_material(df_mat, akost, d, l)
            naklad_koop = compute_kooperacia(df_koop, nazov_koop, hmotnost, ppl, ks) if koop else 0.0
            vstup = naklad_mat + naklad_koop
            jcena = pred_m2(m2, m2_cols, cas, hmotnost, pp, vstup, lojalita, ks, krajina)
            spolu = jcena * ks

            st.session_state["kosik"].append({
                "datum_cp": str(datum),
                "cislo_cp": cislo,
                "zakaznik": zak,
                "krajina": krajina,
                "lojalita": lojalita,
                "item": item,
                "d": d,
                "l": l,
                "pocet_kusov": ks,
                "material": material,
                "akost": akost,
                "narocnost": narocnost,
                "hustota": h,
                "cas_min": cas,
                "hmotnost": hmotnost,
                "naklad_material": naklad_mat,
                "naklad_kooperacia": naklad_koop,
                "vstupne_naklady": vstup,
                "jednotkova_cena": jcena,
                "cena_polozky": spolu
            })

            st.success("Položka pridaná do košíka.")
        except Exception as e:
            st.error(f"Chyba pri výpočte: {e}")

    st.subheader("Košík")
    if st.session_state["kosik"]:
        df_kosik = pd.DataFrame(st.session_state["kosik"])
        st.dataframe(df_kosik[["item", "pocet_kusov", "jednotkova_cena", "cena_polozky"]])
        st.markdown(f"**Celková cena:** {df_kosik['cena_polozky'].sum():,.2f} €")
    else:
        st.info("Košík je prázdny.")

if __name__ == "__main__":
    main()
