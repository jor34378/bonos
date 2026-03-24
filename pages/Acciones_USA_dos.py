import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Performance USA", layout="wide")

@st.cache_data
def cargar_datos_usa():
    nombre = 'reporte_trades_para_USA.csv'
    rutas = [nombre, os.path.join('..', nombre)]
    for r in rutas:
        if os.path.exists(r):
            return pd.read_csv(r, sep=';', encoding='utf-8-sig')
    return None

df_trades = cargar_datos_usa()

if df_trades is not None:
    st.title("🇺🇸 Análisis de Estrategia - Acciones USA")
    
    # 1. Filtramos solo trades cerrados
    df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

    # Agrupamos para obtener el neto de cada trade
    resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
        'Inversion_USA': 'sum',
        'Cantidad_USA': lambda x: x[x > 0].sum(),
        'Precio_Unitario': 'first'
    }).reset_index()

    # --- EL TRUCO DE LA LÓGICA DE ESPEJO ---
    # En tu CSV: Salida de plata (Compra) es +, Entrada de plata (Venta) es -.
    # Si sum(Inversion_USA) es -50, significa que entró más de lo que salió -> GANANCIA.
    
    resumen_stats['Resultado_USD'] = -resumen_stats['Inversion_USA'] # Invertimos: Negativo se hace Positivo (Verde)
    
    # Inversión inicial estimada (Precio de la primera compra * cantidad total comprada)
    resumen_stats['Inversion_Inicial'] = resumen_stats['Cantidad_USA'] * resumen_stats['Precio_Unitario']
    resumen_stats['Rendimiento_%'] = (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100

    # CLASIFICACIÓN REAL
    ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
    perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()
    
    total_trades = len(resumen_stats)
    win_rate = (len(ganadores) / total_trades * 100) if total_trades > 0 else 0
    ganancia_total = resumen_stats['Resultado_USD'].sum()

    # --- UI: MÉTRICAS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Win Rate ✅", f"{win_rate:.1f}%")
    c2.metric("Ganancia Total USD", f"$ {ganancia_total:,.2f}")
    c3.metric("Trade Promedio", f"$ {resumen_stats['Resultado_USD'].mean():,.2f}")
    c4.metric("Total Trades", total_trades)

    st.divider()

    # --- GRÁFICOS ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Efectividad")
        if total_trades > 0:
            fig_pie = px.pie(
                names=['Ganadores', 'Perdedores'], 
                values=[len(ganadores), len(perdedores)],
                color_discrete_sequence=['#2ecc71', '#e74c3c'],
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
        st.subheader("Distribución PnL Real (USD)")
        if not resumen_stats.empty:
            fig_hist = px.histogram(
                resumen_stats, x="Resultado_USD", 
                nbins=20, color_discrete_sequence=['#3498db']
            )
            fig_hist.add_vline(x=0, line_dash="dash", line_color="black")
            st.plotly_chart(fig_hist, use_container_width=True)

    # --- SIMULACIÓN MONTE CARLO ---
    st.subheader("🎲 Simulación de Proyección (Monte Carlo)")
    
    if len(ganadores) > 0 and len(perdedores) > 0:
        capital_inicial = 6000
        g_media = ganadores['Resultado_USD'].mean()
        p_media = abs(perdedores['Resultado_USD'].mean())
        
        fig_mc = go.Figure()
        for _ in range(50):
            # Generamos 107 pasos usando tus promedios reales
            pasos = np.random.choice([g_media, -p_media], size=107, p=[win_rate/100, (100-win_rate)/100])
            trayectoria = capital_inicial + np.cumsum(pasos)
            fig_mc.add_trace(go.Scatter(y=trayectoria, mode='lines', line=dict(width=1), opacity=0.3, showlegend=False))
        
        fig_mc.add_hline(y=capital_inicial, line_dash="dash", line_color="red")
        fig_mc.update_layout(height=400, template="plotly_dark")
        st.plotly_chart(fig_mc, use_container_width=True)
    else:
        st.warning("Se necesitan trades ganadores y perdedores para ejecutar la simulación.")

    # --- TABLA DETALLADA ---
    st.subheader("📋 Registro de Operaciones")
    st.dataframe(
        resumen_stats.sort_values('Resultado_USD', ascending=False).style.format({
            'Inversion_Inicial': '${:,.2f}', 
            'Resultado_USD': '${:,.2f}', 
            'Rendimiento_%': '{:.2f}%'
        }).background_gradient(subset=['Resultado_USD'], cmap='RdYlGn'),
        use_container_width=True
    )
