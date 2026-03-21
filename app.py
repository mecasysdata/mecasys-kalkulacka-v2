import math
import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st
from xgboost import XGBRegressor

# ==========================
# MODELY – CESTY K SÚBOROM
# ==========================

M1_MODEL_PATH = "finalny_model.json"
M1_COLS_PATH = "stlpce_modelu.pkl"

M2_MODEL_PATH = "xgb_model_cena.json"
M2_COLS_PATH = "model_columns.pkl"

# ==========================
# GOOGLE SHEETS – URL ADRESY
# ==========================

URLS = {
    "databaza_ponuk": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=0&single=true&output=csv",
    "kooperacie_cennik": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1180392224&single=true&output=csv",
    "material_akost_hustota": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv",
    "material_cena": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=901617097&single=true&output=csv",
    "zakaznik_lojalita": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=324957857&single=true&output=csv",
}

# Apps Script endpoint (databaza_ponuk)
API_URL = "https://script.google.com/macros/s/AKfycbwxzha-vpADu7Q8hRKplV3i0p4Uo22ssaTCRzwTzqOWLNmvWPUJPnnsZbvpf08YRqTmFA/exec"
# ==========================
# NAČÍTANIE MODELOV A DÁT
# ==========================

@st.cache_resource
def load_m1_model():
    model = XGBRegressor()
    model.load_model(M1_MODEL_PATH)
    with open(M1_COLS_PATH, "rb") as f:
        cols = pickle.load(f)
    return model, cols


@st.cache_resource
def load_m2_model():
    model = XGBRegressor()
    model.load_model(M2_MODEL_PATH)
    with open(M2_COLS_PATH, "rb") as f:
        cols = pickle.load(f)
    return model, cols


@st.cache_data
def load_csv(url_key: str) -> pd.DataFrame:
    url = URLS[url_key]
    df = pd.read_csv(url)
    df.columns = df.columns.astype(str).str.strip()
    return df


@st.cache_data
def load_material_cena():
    return load_csv("material_cena")


@st.cache_data
def load_zakaznik_lojalita():
    return load_csv("zakaznik_lojalita")


@st.cache_data
def load_kooperacie():
    return load_csv("kooperacie_cennik")


@st.cache_data
def load_material_akost_hustota():
    return load_csv("material_akost_hustota")
# ==========================
# HUSTOTA
# ==========================

def get_hustota(material: str, akost: str, hustota_tab: pd.DataFrame | None = None) -> float:
    m = str(material).strip().upper()
    a = str(akost).strip().upper()

    if m in ["OCEĽ", "OCEL"]:
        return 7900.0
    if m == "NEREZ":
        return 8000.0
    if m == "PLAST":
        if hustota_tab is not None:
            df = hustota_tab.copy()
            df["akost_clean"] = df["akost"].astype(str).str.strip().str.upper()
            row = df[df["akost_clean"] == a]
            if not row.empty:
                return float(row["hustota"].iloc[0])
        raise ValueError("Pre PLAST nebola nájdená hustota pre danú akosť.")
    if m in ["FAREBNÉ KOVY", "FAREBNE KOVY"]:
        if a.startswith("3.7"):
            return 4500.0
        if a.startswith("3."):
            return 2900.0
        if a.startswith("2."):
            return 9000.0
        raise ValueError("Pre FAREBNÉ KOVY nebola nájdená hustota pre danú akosť.")
    raise ValueError(f"Neznámy materiál: {material}")


# ==========================
# CENA MATERIÁLU
# ==========================

def get_material_price_per_meter(material_cena_df: pd.DataFrame, akost: str, d: float) -> float:
    a = str(akost).strip().upper()
    df = material_cena_df.copy()
    df["akost_clean"] = df["akost"].astype(str).str.strip().str.upper()
    df["d"] = df["d"].astype(float)

    subset = df[df["akost_clean"] == a]
    if subset.empty:
        raise ValueError(f"Pre akosť {akost} nebola nájdená cena materiálu.")

    exact = subset[subset["d"] == float(d)]
    if not exact.empty:
        return float(exact["cena_za_m"].iloc[0])

    higher = subset[subset["d"] > float(d)].sort_values("d")
    if not higher.empty:
        return float(higher["cena_za_m"].iloc[0])

    raise ValueError(f"Pre akosť {akost} a priemer {d} nebola nájdená cena materiálu.")


