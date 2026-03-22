import streamlit as st
import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
import os

# --- KONFIGURÁCIA STRÁNKY ---
st.set_page_config(page_title="Mecasys Kalkulačka v2", layout="wide")

# URL na číselník z Google Sheets
URL_HUST = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

# --- FUNKCIE NA NAČÍTANIE DÁT ---

@st.cache_resource
def load_model_assets():
    # Definujeme cesty k súborom v priečinku MECASYS_APP
    model_path = os.path.join('MECASYS_APP', 'finalny_model.json')
    columns_path = os.path.join('MECASYS_APP', 'stlpce_modelu.pkl')
    
    # Kontrola, či súbory existujú, aby aplikácia nespadla s nejasnou chybou
    if not os.path.exists(model_path) or not os.path.exists(columns_path):
        st.error(f"Chýbajú modelové súbory v priečinku MECASYS_APP! Hľadám: {model_path} a {columns_path}")
        st.stop()

    # Načítanie modelu
    model = xgb.XGBRegressor()
    model.load_model(model_path)
    
    # Načítanie zoznamu stĺpcov
    with open(columns_path, 'rb') as f:
        model_columns = pickle.load(f)
        
    return model, model_columns

@st.cache_data
def load_catalog():
    try:
        df = pd.read_csv(URL_HUST)
        # Vyčistenie textov pre správne párovanie (UPPERCASE a bez medzier)
        for col in ['material', 'akost']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.upper()
        return df
    except Exception as e:
        st.error(f"Nepodarilo sa načítať číselník z URL: {e}")
        return pd.DataFrame(columns=['material', 'akost', 'hustota'])

# --- INICIALIZÁCIA ---
model, model_columns = load_model_assets()
df_ciselnik = load_catalog()

# --- POUŽÍVATEĽSKÉ ROZHRANIE ---
st.title("🏭 Mecasys - Predikcia výrobného času")
st.info("Aplikácia používa XGBoost model a dynamický číselník materiálov.")

with st.container():
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📏 Geometria")
        d = st.number_input("Priemer (d) [mm]", min_value=0.1, value=10.0, step=0.1)
        l = st.number_input("Dĺžka (l) [mm]", min_value=0.1, value=50.0, step=1.0)
        pocet_kusov = st.number_input("Počet kusov", min_value=1, value=1, step=1)

    with col2:
        st.subheader("🧪 Materiál a Akosť")
        # Kaskádový výber z Google Sheets
        kat_list = sorted(df_ciselnik['material'].unique()) if not df_ciselnik.empty else []
        vybrany_mat = st.selectbox("Kategória materiálu", kat_list)
        
        akost_list = sorted(df_ciselnik[df_ciselnik['material'] == vybrany_mat]['akost'].unique()) if vybrany_mat else []
        vybrana_akost = st.selectbox("Konkrétna akosť", akost_list)
        
        # Zobrazenie hustoty
        if vybrana_akost:
            hustota = df_ciselnik[(df_ciselnik['material'] == vybrany_mat) & 
                                 (df_ciselnik['akost'] == vybrana_akost)]['hustota'].values[0]
            st.caption(f"ℹ️ Hustota materiálu: {hustota} kg/dm³")

    with col3:
        st.subheader("⚙️ Ostatné")
        narocnost = st.selectbox("Náročnosť výroby", ["NIZKA", "STREDNA", "VYSOKA"])

# --- VÝPOČET A PREDIKCIA ---
st.markdown("---")

if st.button("🚀 Vypočítať predikciu", use_container_width=True):
    # 1. Príprava vstupného riadku (všetko nuly, poradie podľa modelu)
    input_df = pd.DataFrame(0, index=[0], columns=model_columns)
    
    # 2. Vyplnenie numerických hodnôt
    input_df['d'] = d
    input_df['l'] = l
    input_df['pocet_kusov'] = np.log1p(pocet_kusov) # Logaritmická transformácia vstupu
    input_df['plocha_prierezu'] = (np.pi * (d**2)) / 4
    input_df['plocha_plasta'] = np.pi * d * l
    
    # 3. Nastavenie Dummy premenných (One-Hot Encoding)
    def set_dummy(category, value):
        col_name = f"{category}_{str(value).strip().upper()}"
        if col_name in input_df.columns:
            input_df[col_name] = 1

    set_dummy('material', vybrany_mat)
    set_dummy('akost', vybrana_akost)
    set_dummy('narocnost', narocnost)

    # 4. Spustenie predikcie
    try:
        # Predikcia vráti logaritmus času
        pred_log = model.predict(input_df)
        # Transformácia späť na reálne minúty
        vysledny_cas = np.expm1(pred_log)[0]
        
        # 5. Zobrazenie výsledkov
        res_col1, res_col2 = st.columns(2)
        res_col1.metric("Odhadovaný čas (1 ks)", f"{vysledny_cas:.2f} min")
        res_col2.metric("Celkový čas zákazky", f"{(vysledny_cas * pocet_kusov / 60):.2f} hod")
        
        st.success("Predikcia bola úspešne vypočítaná.")
        
    except Exception as e:
        st.error(f"Chyba pri výpočte: {e}")

# --- LADENIE (DEBUG) ---
st.markdown("---")
with st.expander("🔍 Technický detail (Vstupy do modelu)"):
    # Skontrolujeme, či užívateľ už klikol na tlačidlo a vytvoril input_df
    if 'input_df' in locals():
        st.write("Tento riadok bol odoslaný do modelu XGBoost:")
        st.dataframe(input_df)
    else:
        st.info("Zadajte údaje a kliknite na 'Vypočítať predikciu', aby ste videli technické vstupy.")
