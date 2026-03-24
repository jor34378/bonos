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
    archivo_encontrado = None
    for r in rutas:
        if os.path.exists(r):
            archivo_encontrado = r
            break
    
    if archivo_encontrado:
        df = pd.read_csv(archivo_encontrado, sep=';', encoding='utf-8-sig')
        # --- EL CAMBIO CLAVE ---
        # Multiplicamos por -1 TODA la columna de inversión apenas entra.
        # Si en el CSV decía -100 (Venta/Ganancia), ahora es +100.
        # Si decía +80 (Compra/Gasto), ahora es -80.
        if 'Inversion_USA' in df.columns:
            df['Inversion_USA'] = df['Inversion_USA'] * -1
        return df
    return None

df_trades = cargar_datos_usa()

if df_trades is not None:
    st.title("🇺🇸 Análisis de Estrategia - Acciones USA")
    
    # 1. Filtramos trades cerrados
    df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

    # 2. Agrupamos para ver el PnL final de cada trade
    # Como ya multiplicamos por -1 arriba, el sum() ahora da el resultado real.
    resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
        'Inversion_USA': 'sum',
        'Cantidad_USA': lambda x: x[x > 0].sum(),
        'Precio_Unitario': 'first',
        'fecha': ['min', 'max']
    }).reset_index()

    resumen_stats.columns = ['Ticker', 'ID_Trade', 'Resultado_USD', 'Cant_Total', 'Precio_Entrada', 'Fecha_In', 'Fecha_Out']

    # 3. Cálculos de inversión inicial (para el %)
    # La inversión inicial siempre es positiva para el cálculo del denominador
    resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
    resumen_stats['Rendimiento_%'] = (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100

    # 4. Clasificación (Ahora sí: > 0 es Ganancia)
    ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
    perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()
    
    total_trades = len(resumen_stats)
    win_rate = (len(ganadores) / total_trades * 100) if total_trades > 0 else 0
    ganancia_total = resumen_stats['Resultado_USD'].sum()

    # --- UI: MÉTRICAS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Win Rate ✅", f"{win_rate:.1f}%")
    c2.metric("Ganancia Total USD", f"$ {ganancia_total:,.2f}")
    c3.metric("P&L Promedio por Trade", f"$ {resumen_stats['Resultado_USD'].mean():,.2f}")
    c4.metric("Total Trades Cerrados", total_trades)

    st.divider()

    # --- GRÁFICOS ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Efectividad")
        fig_pie = px.pie(
            names=['Ganadores (Verde)', 'Perdedores (Rojo)'], 
            values=[len(ganadores), len(perdedores)],
            color_discrete_sequence=['#2ecc71', '#e74c3c'],
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
        st.subheader("Distribución de Trades (USD)")
        # El histograma ahora mostrará las ganancias a la derecha del 0
        fig_hist = px.histogram(
            resumen_stats, x="Resultado_USD", 
            nbins=20, color_discrete_sequence=['#3498db']
        )
        fig_hist.add_vline(x=0, line_dash="dash", line_color="black")
        st.plotly_chart(fig_hist, use_container_width=True)

    # --- SIMULACIÓN MONTE CARLO ---
    st.subheader("🎲 Simulación de Proyección (Próximos 107 Trades)")
    
    if not ganadores.empty and not perdedores.empty:
        capital_inicial = 6000
        g_media = ganadores['Resultado_USD'].mean()
        p_media = abs(perdedores['Resultado_USD'].mean())
        
        fig_mc = go.Figure()
        for _ in range(50):
            pasos = np.random.choice([g_media, -p_media], size=107, p=[win_rate/100, (100-win_rate)/100])
            trayectoria = capital_inicial + np.cumsum(pasos)
            fig_mc.add_trace(go.Scatter(y=trayectoria, mode='lines', line=dict(width=1), opacity=0.3, showlegend=False))
        
        fig_mc.add_hline(y=capital_inicial, line_dash="dash", line_color="white", annotation_text="Base 6k")
        fig_mc.update_layout(height=450, template="plotly_dark", yaxis_title="Capital USD")
        st.plotly_chart(fig_mc, use_container_width=True)
        
        # Métricas de la simulación
        st.info(f"Basado en tu ritmo: Ganancia media ${g_media:.2f} | Pérdida media ${p_media:.2f}")

    # --- REGISTRO DE OPERACIONES ---
    st.subheader("📋 Detalle de Trades (Ordenados por Resultado)")
    # El gradiente RdYlGn pondrá en verde los positivos (ganancias) y en rojo los negativos
    st.dataframe(
        resumen_stats.sort_values('Resultado_USD', ascending=False).style.format({
            'Inversion_Inicial': '${:,.2f}', 
            'Resultado_USD': '${:,.2f}', 
            'Rendimiento_%': '{:.2f}%',
            'Precio_Entrada': '{:.2f}'
        }).background_gradient(subset=['Resultado_USD'], cmap='RdYlGn'),
        use_container_width=True
    )
