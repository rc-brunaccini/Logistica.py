# %%
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time
import plotly.graph_objects as go
from fpdf import FPDF
import io

# %%
# --- SIDEBAR: INPUT DATI ---
st.sidebar.header("Configurazione Spedizione")

# Inizializzazione session_state per date (mantenuta come nel tuo originale)
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.dep_dt = datetime.now()
    st.session_state.arr_dt = datetime.now() + timedelta(hours=12)

# UNICO FORM PER TUTTI I DATI
with st.sidebar.form(key="global_shipping_form"):
    
    # 1. Dati Spedizione
    st.subheader("📍 Percorso")
    origin_city = st.text_input("Città di Partenza")
    dest_city = st.text_input("Città di Destinazione")
    dest_state = st.selectbox("Stato di arrivo (per War Risk)", 
                                 ["Ucraina", "Iran","Israele", "Siria", "Yemen", "Iraq", "Libano", "Giordania", "Sudan","altro"])
    
    st.markdown("---")

    # 2. Dati Merce
    st.subheader("📦 Dati Merce")
    real_weight = st.number_input("Peso Reale (kg)", min_value=0.0, step=0.1)

    col1, col2, col3 = st.columns(3)
    with col1:
        length = st.number_input("L (cm)", min_value=0)
    with col2:
        width = st.number_input("W (cm)", min_value=0)
    with col3:
        height = st.number_input("H (cm)", min_value=0)

    num_pieces = st.number_input("Numero Pezzi", min_value=1, step=1)

    st.markdown("---")

    # 3. Parametri Tariffari (Spostati dentro il form)
    st.subheader("⚙️ Parametri Tariffari")
    service_type = st.selectbox(
        "Tipo di Servizio",
        ["IATA Standard (1:5000)", "Express Courier (1:6000)", "Custom"]
    )
    
    # Per il divisore custom nel form usiamo un numero fisso o lo definiamo fuori
    custom_div = st.number_input("Eventuale Divisore Custom (se selezionato sopra)", value=5000)

    st.markdown("---")

    # 4. Dati Orari e Data
    st.subheader("🕒 Operazioni Volo")
    departure_date = st.date_input("Data di Decollo", value=st.session_state.dep_dt.date())
    departure_time = st.time_input("Ora di Decollo", value=st.session_state.dep_dt.time())
    
    st.markdown("---")
    
    arrival_date = st.date_input("Data di Atterraggio", value=st.session_state.arr_dt.date())
    arrival_time = st.time_input("Ora di Atterraggio", value=st.session_state.arr_dt.time())

    # UNICO BOTTONE DI INVIO
    submit_button = st.form_submit_button(label="🚀 ELABORA QUOTAZIONE")

# --- LOGICA FUORI DAL FORM ---
# Impostazione dinamica del divisore basata sulla scelta nel form
if service_type == "IATA Standard (1:5000)":
    dim_divisor = 5000
elif service_type == "Express Courier (1:6000)":
    dim_divisor = 6000
else:
    dim_divisor = custom_div


# --- CORPO PRINCIPALE: RIEPILOGO ---
st.header("Riepilogo Dati Inseriti")

col_main1, col_main2 = st.columns(2)

with col_main1:
    st.info(f"**Tratta:** {origin_city} ➔ {dest_city}")
    st.write(f"**Stato Destinazione:** {dest_state}")
    st.write(f"**Partenza:** {departure_date} alle {departure_time}")
    st.write(f"**Arrivo:** {arrival_date} alle {arrival_time}")

with col_main2:
    # Esempio di calcolo logistico (Peso Volumetrico standard 1:6000)
    volumetric_weight = (length * width * height) / dim_divisor * num_pieces
    st.success(f"**Peso Reale Totale:** {real_weight} kg")
    st.write(f"**Pezzi:** {num_pieces}")
    st.write(f"**Peso Volumetrico Stimato:** {volumetric_weight:.2} kg")

# Bottone per elaborazione (es. War Risk)
if st.button("Calcola War Risk e Quotazione"):
    # Qui puoi inserire la logica per il calcolo del rischio
    st.warning(f"Calcolo in corso per la zona di rischio: {dest_state}...")

