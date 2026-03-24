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
    
    # 1. Procesamiento con LÓGICA INVERTIDA
    df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

    resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
        'fecha': ['min', 'max'],
        'Inversion_USA': 'sum',
        'Cantidad_USA': lambda x: x[x > 0].sum(),
        'Precio_Unitario': 'first'
    }).reset_index()

    resumen_stats.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Neto_Flujo', 'Cant_Total', 'Precio_Entrada']

    # --- CORRECCIÓN DE SIGNOS ---
    # Si Neto_Flujo es -100, gané 100.
    resumen_stats['Resultado_USD'] = -resumen_stats['Neto_Flujo']
    resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
    resumen_stats['Precio_Salida'] = (resumen_stats['Inversion_Inicial'] + resumen_stats['Resultado_USD']) / resumen_stats['Cant_Total']
    resumen_stats['Rendimiento_%'] = (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100

    # Clasificación real: Resultado_USD > 0 es GANANCIA
    ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
    perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()
    
    total_trades = len(resumen_stats)
    win_rate = (len(ganadores) / total_trades * 100) if total_trades > 0 else 0
    ganancia_total = resumen_stats['Resultado_USD'].sum()

    # --- UI: MÉTRICAS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Win Rate ✅", f"{win_rate:.1f}%")
    c2.metric("Ganancia Total USD", f"$ {ganancia_total:,.2f}", delta=f"{ganancia_total:,.2f}")
    c3.metric("Trade Promedio", f"$ {resumen_stats['Resultado_USD'].mean():,.2f}")
    c4.metric("Total Trades", total_trades)

    # --- UI: GRÁFICOS (Ajuste de tamaño) ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Efectividad")
        fig_pie = px.pie(
            names=['Ganadores', 'Perdedores'], 
            values=[len(ganadores), len(perdedores)],
            color_discrete_sequence=['#2ecc71', '#e74c3c'],
            hole=0.4, height=400
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        st.subheader("Distribución de Ganancias/Pérdidas")
        fig_hist = px.histogram(
            resumen_stats, x="Resultado_USD", 
            nbins=15, color_discrete_sequence=['#3498db'],
            height=400
        )
        fig_hist.add_vline(x=0, line_dash="dash", line_color="black")
        st.plotly_chart(fig_hist, use_container_width=True)

    # --- SIMULACIÓN MONTE CARLO (Corregida) ---
    st.divider()
    st.header("🎲 Proyección Monte Carlo")
    
    capital_inicial = 6000
    # Parámetros basados en tu historia real:
    p_media = abs(perdedores['Resultado_USD'].mean()) if not perdedores.empty else 30
    g_media = ganadores['Resultado_USD'].mean() if not ganadores.empty else 60
    
    fig_mc = go.Figure()
    final_vals = []

    for _ in range(50): # 50 rutas para que no pese tanto
        # Simulamos 107 trades con tu Win Rate real
        random_trades = np.random.choice([g_media, -p_media], size=107, p=[win_rate/100, (100-win_rate)/100])
        trayectoria = capital_inicial + np.cumsum(random_trades)
        final_vals.append(trayectoria[-1])
        fig_mc.add_trace(go.Scatter(y=trayectoria, mode='lines', line=dict(width=1.5), opacity=0.3))

    fig_mc.update_layout(
        height=500,
        yaxis_title="Capital USD",
        xaxis_title="Número de Trades Futuros",
        showlegend=False
    )
    st.plotly_chart(fig_mc, use_container_width=True)

    # --- TABLAS CON GRADIENTES ---
    st.subheader("📋 Detalle de Operaciones")
    # Formateamos para que se vea pro
    st.dataframe(
        resumen_stats.sort_values('Resultado_USD', ascending=False).style.format({
            'Precio_Entrada': '{:.2f}', 'Precio_Salida': '{:.2f}',
            'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'
        }).background_gradient(subset=['Resultado_USD'], cmap='RdYlGn'), # Rojo a Verde
        use_container_width=True
    )
