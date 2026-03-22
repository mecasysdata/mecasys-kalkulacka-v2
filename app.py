with eco2:
    st.write("**Kooperácia**")
    
    # --- INTELIGENTNÝ FILTER KOOPERÁCIÍ ---
    # Vyberieme len tie druhy kooperácií, ktoré majú v tabuľke priradený aktuálny materiál (v_mat)
    dostupne_koop = df_koop_cennik[df_koop_cennik['material'] == v_mat]['druh'].unique().tolist()
    
    # Používateľ uvidí len relevantné možnosti pre daný materiál
    v_koop = st.selectbox(
        "Druh kooperácie", 
        ["Bez kooperácie"] + sorted(dostupne_koop),
        help=f"Zobrazujú sa len kooperácie dostupné pre {v_mat}"
    )
    
    vyp_koop_ks = 0.0
    if v_koop != "Bez kooperácie":
        # Tu už vieme, že riadok existuje, lebo sme ho predtým vyfiltrovali
        mk = df_koop_cennik[(df_koop_cennik['druh'] == v_koop) & (df_koop_cennik['material'] == v_mat)]
        
        if not mk.empty:
            row = mk.iloc[0]
            tarifa = safe_num(row.get('tarifa', 0))
            min_z = safe_num(row.get('minimalna_zakazka', row.get('min_zakazka', 0)))
            jedn = str(row.get('jednotka', 'ks')).lower()
            
            # Logika výpočtu (kg vs dm2 vs ks)
            if 'kg' in jedn:
                zaklad = tarifa * hmotnost
            elif 'dm2' in jedn:
                zaklad = tarifa * (plocha_plasta / 10000)
            else:
                zaklad = tarifa
                
            vyp_koop_ks = max(zaklad, min_z / pocet_kusov)
            st.caption(f"Info: {tarifa} €/{jedn} (Min: {min_z} €)")

    naklad_koop_ks = st.number_input("Kooperácia na kus [€]", value=vyp_koop_ks, format="%.3f")