def compute_naklad_material(material_cena_df: pd.DataFrame, akost: str, d: float, l: float) -> float:
    cena_per_m = get_material_price_per_meter(material_cena_df, akost, d)
    return (l / 1000.0) * cena_per_m


# ==========================
# KOOPERÁCIA
# ==========================

def get_kooperacia_row(kooperacie_df: pd.DataFrame, nazov_kooperacie: str) -> pd.Series:
    df = kooperacie_df.copy()
    df["nazov_clean"] = df["nazov"].astype(str).str.strip().str.upper()
    name = str(nazov_kooperacie).strip().upper()
    row = df[df["nazov_clean"] == name]
    if row.empty:
        raise ValueError(f"Kooperácia '{nazov_kooperacie}' nebola nájdená v cenníku.")
    return row.iloc[0]


def compute_naklad_kooperacie(
    kooperacie_df: pd.DataFrame,
    nazov_kooperacie: str,
    hmotnost: float,
    plocha_plasta: float,
    pocet_kusov: int
) -> float:
    row = get_kooperacia_row(kooperacie_df, nazov_kooperacie)
    tarifa = float(row["tarifa"])
    jednotka = str(row["jednotka"]).strip().lower()
    min_zakazka = float(row["minimalna_zakazka"])

    if jednotka == "kg":
        odhad_na_kus = tarifa * hmotnost
    elif jednotka in ["dm2", "dm²"]:
        odhad_na_kus = (plocha_plasta / 10000.0) * tarifa
    else:
        raise ValueError(f"Neznáma jednotka kooperácie: {jednotka}")

    celkom = odhad_na_kus * pocet_kusov

    if celkom < min_zakazka:
        return min_zakazka / pocet_kusov
    return odhad_na_kus
# ==========================
# MODEL M1 – PREDIKCIA ČASU
# ==========================

def predict_cas_m1(m1_model, m1_cols, d, l, pocet_kusov, material, akost, narocnost):
    # Geometria
    plocha_prierezu = (math.pi * (d ** 2)) / 4.0
    plocha_plasta = math.pi * d * l
    pocet_kusov_log = np.log1p(pocet_kusov)

    # Čistenie kategórií
    material_clean = str(material).strip().upper()
    akost_clean = str(akost).strip().upper()
    narocnost_clean = str(narocnost).strip().upper()

    # Vstupný dataframe
    df_m1 = pd.DataFrame([{
        "d": float(d),
        "l": float(l),
        "pocet_kusov_log": float(pocet_kusov_log),
        "plocha_prierezu": float(plocha_prierezu),
        "plocha_plasta": float(plocha_plasta),
        "material": material_clean,
        "akost": akost_clean,
        "narocnost": narocnost_clean
    }])

    # One-hot encoding
    df_m1_enc = pd.get_dummies(df_m1)

    # Zoradenie stĺpcov podľa tréningového modelu
    df_m1_enc = df_m1_enc.reindex(columns=m1_cols, fill_value=0)

    # Predikcia log(čas)
    pred_log = m1_model.predict(df_m1_enc)[0]

    # Odlogaritmovanie
    cas_min = float(np.expm1(pred_log))

    return cas_min, plocha_prierezu, plocha_plasta
# ==========================
# MODEL M2 – PREDIKCIA JEDNOTKOVEJ CENY
# ==========================

