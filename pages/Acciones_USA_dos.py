import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# --- CONFIGURACIÓN DE PÁGINA ---
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
    st.title("🇺🇸 Análisis de Estrategia (Capital Base: $6,000)")

    # 1. Procesamiento de Trades Cerrados (Lógica Exacta de tu NB)
    df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

    resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
        'fecha': ['min', 'max'],
        'Inversion_USA': 'sum',
        'Cantidad_USA': lambda x: x[x > 0].sum(),
        'Precio_Unitario': 'first'
    }).reset_index()

    resumen_stats.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Neto_Flujo', 'Cant_Total', 'Precio_Entrada']

    # --- LÓGICA DE ESPEJO (IDÉNTICA A TU NB) ---
    resumen_stats['Resultado_USD'] = -resumen_stats['Neto_Flujo']
    resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
    resumen_stats['Precio_Salida'] = (resumen_stats['Inversion_Inicial'] + resumen_stats['Resultado_USD']) / resumen_stats['Cant_Total']
    resumen_stats['Rendimiento_%'] = (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100

    # Limpieza de fechas para visualización
    resumen_stats['Fecha_In'] = pd.to_datetime(resumen_stats['Fecha_In']).dt.date
    resumen_stats['Fecha_Out'] = pd.to_datetime(resumen_stats['Fecha_Out']).dt.date

    # 2. MÉTRICAS DE EFECTIVIDAD (INVERTIDAS SEGÚN TU NB)
    # En tu lógica de espejo: < 0 son los ganadores reales en tu bolsillo
    ganadores = resumen_stats[resumen_stats['Resultado_USD'] < 0].copy()
    perdedores = resumen_stats[resumen_stats['Resultado_USD'] >= 0].copy()

    total_trades = len(resumen_stats)
    win_rate = (len(ganadores) / total_trades) * 100 if total_trades > 0 else 0
    
    # Cálculos para Ratio B/R
    avg_win = -ganadores['Resultado_USD'].mean() if not ganadores.empty else 0
    avg_loss = perdedores['Resultado_USD'].abs().mean() if not perdedores.empty else 0
    risk_reward = avg_win / avg_loss if avg_loss != 0 else 0
    ganancia_neta = resumen_stats['Resultado_USD'].sum()

    # --- UI: MÉTRICAS CABECERA ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Win Rate ✅", f"{win_rate:.1f}%")
    c2.metric("Ganancia Neta", f"${ganancia_neta:,.2f}")
    c3.metric("Ratio B/R", f"1 : {risk_reward:.2f}")
    c4.metric("ROI sobre 6k", f"{(ganancia_neta/6000)*100:.2f}%")

    st.divider()

    # --- GRÁFICOS (Plotly para interactividad, pero con tu lógica) ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Efectividad de Trades (Win Rate)")
        fig_pie = px.pie(
            names=['Wins', 'Losses'],
            values=[len(ganadores), len(perdedores)],
            color_discrete_sequence=['#2ecc71', '#e74c3c'],
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        st.subheader("Distribución de Ganancia/Pérdida (USD)")
        fig_hist = px.histogram(
            resumen_stats, x="Resultado_USD", 
            nbins=20, color_discrete_sequence=['#3498db']
        )
        fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_hist, use_container_width=True)

    # --- SIMULACIÓN MONTE CARLO (BASADA EN TUS PARÁMETROS REALES) ---
    st.divider()
    st.subheader("🎲 Simulación Monte Carlo: 107 Trades (Ritmo 2.5 años)")
    
    capital_inicial = 6000
    win_rate_sim = 0.60
    ratio_rb = 2.0
    perdida_media = 30.02
    ganancia_media = perdida_media * ratio_rb
    n_trades = 107
    n_simulaciones = 100 # Para performance en web, bajamos a 100 rutas visuales
    
    fig_mc = go.Figure()
    resultados_finales = []

    for _ in range(n_simulaciones):
        eventos = np.random.choice([ganancia_media, -perdida_media], size=n_trades, p=[win_rate_sim, 1-win_rate_sim])
        trayectoria = capital_inicial + np.cumsum(eventos)
        resultados_finales.append(trayectoria[-1])
        fig_mc.add_trace(go.Scatter(y=trayectoria, mode='lines', line=dict(width=1), opacity=0.2, showlegend=False, line_color='royalblue'))

    fig_mc.add_hline(y=capital_inicial, line_dash="dash", line_color="red", annotation_text="Capital Inicial")
    fig_mc.update_layout(xaxis_title="Número de Trade", yaxis_title="Capital (USD)", template="plotly_white")
    st.plotly_chart(fig_mc, use_container_width=True)

    # Estadísticas de Proyección
    ganancia_esperada = np.mean(resultados_finales) - capital_inicial
    prob_exito = (np.array(resultados_finales) > capital_inicial).mean() * 100
    
    st.info(f"📊 **ANÁLISIS DE RITMO ACTUAL:** Esperanza de Ganancia: ${ganancia_esperada:,.2f} | Probabilidad de Rentabilidad: {prob_exito:.1f}%")

    # --- TABLAS FINALES (ORDENADAS SEGÚN TU NB) ---
    st.divider()
    cols_mostrar = ['Ticker', 'Fecha_In', 'Fecha_Out', 'Cant_Total', 'Precio_Entrada', 'Precio_Salida', 'Inversion_Inicial', 'Resultado_USD', 'Rendimiento_%']

    # TRADES PERDEDORES (En tu lógica son los que dieron Ganancia Real)
    st.subheader("🟢 TRADES PERDEDORES (Ordenados por Ganancia)")
    st.dataframe(
        ganadores[cols_mostrar].sort_values('Resultado_USD', ascending=True).style.format({
            'Precio_Entrada': '{:.2f}', 'Precio_Salida': '{:.2f}',
            'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'
        }), use_container_width=True
    )

    # TRADES GANADORES (En tu lógica son los que figuran con resultado positivo en el CSV)
    st.subheader("🔴 TRADES GANADORES (Ordenados por Pérdida)")
    st.dataframe(
        perdedores[cols_mostrar].sort_values('Resultado_USD', ascending=False).style.format({
            'Precio_Entrada': '{:.2f}', 'Precio_Salida': '{:.2f}',
            'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'
        }), use_container_width=True
    )
else:
    st.error("No se pudo cargar el archivo. Verificá la ruta de 'reporte_trades_para_USA.csv'.")
