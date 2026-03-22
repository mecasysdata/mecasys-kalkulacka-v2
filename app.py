import streamlit as st
import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
import os

# --- KONFIGURÁCIA ---
st.set_page_config(page_title="Mecasys Kalkulačka v2", layout="wide")

# URL na číselník z Google Sheets (Materiál, Akosť, Hustota)
URL_HUST = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRfPBZ4TCpQyiqybU0ADu3AMwHCi2qOKifQAOnnTWnorVNJ1SVxtN6zJzXthOxCVwtXWp__Bp_-nto0/pub?gid=1281008948&single=true&output=csv"

@st.cache_resource
def load_model_assets():
    """Načíta model a zoznam stĺpcov z priečinka MECASYS_APP"""
    model_path = os.path.join('MECASYS_APP', 'finalny_model.json')
    columns_path = os.path.join('MECASYS_APP', 'stlpce_modelu.pkl')
    
    if not os.path.exists(model_path) or not os.path.exists(columns_path):
        st.error(f"Chýbajú súbory v MECASYS_APP! Hľadám: {model_path} a {columns_path}")
        st.stop()

    model = xgb.XGBRegressor()
    model.load_model(model_path)
    
    with open(columns_path, 'rb') as f:
        model_columns = pickle.load(f)
    return model, model_columns

@st.cache_data
def load_catalog():
    """Načíta dáta z Google Sheets a vyčistí ich pre párovanie"""
    try:
        df = pd.read_csv(URL_HUST)
        for col in ['material', 'akost']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.upper()
        return df
    except Exception as e:
        st.error(f"Chyba pri načítaní číselníka: {e}")
        return pd.DataFrame()

# Inicializácia aplikácie
model, model_columns = load_model_assets()
df_ciselnik = load_catalog()

# --- POUŽÍVATEĽSKÉ ROZHRANIE ---
st.title("🏭 Mecasys - Výrobná kalkulačka")
st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📏 Geometria")
    d = st.number_input("Priemer (d) [mm]", min_value=0.0, value=10.0, step=0.1)
    l = st.number_input("Dĺžka (l) [mm]", min_value=0.0, value=50.0, step=0.1)
    pocet_kusov = st.number_input("Počet kusov [ks]", min_value=1, value=1, step=1)

with col2:
    st.subheader("🧪 Materiál")
    if not df_ciselnik.empty:
        kat_list = sorted(df_ciselnik['material'].unique())
        vybrany_mat = st.selectbox("Kategória materiálu", kat_list)
        
        akost_list = sorted(df_ciselnik[df_ciselnik['material'] == vybrany_mat]['akost'].unique())
        vybrana_akost = st.selectbox("Konkrétna akosť", akost_list)
        
        # Zobrazenie hustoty pre info
        hustota = df_ciselnik[(df_ciselnik['material'] == vybrany_mat) & 
                             (df_ciselnik['akost'] == vybrana_akost)]['hustota'].values[0]
        st.caption(f"Hustota: {hustota} kg/dm³")
    else:
        st.warning("Číselník nie je dostupný.")

with col3:
    st.subheader("⚙️ Výroba")
    # Narocnost je kategoricka premenna (1-5)
    narocnost = st.selectbox("Náročnosť (1-5)", [1, 2, 3, 4, 5])

# --- VÝPOČET A PREDIKCIA ---
st.markdown("---")

if st.button("🚀 Vypočítať predikciu času", use_container_width=True):
    # 1. Príprava vstupného riadku s nulami v presnom poradí podľa .pkl
    input_df = pd.DataFrame(0.0, index=[0], columns=model_columns)
    
    # 2. Numerické vstupy (Priradenie podľa názvu stĺpca)
    input_df['d'] = float(d)
    input_df['l'] = float(l)
    input_df['pocet_kusov'] = np.log1p(float(pocet_kusov))
    input_df['plocha_prierezu'] = (np.pi * (float(d)**2)) / 4
    input_df['plocha_plasta'] = np.pi * float(d) * float(l)
    
    # 3. Kategorické vstupy (Dummy encoding / One-Hot)
    # Tato funkcia zapne '1' v stĺpci, ktorý zodpovedá vybranej kategórii
    def set_dummy(prefix, value):
        col_name = f"{prefix}_{value}"
        if col_name in input_df.columns:
            input_df[col_name] = 1.0

    set_dummy('material', vybrany_mat)
    set_dummy('akost', vybrana_akost)
    set_dummy('narocnost', narocnost)

    # 4. Samotná predikcia
    try:
        # Model vráti logaritmus času
        pred_log = model.predict(input_df)
        # Transformácia späť na reálne minúty
        vysledok_min = np.expm1(pred_log)[0]
        
        # Zobrazenie výsledkov
        res_col1, res_col2 = st.columns(2)
        res_col1.metric("Odhadovaný čas (1 ks)", f"{vysledok_min:.2f} min")
        res_col2.metric("Celkový čas zákazky", f"{(vysledok_min * pocet_kusov / 60):.2f} hod")
        
    except Exception as e:
        st.error(f"Chyba pri výpočte: {e}")

# --- TECHNICKÝ DETAIL (Zobrazí sa až po kliknutí na tlačidlo) ---
if 'input_df' in locals():
    with st.expander("🔍 Technický detail (Vstupy do modelu)"):
        st.write("Dáta odoslané do modelu (overte, či sú v správnych stĺpcoch jednotky):")
        st.dataframe(input_df)