def predict_jednotkova_cena_m2(
    m2_model,
    m2_cols,
    cas_min,
    hmotnost,
    plocha_prierezu,
    vstupne_naklady,
    lojalita,
    pocet_kusov,
    krajina
):
    # Log-transformovaný počet kusov
    pocet_kusov_log = np.log1p(pocet_kusov)

    # Čistenie kategórie krajiny
    krajina_clean = str(krajina).strip().upper()

    # Vstupný dataframe
    df_m2 = pd.DataFrame([{
        "cas": float(cas_min),
        "hmotnost": float(hmotnost),
        "plocha_prierezu": float(plocha_prierezu),
        "vstupne_naklady": float(vstupne_naklady),
        "lojalita": float(lojalita),
        "pocet_kusov_log": float(pocet_kusov_log),
        "krajina": krajina_clean
    }])

    # One-hot encoding
    df_m2_enc = pd.get_dummies(df_m2)

    # Zoradenie stĺpcov podľa tréningového modelu
    df_m2_enc = df_m2_enc.reindex(columns=m2_cols, fill_value=0)

    # Predikcia log(jednotkovej ceny)
    pred_log = m2_model.predict(df_m2_enc)[0]

    # Odlogaritmovanie
    jednotkova_cena = float(np.expm1(pred_log))

    return jednotkova_cena
# ==========================
# ZÁPIS DO APPS SCRIPT (AUTO Z KOŠÍKA)
# ==========================

def send_to_apps_script(payload: dict):
    try:
        resp = requests.post(API_URL, json=payload, timeout=10)
        return resp.status_code, resp.text
    except Exception as e:
        return None, str(e)


# ==========================
# STREAMLIT APLIKÁCIA – ZAČIATOK
# ==========================

