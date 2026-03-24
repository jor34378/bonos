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
        # NO invertimos nada aquí. Los datos entran como vienen:
        # Ventas → Inversion_USA negativa (ingreso de dinero)
        # Compras → Inversion_USA positiva (egreso de dinero)
        return df
    return None

df_trades = cargar_datos_usa()

if df_trades is not None:
    st.title("🇺🇸 Análisis de Estrategia - Acciones USA")

    # 1. Filtramos trades cerrados
    df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

    # 2. Agrupamos para calcular el PnL real de cada trade
    # PnL = suma de Inversion_USA del trade completo.
    # Ventas aportan negativo (ingresos), Compras aportan positivo (costos).
    # PnL = ingresos - costos → si ganaste, el neto es NEGATIVO en el CSV.
    # Por eso al final multiplicamos por -1 SOLO el resultado agrupado.
    resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
        PnL_raw=('Inversion_USA', 'sum'),
        Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
        Precio_Entrada=('Precio_Unitario', 'first'),
        Fecha_In=('fecha', 'min'),
        Fecha_Out=('fecha', 'max')
    ).reset_index()

    # La inversión neta en el CSV es positiva cuando perdés y negativa cuando ganás.
    # Invertimos solo aquí para tener semántica correcta: positivo = ganancia.
    resumen_stats['Resultado_USD'] = resumen_stats['PnL_raw'] * -1

    # 3. Inversión inicial para calcular el rendimiento %
    resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
    resumen_stats['Rendimiento_%'] = np.where(
        resumen_stats['Inversion_Inicial'] > 0,
        (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100,
        0
    )

    # 4. Clasificación correcta
    ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
    perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()

    total_trades = len(resumen_stats)
    win_rate = (len(ganadores) / total_trades * 100) if total_trades > 0 else 0
    ganancia_total = resumen_stats['Resultado_USD'].sum()

    # --- MÉTRICAS ---
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
            names=['Ganadores', 'Perdedores'],
            values=[len(ganadores), len(perdedores)],
            color_discrete_sequence=['#2ecc71', '#e74c3c'],
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
        st.subheader("Distribución de PnL (USD)")
        fig_hist = px.histogram(
            resumen_stats, x="Resultado_USD",
            nbins=20, color_discrete_sequence=['#3498db'],
            labels={"Resultado_USD": "Resultado USD"}
        )
        fig_hist.add_vline(x=0, line_dash="dash", line_color="red",
                           annotation_text="Break even", annotation_position="top right")
        fig_hist.update_layout(template="plotly_dark")
        st.plotly_chart(fig_hist, use_container_width=True)

    # --- SIMULACIÓN MONTE CARLO ---
    st.subheader("🎲 Simulación de Proyección (Próximos 107 Trades)")

    if not ganadores.empty and not perdedores.empty:
        capital_inicial = 6000
        g_media = ganadores['Resultado_USD'].mean()
        p_media = abs(perdedores['Resultado_USD'].mean())
        prob_ganar = win_rate / 100
        prob_perder = 1 - prob_ganar

        simulaciones = 50
        n_trades = 107
        resultados_finales = []

        fig_mc = go.Figure()
        for _ in range(simulaciones):
            pasos = np.random.choice(
                [g_media, -p_media],
                size=n_trades,
                p=[prob_ganar, prob_perder]
            )
            trayectoria = capital_inicial + np.cumsum(pasos)
            resultados_finales.append(trayectoria[-1])
            fig_mc.add_trace(go.Scatter(
                y=trayectoria, mode='lines',
                line=dict(width=1),
                opacity=0.3,
                showlegend=False
            ))

        fig_mc.add_hline(y=capital_inicial, line_dash="dash", line_color="white",
                         annotation_text=f"Capital inicial ${capital_inicial:,}")
        fig_mc.update_layout(
            height=450,
            template="plotly_dark",
            yaxis_title="Capital USD",
            xaxis_title="Nro. de Trade"
        )
        st.plotly_chart(fig_mc, use_container_width=True)

        # Métricas Monte Carlo
        percentil_10 = np.percentile(resultados_finales, 10)
        percentil_90 = np.percentile(resultados_finales, 90)
        media_final = np.mean(resultados_finales)

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Escenario Pesimista (P10)", f"$ {percentil_10:,.2f}")
        mc2.metric("Capital Esperado (Media)", f"$ {media_final:,.2f}")
        mc3.metric("Escenario Optimista (P90)", f"$ {percentil_90:,.2f}")

        st.info(f"Basado en {total_trades} trades históricos | Ganancia media: ${g_media:.2f} | Pérdida media: ${p_media:.2f} | Win Rate: {win_rate:.1f}%")
    else:
        st.warning("No hay suficientes datos de ganadores y perdedores para simular.")

    # --- REGISTRO DE OPERACIONES ---
    st.subheader("📋 Detalle de Trades (Ordenados por Resultado)")
    st.dataframe(
        resumen_stats[['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out',
                        'Cant_Total', 'Precio_Entrada', 'Inversion_Inicial',
                        'Resultado_USD', 'Rendimiento_%']]
        .sort_values('Resultado_USD', ascending=False)
        .style.format({
            'Inversion_Inicial': '${:,.2f}',
            'Resultado_USD': '${:,.2f}',
            'Rendimiento_%': '{:.2f}%',
            'Precio_Entrada': '{:.2f}'
        }).background_gradient(subset=['Resultado_USD'], cmap='RdYlGn'),
        use_container_width=True
    )
else:
    st.error("❌ No se encontró el archivo 'reporte_trades_para_USA.csv'. Asegurate de que esté en la misma carpeta que este script.")