# dati live in alto
@st.cache_data(ttl=3600) # Cache di 1 ora per non sovraccaricare le API e velocizzare l'app
def get_market_intelligence():
    try:
        # Scarichiamo solo l'ultimo prezzo disponibile
        data = yf.download("BZ=F", period="1d", progress=False)
        
        # Estraiamo il prezzo (gestendo il nuovo formato di yfinance)
        # .iloc[-1] prende l'ultima riga, .values[0] evita errori di formato
        current_price = float(data['Close'].iloc[-1].values[0])
        
        # Logica BAF rapida
        baf_index = 15.5 if current_price > 80 else 12.0
        
        return round(current_price, 2), baf_index
    except:
        # Se Yahoo fa i capricci, spariamo un prezzo fisso per non bloccare l'app
        return 85.0, 15.0

# --- HEADER: DATI LIVE ---
st.markdown("### 📊 Market Intelligence & Fuel Analysis")

jet_price, baf_value = get_market_intelligence()

# Layout a 3 colonne per un look da Bloomberg Terminal
m_col1, m_col2, m_col3 = st.columns(3)

with m_col1:
    st.metric(
        label="Brent Crude Oil (Ref. Jet Fuel)", 
        value=f"${jet_price} / Bbl")
  
with m_col2:
    # Mostriamo il BAF
    st.metric(
        label="Indice BAF applicato", 
        value=f"{baf_value}%",
        delta="Fuel Surcharge"
    )

with m_col3:
    # tasso di cambio EUR/USD
    try:
        forex = yf.download("EURUSD=X", period="1d", progress=False)
        fx_val = round(forex['Close'].iloc[-1], 4)
        st.metric(label="Cambio EUR/USD", value=fx_val)
    except:
        st.metric(label="Cambio EUR/USD", value="N/D")

st.divider()


# %%
@st.cache_data(show_spinner="Calcolo coordinate in corso...")
def get_precise_route_data(origin_city, dest_city):
    geolocator = Nominatim(user_agent="Logistics_Professional_App_ID_9872", timeout=10) # User agent necessario per policy Nominatim
    
    try:
        # Recupero coordinate città di partenza
        loc_origin = geolocator.geocode(origin_city)
        # Piccolo delay per rispettare le policy di Nominatim (1 richiesta al sec)
        time.sleep(1.2) 
        # Recupero coordinate città di destinazione
        loc_dest = geolocator.geocode(dest_city)
        
        if loc_origin and loc_dest:
            coords_1 = (loc_origin.latitude, loc_origin.longitude)
            coords_2 = (loc_dest.latitude, loc_dest.longitude)
            
            # Calcolo distanza reale in KM
            distanza_reale = round(geodesic(coords_1, coords_2).km, 2)
            
            # Logica Direzionalità basata su Longitudine (Semplificata: Ovest -> Est)
            # In logica aerea, Headhaul è solitamente verso i grandi hub di produzione/consumo
            direzionalita = "Headhaul" if loc_dest.longitude > loc_origin.longitude else "Backhaul"
            
            return distanza_reale, direzionalita, loc_origin, loc_dest
        else:
            return None, None, None, None
    except Exception as e:
        st.error(f"Errore Geografico: {e}")
        return None, None, None, None

# --- VISUALIZZAZIONE NELLA MAIN PAGE ---

