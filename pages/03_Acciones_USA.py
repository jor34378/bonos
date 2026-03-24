import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Performance USA", layout="wide")

@st.cache_data
def cargar_datos_usa():
    try:
        # Cargamos el CSV que generaste en la Notebook
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=';', encoding='utf-8-sig')
        return df
    except Exception as e:
        st.error(f"Error al cargar 'reporte_trades_para_USA.csv': {e}")
        return None

# --- PROCESAMIENTO ---
df_trades = cargar_datos_usa()

if df_trades is not None:
    st.title("🇺🇸 Análisis de Estrategia - Acciones USA")
    
    # 1. Procesamiento de Trades Cerrados
    df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

    resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
        'fecha': ['min', 'max'],
        'Inversion_USA': 'sum',
        'Cantidad_USA': lambda x: x[x > 0].sum(),
        'Precio_Unitario': 'first'
    }).reset_index()

    resumen_stats.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Neto_Flujo', 'Cant_Total', 'Precio_Entrada']

    # Lógica de Espejo
    resumen_stats['Resultado_USD'] = -resumen_stats['Neto_Flujo']
    resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
    resumen_stats['Precio_Salida'] = (resumen_stats['Inversion_Inicial'] + resumen_stats['Resultado_USD']) / resumen_stats['Cant_Total']
    resumen_stats['Rendimiento_%'] = (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100

    # Métricas de Efectividad
    ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
    perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()
    
    total_trades = len(resumen_stats)
    win_rate = (len(ganadores) / total_trades * 100) if total_trades > 0 else 0
    ganancia_neta = resumen_stats['Resultado_USD'].sum()
    roi_6k = (ganancia_neta / 6000) * 100

    # --- UI: MÉTRICAS PRINCIPALES ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Win Rate", f"{win_rate:.1f}%")
    col2.metric("Ganancia Neta", f"US$ {ganancia_neta:,.2f}")
    col3.metric("ROI (Base 6k)", f"{roi_6k:.2f}%")
    col4.metric("Total Trades", total_trades)

    st.divider()

    # --- UI: GRÁFICOS INTERACTIVOS ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Pie Chart: Efectividad")
        fig_pie = px.pie(
            names=['Wins', 'Losses'], 
            values=[len(ganadores), len(perdedores)],
            color_discrete_sequence=['#2ecc71', '#e74c3c'],
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
        st.subheader("Distribución PnL (USD)")
        fig_hist = px.histogram(
            resumen_stats, x="Resultado_USD", 
            nbins=20, color_discrete_sequence=['skyblue'],
            marginal="box" # Agrega un diagrama de caja arriba
        )
        fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_hist, use_container_width=True)

    # --- UI: TABLAS CON GRADIENTES ---
    st.subheader("🟢 Detalle de Trades Ganadores")
    st.dataframe(
        ganadores.sort_values('Resultado_USD', ascending=False).style.format({
            'Precio_Entrada': '{:.2f}', 'Precio_Salida': '{:.2f}',
            'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'
        }).background_gradient(subset=['Resultado_USD'], cmap='Greens'),
        use_container_width=True
    )

    st.subheader("🔴 Detalle de Trades Perdedores")
    st.dataframe(
        perdedores.sort_values('Resultado_USD', ascending=True).style.format({
            'Precio_Entrada': '{:.2f}', 'Precio_Salida': '{:.2f}',
            'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'
        }).background_gradient(subset=['Resultado_USD'], cmap='Reds'),
        use_container_width=True
    )

    # --- SIMULACIÓN MONTE CARLO ---
    st.divider()
    st.header("🎲 Proyección Monte Carlo (Próximos 107 Trades)")
    
    capital_inicial = 6000
    perdida_media = abs(perdedores['Resultado_USD'].mean()) if not perdedores.empty else 30
    ganancia_media = ganadores['Resultado_USD'].mean() if not ganadores.empty else 60
    n_simulaciones = 100
    
    fig_mc = go.Figure()
    final_values = []

    for _ in range(n_simulaciones):
        eventos = np.random.choice([ganancia_media, -perdida_media], size=107, p=[win_rate/100, (100-win_rate)/100])
        trayectoria = capital_inicial + np.cumsum(eventos)
        final_values.append(trayectoria[-1])
        fig_mc.add_trace(go.Scatter(y=trayectoria, mode='lines', line=dict(width=1), opacity=0.1, showlegend=False, line_color='royalblue'))

    fig_mc.add_hline(y=capital_inicial, line_dash="dash", line_color="red", annotation_text="Capital Inicial")
    fig_mc.update_layout(title="100 Rutas Probables de Capital", xaxis_title="Número de Trade", yaxis_title="Capital (USD)")
    st.plotly_chart(fig_mc, use_container_width=True)

    # Estadísticas de Proyección
    ganancia_esp = np.mean(final_values) - capital_inicial
    prob_rentable = (np.array(final_values) > capital_inicial).mean() * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Esperanza Ganancia Total", f"US$ {ganancia_esp:,.2f}")
    c2.metric("Probabilidad de Éxito", f"{prob_rentable:.1f}%")
    c3.metric("Capital Final Promedio", f"US$ {np.mean(final_values):,.2f}")
