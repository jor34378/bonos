import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Performance USA", layout="wide")

@st.cache_data
def cargar_datos_usa():
    # Buscamos el archivo que ya tenés en la raíz
    nombre = 'reporte_trades_para_USA.csv'
    rutas = [nombre, os.path.join('..', nombre)]
    for r in rutas:
        if os.path.exists(r):
            # Cargamos con el separador ; que usaste en tu exportación
            return pd.read_csv(r, sep=';', encoding='utf-8-sig')
    return None

st.title("🇺🇸 Análisis de Estrategia - Acciones USA")

df_trades = cargar_datos_usa()

if df_trades is not None:
    # 1. Filtramos solo los cerrados (igual que en tu código de ARG)
    df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()
    
    if not df_cerrados.empty:
        # 2. Agrupación idéntica a la de ARG
        resumen_c = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
            'fecha': ['min', 'max'],
            'Inversion_USA': 'sum'  # Sumamos los flujos directamente
        }).reset_index()
        
        # Aplanamos columnas
        resumen_c.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Resultado_Neto']
        
        # --- LA LÓGICA CLAVE DE TU CÓDIGO ARG ---
        # Invertís el signo del total de la inversión sumada
        resumen_c['Resultado_USD'] = -resumen_c['Resultado_Neto']
        
        # 3. Métricas Principales
        ganadores = resumen_c[resumen_c['Resultado_USD'] > 0]
        perdedores = resumen_c[resumen_c['Resultado_USD'] <= 0]
        
        total_trades = len(resumen_c)
        win_rate = (len(ganadores) / total_trades * 100) if total_trades > 0 else 0
        ganancia_total = resumen_c['Resultado_USD'].sum()

        # --- VISUALIZACIÓN ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Win Rate ✅", f"{win_rate:.1f}%")
        col2.metric("Ganancia Total", f"US$ {ganancia_total:,.2f}")
        col3.metric("Total Trades", total_trades)

        st.divider()

        # Gráficos dinámicos
        c_left, c_right = st.columns(2)
        with c_left:
            st.subheader("Efectividad")
            fig_pie = px.pie(names=['Win', 'Loss'], values=[len(ganadores), len(perdedores)],
                             color_discrete_sequence=['#2ecc71', '#e74c3c'], hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c_right:
            st.subheader("Distribución PnL")
            fig_hist = px.histogram(resumen_c, x="Resultado_USD", color_discrete_sequence=['#3498db'])
            fig_hist.add_vline(x=0, line_dash="dash", line_color="black")
            st.plotly_chart(fig_hist, use_container_width=True)

        # --- SIMULACIÓN MONTE CARLO ---
        st.subheader("🎲 Simulación de Proyección (Próximos 107 Trades)")
        if not ganadores.empty and not perdedores.empty:
            cap_inicial = 6000
            g_media = ganadores['Resultado_USD'].mean()
            p_media = abs(perdedores['Resultado_USD'].mean())
            
            fig_mc = go.Figure()
            for _ in range(50):
                pasos = np.random.choice([g_media, -p_media], size=107, p=[win_rate/100, (1-win_rate/100)])
                trayectoria = cap_inicial + np.cumsum(pasos)
                fig_mc.add_trace(go.Scatter(y=trayectoria, mode='lines', line=dict(width=1), opacity=0.3, showlegend=False))
            
            fig_mc.add_hline(y=cap_inicial, line_dash="dash", line_color="red")
            st.plotly_chart(fig_mc, use_container_width=True)

        # --- TABLA FINAL (Estilo ARG) ---
        st.subheader("📋 Historial de Ganancias/Pérdidas")
        st.dataframe(
            resumen_c.sort_values('Fecha_Out', ascending=False).style.format({
                'Resultado_USD': 'US$ {:,.2f}'
            }).background_gradient(subset=['Resultado_USD'], cmap='RdYlGn'),
            use_container_width=True
        )
    else:
        st.info("No se detectaron trades cerrados en el archivo de USA.")
