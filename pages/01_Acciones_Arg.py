import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import os
import matplotlib.pyplot as plt

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Portfolio Argentina Pro", layout="wide")

@st.cache_data
def cargar_datos_argentina():
    archivo = 'reporte_trades_para_ARG.csv'
    if not os.path.exists(archivo):
        st.error(f"⚠️ No se encuentra '{archivo}'")
        return None

    df = pd.read_csv(archivo, sep=None, engine='python', encoding='utf-8-sig')
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    mapeo = {
        'ticker': 'Ticker', 'operado': 'fecha', 'cantidad': 'Cantidad',
        'precio_usd': 'Precio_USD', 'inversion_usd': 'Inversion_USD'
    }
    df = df.rename(columns={k: v for k, v in mapeo.items() if k in df.columns})
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    
    # --- PROCESAMIENTO ---
    df = df.sort_values(['Ticker', 'fecha'])
    df['Posicion_Acum'] = df.groupby('Ticker')['Cantidad'].cumsum()

    # Limpieza de residuos (FERR/IRSA)
    df.loc[df['Posicion_Acum'].abs() < 1.0, 'Posicion_Acum'] = 0.0
    
    df['Es_Cierre'] = (df['Posicion_Acum'] == 0)
    df['ID_Trade'] = (df.groupby('Ticker')['Es_Cierre'].shift(fill_value=False)
                      .groupby(df['Ticker']).cumsum() + 1)
    
    status = df.groupby(['Ticker', 'ID_Trade'])['Posicion_Acum'].last().apply(
        lambda x: 'Abierto' if abs(x) >= 1.0 else 'Cerrado'
    ).reset_index(name='Estado_Trade')
    
    return df.merge(status, on=['Ticker', 'ID_Trade'])

def obtener_precios(tickers):
    if not tickers: return {}
    try:
        data = yf.download([f"{t}.BA" for t in tickers], period="1d", progress=False)['Close']
        return {t: data[f"{t}.BA"].iloc[-1] if len(tickers)>1 else data.iloc[-1] for t in tickers}
    except: return {}

# --- LÓGICA DE LA APP ---
df_arg = cargar_datos_argentina()

