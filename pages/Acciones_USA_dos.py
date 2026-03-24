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

    # 1. Procesamiento de Trades Cerrados (Tu lógica de Notebook)
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

    # 2. MÉTRICAS DE EFECTIVIDAD (INVERTIDAS SEGÚN TU NB)
    # Nota: Siguiendo tu código, clasificamos por < 0 para ganadores
    ganadores = resumen_stats[resumen_stats['Resultado_USD'] < 0].copy()
    perdedores = resumen_stats[resumen_stats['Resultado_USD'] >= 0].copy()

    total_trades = len(resumen_stats)
    win_rate = (len(ganadores) / total_trades) * 100 if total_trades > 0 else 0
    loss_rate = 100 - win_rate

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

    # --- GRÁFICOS DE TU NB (Adaptados a Plotly para Streamlit) ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Efectividad de Trades")
        fig_pie = px.pie(
            names=['Wins', 'Losses'],
            values=[len(ganadores), len(perdedores)],
            color_discrete_sequence=['#2ecc71', '#e74c3c'],
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        st.subheader("Distribución de Ganancia/Pérdida")
        fig_hist = px.histogram(
            resumen_stats, x="Resultado_USD", 
            nbins=20, color_discrete_sequence=['#3498db']
        )
        fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_hist, use_container_width=True)

   import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Configuración inicial
st.set_page_config(page_title="Performance USA", layout="wide")

@st.cache_data
def cargar_datos():
    nombre = 'reporte_trades_para_USA.csv'
    if os.path.exists(nombre):
        return pd.read_csv(nombre, sep=';')
    elif os.path.exists(os.path.join('..', nombre)):
        return pd.read_csv(os.path.join('..', nombre), sep=';')
    return None

df_trades = cargar_datos()

if df_trades is not None:
    # 1. Procesamiento de Trades Cerrados
    df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

    # Agrupamos por Ticker e ID_Trade
    resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
        'fecha': ['min', 'max'],
        'Inversion_USA': 'sum',
        'Cantidad_USA': lambda x: x[x > 0].sum(),
        'Precio_Unitario': 'first'
    }).reset_index()

    resumen_stats.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Neto_Flujo', 'Cant_Total', 'Precio_Entrada']

    # --- LÓGICA DE ESPEJO (TU NOTEBOOK) ---
    resumen_stats['Resultado_USD'] = -resumen_stats['Neto_Flujo']
    resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
    resumen_stats['Precio_Salida'] = (resumen_stats['Inversion_Inicial'] + resumen_stats['Resultado_USD']) / resumen_stats['Cant_Total']
    resumen_stats['Rendimiento_%'] = (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100

    # 2. MÉTRICAS DE EFECTIVIDAD (INVERTIDAS SEGÚN TU NB)
    ganadores = resumen_stats[resumen_stats['Resultado_USD'] < 0].copy()
    perdedores = resumen_stats[resumen_stats['Resultado_USD'] >= 0].copy()

    total_trades = len(resumen_stats)
    win_rate_calc = (len(ganadores) / total_trades) * 100 if total_trades > 0 else 0
    ganancia_neta = resumen_stats['Resultado_USD'].sum()

    st.title("📊 Análisis de Estrategia USA")
    
    # --- MÉTRICAS DASHBOARD ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Win Rate", f"{win_rate_calc:.1f}%")
    c2.metric("Ganancia Neta", f"${ganancia_neta:,.2f}")
    c3.metric("Total Trades", total_trades)
    c4.metric("ROI s/ 6k", f"{(ganancia_neta/6000)*100:.2f}%")

    # --- GRÁFICOS INICIALES (Matplotlib como en tu NB) ---
    st.divider()
    col_gr1, col_gr2 = st.columns(2)
    
    with col_gr1:
        fig_pie, ax_pie = plt.subplots(figsize=(7, 4))
        ax_pie.pie([len(ganadores), len(perdedores)], labels=['Wins', 'Losses'],
                   autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'], startangle=140, explode=(0.05, 0))
        ax_pie.set_title('Efectividad de Trades')
        st.pyplot(fig_pie)

    with col_gr2:
        fig_hist, ax_hist = plt.subplots(figsize=(7, 4))
        sns.histplot(resumen_stats['Resultado_USD'], bins=20, color='skyblue', kde=True, ax=ax_hist)
        ax_hist.axvline(0, color='red', linestyle='--')
        ax_hist.set_title('Distribución de Ganancia/Pérdida (USD)')
        st.pyplot(fig_hist)

    # --- SIMULACIÓN MONTE CARLO (TU CÓDIGO EXACTO) ---
    st.divider()
    st.subheader("🎲 Simulación Monte Carlo: 107 Trades (Ritmo de 2.5 años)")
    
    capital_inicial = 6000
    win_rate = 0.60
    ratio_rb = 2.0
    perdida_media = 30.02
    ganancia_media = perdida_media * ratio_rb
    n_trades = 107
    n_simulaciones = 1000

    resultados_finales = []
    fig_mc, ax_mc = plt.subplots(figsize=(12, 6))

    for _ in range(n_simulaciones):
        eventos = np.random.choice([ganancia_media, -perdida_media], size=n_trades, p=[win_rate, 1-win_rate])
        trayectoria = capital_inicial + np.cumsum(eventos)
        resultados_finales.append(trayectoria[-1])
        ax_mc.plot(trayectoria, color='royalblue', alpha=0.03)

    ax_mc.axhline(capital_inicial, color='red', linestyle='--', label='Capital Inicial')
    ax_mc.set_xlabel('Número de Trade')
    ax_mc.set_ylabel('Capital (USD)')
    ax_mc.grid(True, alpha=0.3)
    st.pyplot(fig_mc)

    # Estadísticas de Proyección
    ganancia_esperada = np.mean(resultados_finales) - capital_inicial
    prob_exito = (np.array(resultados_finales) > capital_inicial).mean() * 100
    
    st.info(f"**Análisis de ritmo actual:** Esperanza de Ganancia: ${ganancia_esperada:,.2f} USD | Probabilidad de éxito: {prob_exito:.1f}%")

    # --- TABLAS FINALES ---
    st.divider()
    st.subheader("🟢 TRADES PERDEDORES (Ordenados por Ganancia)")
    cols_mostrar = ['Ticker', 'Fecha_In', 'Fecha_Out', 'Cant_Total', 'Precio_Entrada', 'Precio_Salida', 'Inversion_Inicial', 'Resultado_USD', 'Rendimiento_%']
    
    st.dataframe(ganadores[cols_mostrar].sort_values('Resultado_USD', ascending=False).style.format({
        'Precio_Entrada': '{:.2f}', 'Precio_Salida': '{:.2f}',
        'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'
    }), use_container_width=True)

    st.subheader("🔴 TRADES GANADORES (Ordenados por Pérdida)")
    st.dataframe(perdedores[cols_mostrar].sort_values('Resultado_USD', ascending=True).style.format({
        'Precio_Entrada': '{:.2f}', 'Precio_Salida': '{:.2f}',
        'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'
    }), use_container_width=True)

else:
    st.error("No se encontró el archivo 'reporte_trades_para_USA.csv'.")
