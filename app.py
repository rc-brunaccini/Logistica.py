# %%
import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time
import plotly.graph_objects as go
from fpdf import FPDF
import io

# %%
# sidebar per gli input
st.set_page_config(page_title="Gestione Spedizioni", layout="wide")

st.title("✈️ Calcolo e Gestione Spedizioni")

# --- SIDEBAR: INPUT DATI ---
st.sidebar.header("Configurazione Spedizione")

# Dati Spedizione
with st.sidebar.form(key="città"):
    st.subheader("📍 Percorso")
    origin_city = st.text_input("Città di Partenza")
    dest_city = st.text_input("Città di Destinazione")
    dest_state = st.selectbox("Stato di arrivo (per War Risk)", 
                                 ["Ucraina", "Iran","Israele", "Siria", "Yemen", "Iraq", "Libano", "Giordania", "Sudan","altro"])
    
    submit_button = st.form_submit_button(label="Calcola Rotta")
st.sidebar.markdown("---")

# Dati Merce
with st.sidebar.form(key="merce"):
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
    submit_button = st.form_submit_button(label="Calcola Dati Merce")

# decidi la IATA applicata 

st.sidebar.subheader("⚙️ Parametri Tariffari")
service_type = st.sidebar.selectbox(
    "Tipo di Servizio",
    ["IATA Standard (1:5000)", "Express Courier (1:6000)", "Custom"]
)

# Impostazione dinamica del divisore
if service_type == "IATA Standard (1:5000)":
    dim_divisor = 5000
elif service_type == "Express Courier (1:6000)":
    dim_divisor = 6000
else:
    dim_divisor = st.sidebar.number_input("Inserisci Divisore Custom", value=5000)

st.sidebar.markdown("---")

# Dati Orari e Data

# Questo blocco serve a definire i valori iniziali che NON cambieranno più da soli
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.dep_dt = datetime.now()
    st.session_state.arr_dt = datetime.now() + timedelta(hours=12)

with st.sidebar.form(key="Date"):
    st.subheader("🕒 Operazioni Volo")

    departure_date = st.date_input(
    "Data di Decollo", 
    value=st.session_state.dep_dt.date()
)
    departure_time = st.time_input(
    "Ora di Decollo", 
    value=st.session_state.dep_dt.time()
)

    st.sidebar.markdown("---")
    

# ATTERRAGGIO
    arrival_date = st.date_input(
    "Data di Atterraggio", 
    value=st.session_state.arr_dt.date()
)
    arrival_time = st.time_input(
    "Ora di Atterraggio", 
    value=st.session_state.arr_dt.time()
)
    submit_button = st.form_submit_button(label="Calcola Data e Ora")


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
    volumetric_weight = (length * width * height) / 6000 * num_pieces
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
        col_sinistra, col_destra = st.columns([1, 1]) # [1, 1] assicura metà e metà

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

# --- VISUALIZZAZIONE MAIN PAGE: COSTI ---
st.header("💰 Analisi Costi e Riepilogo Finale")

# 1. Ricalcolo preciso del peso volumetrico (1:6000)
# Nota: Usiamo float() per sicurezza se gli input arrivano da widget numerici
vol_weight = (float(length) * float(width) * float(height)) / 6000 * int(num_pieces)

# 2. Applichiamo la funzione corretta con arrotondamento IATA (0.5 kg)
chargeable_w = calculate_chargeable_weight(real_weight, vol_weight)

# 3. Calcolo costi finali con la nuova logica (Minimi inclusi)
total_est, df_costs = estimate_final_costs(chargeable_w, baf_value, dest_state)

col_res1, col_res2 = st.columns(2)

with col_res1:
    st.subheader("⚖️ Analisi Peso")
    st.write(f"Peso Reale: **{real_weight:.2f} kg**")
    st.write(f"Peso Volumetrico: **{vol_weight:.2f} kg**")
    # Messaggio info che chiarisce l'arrotondamento
    st.info(f"**Peso Tassabile (IATA): {chargeable_w:.2f} kg**")

with col_res2:
    # Grafico a torta per il breakdown dei costi
    import plotly.express as px
    
    fig = px.pie(df_costs, values='Importo ($)', names='Voce di Costo', 
                 title="Distribuzione Costi", hole=0.4)
    fig.update_layout(showlegend=False, height=300)
    st.plotly_chart(fig, use_container_width=True)

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