if origin_city and dest_city:
    dist_km, direz, latlon_org, latlon_dest = get_precise_route_data(origin_city, dest_city)
    
    if dist_km and latlon_org and latlon_dest:
        st.divider()
        
        # Creiamo le due colonne
        col_sinistra, col_destra = st.columns([1, 1.5]) 

        with col_sinistra:
            st.metric("Distanza Geodetica", f"{dist_km} km")
            st.write(f"**🛫 Partenza:** {latlon_org.address}")
            st.write(f"**🛬 Arrivo:** {latlon_dest.address}")
            st.info(f"Rotta: {direz}")

        with col_destra:
            try:
                # 1. Coordinate per la rotazione
                c_lat = float(latlon_org.latitude + latlon_dest.latitude) / 2
                c_lon = float(latlon_org.longitude + latlon_dest.longitude) / 2

                # 2. Definizione della figura
                fig = go.Figure(go.Scattergeo(
                    lat = [latlon_org.latitude, latlon_dest.latitude],
                    lon = [latlon_org.longitude, latlon_dest.longitude],
                    mode = 'lines+markers',
                    line = dict(width = 3, color = 'red'),
                    marker = dict(size = 12, color = ['red', 'red']),
                ))

                # 3. Impostazioni del globo (PROIEZIONE ORTOGRAFICA)
                fig.update_layout(
                    height=450,
                    margin=dict(l=0, r=0, t=0, b=0),
                    geo = dict(
                        projection_type = 'orthographic', # Questa la rende una sfera 3D
                        showland = True,
                        landcolor = "Azure",
                        showocean = True,
                        oceancolor = "Lightblue",
                        showcountries = True,
                        # Ruota il globo verso la rotta
                        projection_rotation = dict(lon=c_lon, lat=c_lat, roll=0)
                    )
                )

                # Mostra il grafico
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Errore tecnico nella mappa: {e}")
    else:
        st.warning("Inserisci città valide per vedere la mappa.")

st.divider()

# %%
# --- LOGICA DI CALCOLO COSTI ---

import math

def calculate_chargeable_weight(real_w, vol_w):
    # 1. Prendo il maggiore tra reale e volumetrico
    target_w = max(real_w, vol_w)
    
    # 2. Arrotondamento IATA: scatti di 0.5 kg verso l'alto
    # Esempio: 12.1 -> 12.5 | 12.6 -> 13.0
    return math.ceil(target_w * 2) / 2

def estimate_final_costs(chargeable_weight, baf_pct, country):
    # Costi unitari
    base_rate_per_kg = 2.50
    min_freight = 90.0       # <--- AGGIUNTO: Minimo di nolo base
    security_per_kg = 0.15 
    handling_fix = 50.0      
    docs_fix = 35.0          
    war_risk_per_kg = 0.50 if country in ["Ucraina", "Iran","Israele", "Siria", "Yemen", "Iraq", "Libano", "Giordania", "Sudan"] else 0.05
    
    # CALCOLO NOLO BASE (con controllo del minimo)
    nolo_calcolato = chargeable_weight * base_rate_per_kg
    nolo_base = max(nolo_calcolato, min_freight) # Se il calcolo è < 90, applico 90
    
    # IL BAF si applica sul nolo effettivamente pagato
    fuel_surcharge = nolo_base * (baf_pct / 100)
    
    # Security e War Risk si applicano SEMPRE sul peso tassabile reale
    security_war = chargeable_weight * (security_per_kg + war_risk_per_kg)
    
    total = nolo_base + fuel_surcharge + security_war + handling_fix + docs_fix
    
    breakdown = pd.DataFrame({
        "Voce di Costo": ["Nolo Base", "Fuel Surcharge (BAF)", "Security & War Risk", "Handling Terminal", "Documentazione"],
        "Importo ($)": [
            round(nolo_base, 2), 
            round(fuel_surcharge, 2), 
            round(security_war, 2), 
            round(handling_fix, 2), 
            round(docs_fix, 2)
        ]
    })
    
    return total, breakdown
    

# 1. Ricalcolo preciso del peso volumetrico (1:6000)
# Nota: Usiamo float() per sicurezza se gli input arrivano da widget numerici
vol_weight = (float(length) * float(width) * float(height)) / dim_divisor * int(num_pieces)

# 2. Applichiamo la funzione corretta con arrotondamento IATA (0.5 kg)
chargeable_w = calculate_chargeable_weight(real_weight, vol_weight)

# 3. Calcolo costi finali con la nuova logica (Minimi inclusi)
total_est, df_costs = estimate_final_costs(chargeable_w, baf_value, dest_state)

# --- STILIZZAZIONE E LAYOUT ---
st.header("💰 Business Intelligence Tool")