if df_arg is not None:
    mep_hoy = st.sidebar.number_input("Cotización MEP", value=1433.21)
    
    # 1. CÁLCULO DE CERRADOS PARA MÉTRICAS
    df_cerrados = df_arg[df_arg['Estado_Trade'] == 'Cerrado'].copy()
    
    # Agregamos lógica para obtener el COSTO (suma de compras) y el RESULTADO
    resumen_c = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
        Fecha_In=('fecha', 'min'),
        Fecha_Out=('fecha', 'max'),
        Flujo_Neto=('Inversion_USD', 'sum') # Si es positivo, es ganancia neta
    ).reset_index()
    
    # El costo lo sacamos de la suma de flujos negativos de ese trade
    costos = df_cerrados[df_cerrados['Inversion_USD'] < 0].groupby(['Ticker', 'ID_Trade'])['Inversion_USD'].sum().abs()
    resumen_c = resumen_c.merge(costos.rename('Costo_USD'), on=['Ticker', 'ID_Trade'], how='left')
    
    resumen_c['Resultado_USD'] = -resumen_c['Flujo_Neto'] # Invertimos para que + sea Ganancia
    resumen_c['Rend_%'] = (resumen_c['Resultado_USD'] / resumen_c['Costo_USD']) * 100

    ganadores = resumen_c[resumen_c['Resultado_USD'] > 0]
    perdedores = resumen_c[resumen_c['Resultado_USD'] <= 0]

    # --- MÉTRICAS ENCABEZADO ---
    st.title("📊 Performance Argentina - Trade Report")
    
    w_avg_gain = (ganadores['Rend_%'] * ganadores['Costo_USD']).sum() / ganadores['Costo_USD'].sum() if not ganadores.empty else 0
    w_avg_loss = (perdedores['Rend_%'] * perdedores['Costo_USD']).sum() / perdedores['Costo_USD'].sum() if not perdedores.empty else 0
    avg_size_10k = (resumen_c['Costo_USD'].mean() / 10000) * 100
    profit_factor = ganadores['Resultado_USD'].sum() / abs(perdedores['Resultado_USD'].sum()) if not perdedores.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Prom. Pond. Ganancia", f"{w_avg_gain:.2f}%")
    m2.metric("Prom. Pond. Pérdida", f"{w_avg_loss:.2f}%")
    m3.metric("Avg Size (s/10k)", f"{avg_size_10k:.2f}%")
    m4.metric("Profit Factor", f"{profit_factor:.2f}x")

    # --- CUADRANTE DE TORTAS ---
    st.write("---")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        fig_win, ax_win = plt.subplots(figsize=(6, 4))
        ax_win.pie([len(ganadores), len(perdedores)], labels=['Wins', 'Losses'], 
                   autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'], startangle=140)
        ax_win.set_title("Win Rate (Efectividad)")
        st.pyplot(fig_win)

    # --- ABIERTOS & PARTICIPACIÓN ---
    df_abiertos = df_arg[df_arg['Estado_Trade'] == 'Abierto'].copy()
    if not df_abiertos.empty:
        dict_precios = obtener_precios(df_abiertos['Ticker'].unique().tolist())
        res_abierto = df_abiertos.groupby(['Ticker', 'ID_Trade']).agg({
            'Posicion_Acum': 'last', 
            'Inversion_USD': 'sum' # Flujo negativo de compras
        }).reset_index()
        
        res_abierto['Valuacion_USD'] = (res_abierto['Posicion_Acum'] * res_abierto['Ticker'].map(dict_precios)) / mep_hoy
        
        # CORRECCIÓN DE FÓRMULA: Valuacion - Costo
        res_abierto['Costo_USD'] = res_abierto['Inversion_USD'].abs()
        res_abierto['Ganancia_USD'] = res_abierto['Valuacion_USD'] - res_abierto['Costo_USD']
        res_abierto['Rend_%'] = (res_abierto['Ganancia_USD'] / res_abierto['Costo_USD']) * 100

        with col_chart2:
            fig_part, ax_part = plt.subplots(figsize=(6, 4))
            ax_part.pie(res_abierto['Valuacion_USD'], labels=res_abierto['Ticker'], autopct='%1.1f%%', startangle=140)
            ax_part.set_title("Participación Tenencia Actual")
            st.pyplot(fig_part)

        st.subheader("🔵 Posiciones Actuales")
        # Aplicamos la paleta de colores solicitada
        st.dataframe(res_abierto.style.format({
            'Valuacion_USD': 'US$ {:,.2f}', 'Costo_USD': 'US$ {:,.2f}', 
            'Ganancia_USD': 'US$ {:,.2f}', 'Rend_%': '{:.2f}%'
        }).background_gradient(subset=['Ganancia_USD', 'Rend_%'], cmap='RdYlGn', vmin=-15, vmax=15))

    # --- HISTORIAL CERRADOS ---
    st.write("---")
    st.subheader("📜 Historial de Trades Cerrados")
    tab_win, tab_loss = st.tabs(["✅ Ganadores", "❌ Perdedores"])
    
    format_dict = {'Resultado_USD': 'US$ {:,.2f}', 'Costo_USD': 'US$ {:,.2f}', 'Rend_%': '{:.2f}%'}
    
    with tab_win:
        st.dataframe(ganadores.sort_values('Resultado_USD', ascending=False).style.format(format_dict)
                     .background_gradient(subset=['Resultado_USD', 'Rend_%'], cmap='Greens'), use_container_width=True)
    with tab_loss:
        st.dataframe(perdedores.sort_values('Resultado_USD', ascending=True).style.format(format_dict)
                     .background_gradient(subset=['Resultado_USD', 'Rend_%'], cmap='Reds'), use_container_width=True)
