# -----------------------------------------
# 5️⃣ Zápis do databaza_ponuk cez Apps Script
# -----------------------------------------

st.header("5️⃣ Zápis do databaza_ponuk cez Apps Script")

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
# 6️⃣ Testovací zápis – automatický
# -----------------------------------------

st.header("6️⃣ Testovací zápis – automatický")

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