# Prepariamo i dati per il Break-even
prezzo_break_even = total_est / real_weight if real_weight > 0 else 0
# Creiamo un range di prezzi attorno al break-even
tariffe_test = np.linspace(prezzo_break_even * 0.5, prezzo_break_even * 2, 50)
ricavi = tariffe_test * real_weight
costi_fissi = np.full(len(tariffe_test), total_est)

col_res1, col_res2 = st.columns([1,1]) # Bilanciamo le larghezze

with col_res1:
    st.subheader("📉 Incidenza Costi per kg Reale")
    
    # 1. Prepariamo i dati: calcoliamo quanto ogni voce pesa su 1 kg di merce fisica
    df_incidenza = df_costs.copy()
    # Usiamo real_weight per l'analisi di efficienza (costo effettivo per kg spedito)
    df_incidenza["$/kg"] = df_incidenza["Importo ($)"] / real_weight if real_weight > 0 else 0
    
    # 2. Creazione del grafico a barre orizzontali
    fig_inc = go.Figure(go.Bar(
        x=df_incidenza["$/kg"],
        y=df_incidenza["Voce di Costo"],
        orientation='h',
        marker=dict(
            color='#3498db',
            line=dict(color='#2980b9', width=1)
        ),
        text=[f"${x:.2f}/kg" for x in df_incidenza["$/kg"]],
        textposition='outside',
        cliponaxis=False # Evita che il testo venga tagliato
    ))
    
    # 3. Styling del layout
    fig_inc.update_layout(
        height=400,
        margin=dict(l=10, r=40, t=20, b=10), # Margine destro ampio per le etichette
        xaxis_title="Impatto economico per kg ($)",
        yaxis=dict(autorange="reversed"), # Nolo in alto, Documenti in basso
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            showgrid=True,
            gridcolor='lightgray',
            zeroline=True,
            zerolinecolor='black'
        )
    )
    
    st.plotly_chart(fig_inc, use_container_width=True)

with col_res2:
    st.subheader("📊 Analisi Struttura Costi")
    
    nomi_voci = list(df_costs["Voce di Costo"])
    valori_voci = list(df_costs["Importo ($)"])
    
    fig_wf = go.Figure(go.Waterfall(
        orientation = "v",
        measure = ["relative"] * len(valori_voci) + ["total"],
        x = nomi_voci + ["TOTALE"],
        y = valori_voci + [0],
        text = [f"${x}" for x in valori_voci] + [f"${total_est:.2f}"],
        textposition = "outside",
        # Colori moderni (Azzurro per incrementi, Blu Scuro per totale)
        increasing = {"marker":{"color": "#3498db"}},
        totals = {"marker":{"color": "#2c3e50"}},
        connector = {"line":{"color":"#bdc3c7", "width":2}},
    ))

    fig_wf.update_layout(
        margin=dict(l=10, r=10, t=50, b=10),
        height=400,
        plot_bgcolor='white',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(tickangle=-45) # Incliniamo i nomi per non sovrapporli
    )
    st.plotly_chart(fig_wf, use_container_width=True)

st.divider()

# Tabella dettagliata - Uso st.dataframe per una visualizzazione più moderna rispetto a st.table
st.subheader("📋 Breakdown Preventivo")
st.dataframe(df_costs, use_container_width=True, hide_index=True)

# Banner Finale
# Nota logistica: Il costo al kg si calcola solitamente sul peso tassabile (chargeable) 
# per analisi interna, ma per il cliente si usa il reale per mostrare l'incidenza.
costo_al_kg = total_est / real_weight if real_weight > 0 else 0

st.success(f"""
### **TOTALE STIMATO SPEDIZIONE: $ {total_est:,.2f}**
---
* **Costo medio per kg reale:** $ {costo_al_kg:.2f}
* **Peso Tassabile applicato:** {chargeable_w:.2f} kg
* **Note:** Include Fuel Surcharge ({baf_value}%) e War Risk per {dest_state}.
""")

#calcolo SLA

# --- SEZIONE 3: PIANIFICAZIONE LOGISTICA DINAMICA (SLA) ---
st.header("🕒 Pianificazione Logistica Integrata (SLA)")