# --- FUNZIONE GENERAZIONE PDF (VERSIONE DEFINITIVA) ---
def generate_pdf(df_costs, total_est, origin, dest, weight_data, sla_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    # Intestazione
    pdf.cell(190, 10, "Preventivo Spedizione Aerea", ln=True, align='C')
    pdf.ln(10)
    
    # 1. Dettagli Percorso
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "1. Dettagli Percorso", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(190, 7, f"Da: {origin}", ln=True)
    pdf.cell(190, 7, f"A: {dest}", ln=True)
    pdf.ln(5)
    
    # 2. Analisi Pesi
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "2. Analisi Pesi", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(190, 7, f"Peso Reale: {weight_data['real']:.2f} kg", ln=True)
    pdf.cell(190, 7, f"Peso Volumetrico: {weight_data['vol']:.2f} kg", ln=True)
    pdf.cell(190, 7, f"Peso Tassabile (IATA): {weight_data['chargeable']:.2f} kg", ln=True)
    pdf.ln(5)
    
    # 3. Breakdown Costi
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "3. Breakdown Costi", ln=True)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(120, 8, "Voce di Costo", 1)
    pdf.cell(70, 8, "Importo ($)", 1, ln=True)
    
    pdf.set_font("Arial", "", 10)
    for index, row in df_costs.iterrows():
        pdf.cell(120, 8, str(row['Voce di Costo']), 1)
        pdf.cell(70, 8, f"{row['Importo ($)']:,.2f}", 1, ln=True)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(120, 10, "TOTALE STIMATO", 1)
    pdf.cell(70, 10, f"$ {total_est:,.2f}", 1, ln=True)
    pdf.ln(5)
    
    # 4. SLA Logistica
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "4. Tempistiche Operative (SLA)", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(190, 7, f"Cut-off (Consegna entro): {sla_data['cutoff']}", ln=True)
    pdf.cell(190, 7, f"Svincolo (Disponibile dal): {sla_data['pickup']}", ln=True)
    
    # ESTRAZIONE BINARIA PULITA
    # Usiamo 'S' e poi forziamo la conversione in bytes standard
    pdf_out = pdf.output(dest='S')
    if isinstance(pdf_out, str):
        return bytes(pdf_out, 'latin-1')
    return bytes(pdf_out) # Se è bytearray, lo trasforma in bytes puri

# --- TASTO DI DOWNLOAD ---
st.divider()
st.subheader("🖨️ Esporta Documentazione")

# Generazione e bottone
try:
    # Preparazione dati last-minute
    w_info = {"real": float(real_weight), "vol": float(vol_weight), "chargeable": float(chargeable_w)}
    s_info = {
        "cutoff": limite_consegna.strftime('%d/%m/%Y %H:%M'),
        "pickup": pronto_ritiro.strftime('%d/%m/%Y %H:%M')
    }

    pdf_data = generate_pdf(df_costs, total_est, origin_city, dest_city, w_info, s_info)
    
    st.download_button(
        label="📥 Scarica Preventivo PDF",
        data=pdf_data,
        file_name=f"Preventivo_{dest_city.replace(' ', '_')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
except Exception as e:
    st.error(f"Errore: {e}")

import plotly.graph_objects as go
import numpy as np

# --- STILIZZAZIONE E LAYOUT ---
st.header("💰 Business Intelligence Tool")

# Prepariamo i dati per il Break-even
prezzo_break_even = total_est / real_weight if real_weight > 0 else 0
# Creiamo un range di prezzi attorno al break-even
tariffe_test = np.linspace(prezzo_break_even * 0.5, prezzo_break_even * 2, 50)
ricavi = tariffe_test * real_weight
costi_fissi = np.full(len(tariffe_test), total_est)

col_res1, col_res2, col_res3 = st.columns([0.6, 1.2,1]) # Bilanciamo le larghezze

with col_res1:
    st.subheader("⚖️ Analisi Peso")
    st.write(f"Peso Reale: **{real_weight:.2f} kg**")
    st.write(f"Peso Volumetrico: **{vol_weight:.2f} kg**")
    # Messaggio info che chiarisce l'arrotondamento
    st.info(f"**Peso Tassabile (IATA): {chargeable_w:.2f} kg**")

with col_res2:
    st.subheader("📈 Analisi Margine e Profitto")
    
    fig_be = go.Figure()

    # Area del Profitto (Verde) e Perdita (Rossa)
    fig_be.add_trace(go.Scatter(
        x=tariffe_test, y=ricavi,
        line=dict(color='#2ecc71', width=4),
        name='Ricavo Totale',
        fill='tonexty', # Questo colora l'area tra le linee
        fillcolor='rgba(46, 204, 113, 0.2)' 
    ))

    fig_be.add_trace(go.Scatter(
        x=tariffe_test, y=costi_fissi,
        line=dict(color='#e74c3c', width=3, dash='dot'),
        name='Costo Totale (Break-even)',
        fill='toself',
        fillcolor='rgba(231, 76, 60, 0.1)'
    ))

    # Punto di Break-even evidenziato
    fig_be.add_trace(go.Scatter(
        x=[prezzo_break_even], y=[total_est],
        mode='markers+text',
        marker=dict(color='black', size=12, symbol='x'),
        text=["BREAK-EVEN"],
        textposition="top center",
        name='Punto di Pareggio'
    ))

    fig_be.update_layout(
        hovermode="x unified",
        margin=dict(l=10, r=10, t=50, b=10),
        height=400,
        plot_bgcolor='white',
        xaxis=dict(title="Prezzo di vendita ($/kg)", showgrid=True, gridcolor='lightgray'),
        yaxis=dict(title="Valore Totale ($)", showgrid=True, gridcolor='lightgray'),
        legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig_be, use_container_width=True)

with col_res3:
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

# Banner Finale "Executive"
st.success(f"""
### **SINTESI FINANZIARIA**
* 💰 **Costo di Produzione:** $ {total_est:,.2f}
* 🎯 **Prezzo di Pareggio (Break-even):** $ {prezzo_break_even:.2f} / kg
* 💡 *Ogni dollaro incassato sopra questa soglia è profitto netto.*
""")


st.write("Developed by Brunaccini Riccardo")