def main():
    st.set_page_config(page_title="Cenová ponuka – M1 & M2", layout="wide")
    st.title("Cenová ponuka – predikcia času a ceny")

    # Načítanie modelov a dát
    m1_model, m1_cols = load_m1_model()
    m2_model, m2_cols = load_m2_model()
    material_cena_df = load_material_cena()
    zakaznik_df = load_zakaznik_lojalita()
    kooperacie_df = load_kooperacie()
    hustota_tab = load_material_akost_hustota()

    # Košík
    if "kosik" not in st.session_state:
        st.session_state["kosik"] = []

    # HLAVIČKA CP
    st.sidebar.header("Hlavička CP")
    datum_cp = st.sidebar.date_input("Dátum CP", value=datetime.today())
    cislo_cp = st.sidebar.text_input("Číslo CP", value="")
    existujuci_zakaznik = st.sidebar.checkbox("Existujúci zákazník", value=True)

    if existujuci_zakaznik:
        moznosti_zakaznikov = zakaznik_df["zakaznik"].astype(str).unique().tolist()
        zakaznik = st.sidebar.selectbox("Zákazník", moznosti_zakaznikov)
        info = get_zakaznik_info(zakaznik_df, zakaznik)
        if info is None:
            st.sidebar.error("Zákazník nebol nájdený v tabuľke lojalít.")
            lojalita = 1.0
            krajina = "SK"
        else:
            lojalita, krajina = info
    else:
        zakaznik = st.sidebar.text_input("Názov nového zákazníka")
        krajina = st.sidebar.text_input("Krajina (napr. SK, CZ, DE)").strip().upper() or "SK"
        lojalita = st.sidebar.number_input("Lojalita (0.5 = neutrálny)", min_value=0.0, value=1.0, step=0.1)
    # ==========================
    # DEFINÍCIA POLOŽKY
    # ==========================

    st.markdown("## Definícia položky")

    col1, col2, col3 = st.columns(3)
    with col1:
        item_nazov = st.text_input("Názov položky (ITEM)")
        d = st.number_input("Priemer d [mm]", min_value=0.0, value=30.0, step=1.0)
        l = st.number_input("Dĺžka l [mm]", min_value=0.0, value=100.0, step=1.0)

    with col2:
        pocet_kusov = st.number_input("Počet kusov", min_value=1, value=10, step=1)
        material = st.selectbox("Materiál", ["OCEĽ", "NEREZ", "PLAST", "FAREBNÉ KOVY"])
        akost = st.text_input("Akosť (napr. 11SMNPB30, 1.4301, 3.7165)")

    with col3:
        narocnost = st.selectbox("Náročnosť (1–5)", ["1", "2", "3", "4", "5"])
        ma_kooperaciu = st.checkbox("Kooperácia", value=False)
        nazov_kooperacie = None
        if ma_kooperaciu:
            moznosti_koop = kooperacie_df["nazov"].astype(str).unique().tolist()
            nazov_kooperacie = st.selectbox("Typ kooperácie", moznosti_koop)

    # ==========================
    # PRIDAŤ POLOŽKU DO KOŠÍKA
    # ==========================

    if st.button("Pridať položku do košíka"):
        try:
            # Hustota
            hustota = get_hustota(material, akost, hustota_tab)

            # Predikcia času M1 + geometria
            cas_min, plocha_prierezu, plocha_plasta = predict_cas_m1(
                m1_model, m1_cols, d, l, pocet_kusov, material, akost, narocnost
            )

            # Hmotnosť
            hmotnost = hustota * (math.pi / 4.0) * (d / 1000.0) ** 2 * (l / 1000.0)

            # Cena materiálu
            naklad_material = compute_naklad_material(material_cena_df, akost, d, l)

            # Kooperácia
            if ma_kooperaciu and nazov_kooperacie:
                naklad_kooperacie = compute_naklad_kooperacie(
                    kooperacie_df, nazov_kooperacie, hmotnost, plocha_plasta, pocet_kusov
                )
            else:
                naklad_kooperacie = 0.0

            # Vstupné náklady
            vstupne_naklady = naklad_material + naklad_kooperacie

            # Predikcia jednotkovej ceny M2
            jednotkova_cena = predict_jednotkova_cena_m2(
                m2_model,
                m2_cols,
                cas_min,
                hmotnost,
                plocha_prierezu,
                vstupne_naklady,
                lojalita,
                pocet_kusov,
                krajina
            )

            # Cena položky spolu
            cena_polozky = jednotkova_cena * pocet_kusov

            # Uloženie položky
            polozka = {
                "datum_cp": str(datum_cp),
                "cislo_cp": cislo_cp,
                "zakaznik": zakaznik,
                "krajina": krajina,
                "lojalita": lojalita,
                "item_nazov": item_nazov,
                "d": d,
                "l": l,
                "pocet_kusov": pocet_kusov,
                "material": material,
                "akost": akost,
                "narocnost": narocnost,
                "hustota": hustota,
                "plocha_prierezu": plocha_prierezu,
                "plocha_plasta": plocha_plasta,
                "hmotnost": hmotnost,
                "cas_min": cas_min,
                "naklad_material": naklad_material,
                "naklad_kooperacie": naklad_kooperacie,
                "vstupne_naklady": vstupne_naklady,
                "jednotkova_cena": jednotkova_cena,
                "cena_polozky": cena_polozky,
                "ma_kooperaciu": ma_kooperaciu,
                "nazov_kooperacie": nazov_kooperacie
            }

            st.session_state["kosik"].append(polozka)
            st.success("Položka bola pridaná do košíka.")

        except Exception as e:
            st.error(f"Nastala chyba pri výpočte: {e}")
    # ==========================
    # KOŠÍK – ZOBRAZENIE A EXPORT
    # ==========================

    st.markdown("## Košík položiek")

    if st.session_state["kosik"]:
        df_kosik = pd.DataFrame(st.session_state["kosik"])

        # Zobrazenie pre používateľa
        df_zobraz = df_kosik[[
            "item_nazov",
            "pocet_kusov",
            "jednotkova_cena",
            "cena_polozky"
        ]].copy()

        df_zobraz.rename(columns={
            "item_nazov": "Položka",
            "pocet_kusov": "Počet kusov",
            "jednotkova_cena": "Jednotková cena [€]",
            "cena_polozky": "Cena položky spolu [€]"
        }, inplace=True)

        st.dataframe(df_zobraz, use_container_width=True)

        # Celková cena CP
        celkova_cena = df_kosik["cena_polozky"].sum()
        st.markdown(f"### Celková cena CP: **{celkova_cena:,.2f} €**")

        # Export celého košíka do Apps Script
        if st.button("Odoslať celý košík do databázy (Apps Script)"):
            payload = {
                "cislo_cp": cislo_cp,
                "datum_cp": str(datum_cp),
                "zakaznik": zakaznik,
                "krajina": krajina,
                "lojalita": lojalita,
                "polozky": st.session_state["kosik"],
                "celkova_cena": celkova_cena
            }

            status, text = send_to_apps_script(payload)

            if status == 200 and text.strip() == "OK":
                st.success("Dáta boli úspešne odoslané do databaza_ponuk.")
            else:
                st.error("Chyba pri odosielaní do databázy.")
                st.write("Odpoveď servera:", text)

    else:
        st.info("Košík je zatiaľ prázdny.")


    # ==========================================
    # 4️⃣ Zápis do databaza_ponuk cez Apps Script – manuálny formulár
    # ==========================================

    st.header("4️⃣ Zápis do databaza_ponuk cez Apps Script")

    st.subheader("Formulár na zápis jednej položky")

    with st.form("formular_zapis"):
        datum_cp_f = st.date_input("Dátum CP (formulár)", value=datetime.today())
        cislo_cp_f = st.text_input("Číslo CP (formulár)")
        zakaznik_f = st.text_input("Zákazník")
        krajina_f = st.text_input("Krajina")
        lojalita_f = st.text_input("Lojalita")
        item_f = st.text_input("ITEM")
        material_f = st.text_input("Materiál")
        akost_f = st.text_input("Akosť")
        d_f = st.number_input("d (formulár)", step=0.1)
        l_f = st.number_input("l (formulár)", step=0.1)
        hustota_f = st.number_input("Hustota", step=0.01)
        hmotnost_f = st.number_input("Hmotnosť", step=0.01)
        narocnost_f = st.text_input("Náročnosť")
        j_cena_materialu_f = st.number_input("J.cena materiálu", step=0.01)
        naklad_material_f = st.number_input("Náklad materiál", step=0.01)
        naklad_kooperacia_f = st.number_input("Náklad kooperácia", step=0.01)
        vstupne_naklady_f = st.number_input("Vstupné náklady", step=0.01)
        cas_min_f = st.number_input("Čas (min)", step=1)
        jednotkova_cena_f = st.number_input("Jednotková cena", step=0.01)
        pocet_kusov_f = st.number_input("Počet kusov (formulár)", step=1)
        cena_polozky_spolu_f = st.number_input("Cena položky spolu", step=0.01)

        submit_zapis = st.form_submit_button("Odoslať do databázy")

    if submit_zapis:
        data = {
            "datum_cp": str(datum_cp_f),
            "cislo_cp": cislo_cp_f,
            "zakaznik": zakaznik_f,
            "krajina": krajina_f,
            "lojalita": lojalita_f,
            "item": item_f,
            "material": material_f,
            "akost": akost_f,
            "d": d_f,
            "l": l_f,
            "hustota": hustota_f,
            "hmotnost": hmotnost_f,
            "narocnost": narocnost_f,
            "j_cena_materialu": j_cena_materialu_f,
            "naklad_material": naklad_material_f,
            "naklad_kooperacia": naklad_kooperacia_f,
            "vstupne_naklady": vstupne_naklady_f,
            "cas_min": cas_min_f,
            "jednotkova_cena": jednotkova_cena_f,
            "pocet_kusov": pocet_kusov_f,
            "cena_polozky_spolu": cena_polozky_spolu_f
        }

        r = requests.post(API_URL, json=data)

        if r.text.strip() == "OK":
            st.success("Úspešne zapísané do databaza_ponuk!")
        else:
            st.error("Chyba pri zápise")
            st.write("Odpoveď servera:", r.text)
# ==========================
# UKONČENIE APLIKÁCIE
# ==========================

if __name__ == "__main__":
    main()