# 1. Definizione dinamica dei tempi in base all'importanza dell'aeroporto
# Hub Grandi: 12h cutoff / 18h svincolo
# Aeroporti Standard: 6h cutoff / 10h svincolo
HUBS_GRANDI = ["Milano", "Roma", "New York", "Londra", "Francoforte", "Parigi", "Shanghai", "Tokyo"]

def get_sla_params(city_name):
    if any(hub.lower() in city_name.lower() for hub in HUBS_GRANDI):
        return 12, 18  # Aeroporto congestionato/grande
    else:
        return 6, 10   # Aeroporto secondario/veloce

# Recuperiamo i tempi in base alle città già definite negli input precedenti
cutoff, availability = get_sla_params(origin_city) if origin_city else (8, 12)
_, availability = get_sla_params(dest_city) if dest_city else (8, 12)

try:
    # 2. Conversione degli input sidebar (departure_date, departure_time, etc.)
    partenza_dt = datetime.combine(departure_date, departure_time)
    arrivo_dt = datetime.combine(arrival_date, arrival_time)

    # 3. CALCOLO LIMITI OPERATIVI DINAMICI
    limite_consegna = partenza_dt - timedelta(hours=cutoff)
    pronto_ritiro = arrivo_dt + timedelta(hours=availability)

    # 4. VISUALIZZAZIONE
    st.info(f"💡 **Logistica Dinamica:** Parametri impostati per aeroporto di classe {'Hub' if cutoff == 12 else 'Standard'}.")
    
    col_log1, col_log2 = st.columns(2)

    with col_log1:
        st.markdown(f"#### 📤 Accettazione ({origin_city})")
        st.warning(f"""
        **CONSEGNARE ENTRO IL:** 📅 {limite_consegna.strftime('%d/%m/%Y')}  
        ⏰ ore **{limite_consegna.strftime('%H:%M')}**
        
        *(Cut-off applicato: {cutoff} ore)*
        """)

    with col_log2:
        st.markdown(f"#### 📥 Disponibilità ({dest_city})")
        st.success(f"""
        **PRONTO PER IL RITIRO DAL:** 📅 {pronto_ritiro.strftime('%d/%m/%Y')}  
        ⏰ ore **{pronto_ritiro.strftime('%H:%M')}**
        
        *(Svincolo applicato: {availability} ore)*
        """)

except Exception as e:
    st.error(f"Errore nel calcolo delle tempistiche: {e}")


# generazione pdf 

def generate_pdf(df_costs, total_est, origin, dest, weight_data, sla_data, baf_val, dest_state):
    class PDF(FPDF):
        def header(self):
            # Fascia blu in alto
            self.set_fill_color(44, 62, 80) # Blu scuro professionale
            self.rect(0, 0, 210, 40, 'F')
            self.set_text_color(255, 255, 255)
            self.set_font("Arial", "B", 20)
            self.cell(0, 20, "AIR FREIGHT QUOTATION", ln=True, align='C')
            self.set_font("Arial", "", 10)
            self.cell(0, -5, f"Data documento: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
            self.ln(20)

        def footer(self):
            self.set_y(-25)
            self.set_font("Arial", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, "Documento generato da Logistics BI Tool - Brunaccini Riccardo", 0, 0, 'L')
            self.cell(0, 10, f"Pagina {self.page_no()}", 0, 0, 'R')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- 1. DETTAGLI SPEDIZIONE ---
    pdf.set_y(50)
    pdf.set_text_color(44, 62, 80)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. DETTAGLI TRATTA E CARICO", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y()) # Linea divisoria
    pdf.ln(2)

    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)
    
    # Tabella info base
    col_width = 95
    pdf.cell(col_width, 7, f"Partenza: {origin}", 0)
    pdf.cell(col_width, 7, f"Destinazione: {dest} ({dest_state})", 0, ln=True)
    pdf.cell(col_width, 7, f"Peso Reale: {weight_data['real']} kg", 0)
    pdf.cell(col_width, 7, f"Peso Tassabile: {weight_data['chargeable']} kg", 0, ln=True)
    pdf.ln(5)

    # --- 2. BREAKDOWN COSTI (TABELLA STYLE) ---
    pdf.set_text_color(44, 62, 80)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "2. ANALISI ECONOMICA", ln=True)
    pdf.set_font("Arial", "B", 10)
    
    # Header Tabella
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(130, 10, " Descrizione Voce", 0, 0, 'L', fill=True)
    pdf.cell(60, 10, "Importo ($) ", 0, 1, 'R', fill=True)
    
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)
    
    for index, row in df_costs.iterrows():
        # Riga alternata grigio chiaro per leggibilità
        fill = True if index % 2 == 0 else False
        if fill: pdf.set_fill_color(248, 249, 250)
        pdf.cell(130, 8, f" {row['Voce di Costo']}", 0, 0, 'L', fill=fill)
        pdf.cell(60, 8, f"{row['Importo ($)']:,.2f}  ", 0, 1, 'R', fill=fill)

    # Totale evidenziato
    pdf.ln(2)
    pdf.set_fill_color(44, 62, 80)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(130, 12, " TOTALE STIMATO (USD)", 0, 0, 'L', fill=True)
    pdf.cell(60, 12, f"$ {total_est:,.2f}  ", 0, 1, 'R', fill=True)
    
    # --- 3. SLA & LOGISTICA ---
    pdf.ln(10)
    pdf.set_text_color(44, 62, 80)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "3. TEMPISTICHE OPERATIVE (SLA)", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)
    
    # Box per SLA
    pdf.set_fill_color(232, 244, 253)
    pdf.rect(10, pdf.get_y(), 190, 25, 'F')
    pdf.set_y(pdf.get_y() + 5)
    pdf.cell(10) # Indentazione
    pdf.cell(0, 7, f"LATEST DELIVERY (Cut-off): {sla_data['cutoff']}", ln=True)
    pdf.cell(10)
    pdf.cell(0, 7, f"ESTIMATED AVAILABILITY (Pickup): {sla_data['pickup']}", ln=True)

    # --- NOTE FINALI ---
    pdf.ln(15)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(100, 100, 100)
    disclaimer = f"Nota: La quotazione include Fuel Surcharge ({baf_val}%) e War Risk surcharge. Prezzi soggetti a verifica disponibilità voli."
    pdf.multi_cell(0, 5, disclaimer)

    # Output
    pdf_out = pdf.output(dest='S')
    return bytes(pdf_out, 'latin-1') if isinstance(pdf_out, str) else bytes(pdf_out)


# --- TASTO DI DOWNLOAD AGGIORNATO ---
st.divider()
st.subheader("🖨️ Esporta Documentazione Professionale")

try:
    # 1. Prepariamo i dati necessari (assicurandoci che siano formattati correttamente)
    w_info = {
        "real": float(real_weight), 
        "vol": float(vol_weight), 
        "chargeable": float(chargeable_w)
    }
    
    s_info = {
        "cutoff": limite_consegna.strftime('%d/%m/%Y %H:%M'),
        "pickup": pronto_ritiro.strftime('%d/%m/%Y %H:%M')
    }

    # 2. CHIAMATA ALLA FUNZIONE: Qui passiamo tutti gli argomenti richiesti
    # Abbiamo aggiunto baf_value e dest_state alla fine
    pdf_data = generate_pdf(
        df_costs, 
        total_est, 
        origin_city, 
        dest_city, 
        w_info, 
        s_info, 
        baf_value,   # <-- Argomento mancante 1
        dest_state   # <-- Argomento mancante 2
    )
    
    # 3. Bottone Streamlit
    st.download_button(
        label="🚀 Scarica Preventivo PDF Premium",
        data=pdf_data,
        file_name=f"Quote_{dest_city.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

except Exception as e:
    # Se qualcosa va storto (es. città non inserite), mostriamo un avviso pulito
    st.warning("Completa l'inserimento dei dati per generare il PDF professionale.")
    # Debug opzionale: st.error(f"Dettaglio errore: {e}")




st.write("Developed by Brunaccini Riccardo")
