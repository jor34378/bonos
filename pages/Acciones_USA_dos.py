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
            df = pd.read_csv(r, sep=';', encoding='utf-8-sig')
            return df
    return None

df_trades = cargar_datos_usa()

if df_trades is None:
    st.error("❌ No se encontró 'reporte_trades_para_USA.csv'.")
    st.stop()

st.title("🇺🇸 Análisis de Estrategia - Acciones USA")

# ── 1. Solo cerrados ──────────────────────────────────────────────────────────
df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

if df_cerrados.empty:
    st.warning("No hay trades cerrados en el archivo.")
    st.stop()

# ── 2. PnL por trade ──────────────────────────────────────────────────────────
# Compra = +X (egreso), Venta = -X (ingreso)
# PnL = -(sum) → positivo cuando ganaste
resumen = (
    df_cerrados
    .groupby(['Ticker', 'ID_Trade'])
    .agg(
        PnL_raw        = ('Inversion_USA', 'sum'),
        Cant_Total     = ('Cantidad_USA',  lambda x: x[x > 0].sum()),
        Precio_Entrada = ('Precio_Unitario','first'),
        Fecha_In       = ('fecha',         'min'),
        Fecha_Out      = ('fecha',         'max'),
    )
    .reset_index()
)

resumen['Resultado_USD']   = resumen['PnL_raw'] * -1
resumen['Inversion_Inicial'] = resumen['Cant_Total'] * resumen['Precio_Entrada']
resumen['Rendimiento_%']   = np.where(
    resumen['Inversion_Inicial'] > 0,
    (resumen['Resultado_USD'] / resumen['Inversion_Inicial']) * 100,
    0
)

# ── 3. Clasificación ──────────────────────────────────────────────────────────
ganadores   = resumen[resumen['Resultado_USD'] > 0]
perdedores  = resumen[resumen['Resultado_USD'] <= 0]
total       = len(resumen)
win_rate    = len(ganadores) / total * 100 if total > 0 else 0
ganancia_total = resumen['Resultado_USD'].sum()

# ── 4. DEBUG temporal (borralo cuando todo funcione) ──────────────────────────
with st.expander("🔍 Debug — primeras filas del resumen"):
    st.dataframe(resumen.head(10))
    st.write(f"Ganadores: {len(ganadores)} | Perdedores: {len(perdedores)} | Total: {total}")
    st.write(f"Resultado_USD — min: {resumen['Resultado_USD'].min():.2f}, max: {resumen['Resultado_USD'].max():.2f}")

# ── 5. Métricas ───────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Win Rate ✅",            f"{win_rate:.1f}%")
c2.metric("Ganancia Total USD",     f"$ {ganancia_total:,.2f}")
c3.metric("P&L Promedio por Trade", f"$ {resumen['Resultado_USD'].mean():,.2f}")
c4.metric("Total Trades Cerrados",  total)

st.divider()

# ── 6. Gráficos ───────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Efectividad")
    fig_pie = go.Figure(go.Pie(
        labels = ['Ganadores', 'Perdedores'],
        values = [len(ganadores), len(perdedores)],
        hole   = 0.4,
        marker_colors = ['#2ecc71', '#e74c3c'],
    ))
    fig_pie.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig_pie, use_container_width=True)

with col_right:
    st.subheader("Distribución de PnL (USD)")
    fig_hist = go.Figure(go.Histogram(
        x      = resumen['Resultado_USD'],
        nbinsx = 20,
        marker_color = '#3498db',
    ))
    fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
    fig_hist.update_layout(
        xaxis_title = "Resultado USD",
        yaxis_title = "Frecuencia",
        margin      = dict(t=20, b=40),
    )
    st.plotly_chart(fig_hist, use_container_width=True)

# ── 7. Monte Carlo ────────────────────────────────────────────────────────────
st.subheader("🎲 Simulación de Proyección (Próximos 107 Trades)")

if not ganadores.empty and not perdedores.empty:
    capital_inicial = 6000
    g_media  = float(ganadores['Resultado_USD'].mean())
    p_media  = float(abs(perdedores['Resultado_USD'].mean()))
    prob_win = win_rate / 100

    resultados_finales = []
    fig_mc = go.Figure()

    for _ in range(50):
        pasos = np.random.choice(
            [g_media, -p_media],
            size = 107,
            p    = [prob_win, 1 - prob_win]
        )
        trayectoria = capital_inicial + np.cumsum(pasos)
        resultados_finales.append(float(trayectoria[-1]))
        fig_mc.add_trace(go.Scatter(
            y          = trayectoria.tolist(),
            mode       = 'lines',
            line       = dict(width=1),
            opacity    = 0.3,
            showlegend = False,
        ))

    fig_mc.add_hline(
        y                   = capital_inicial,
        line_dash           = "dash",
        line_color          = "gray",
        annotation_text     = f"Capital inicial ${capital_inicial:,}",
        annotation_position = "bottom right",
    )
    fig_mc.update_layout(
        height      = 400,
        yaxis_title = "Capital USD",
        xaxis_title = "Nro. de Trade",
        margin      = dict(t=20, b=40),
    )
    st.plotly_chart(fig_mc, use_container_width=True)

    p10  = np.percentile(resultados_finales, 10)
    p90  = np.percentile(resultados_finales, 90)
    med  = np.mean(resultados_finales)
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Escenario Pesimista (P10)",  f"$ {p10:,.2f}")
    mc2.metric("Capital Esperado (Media)",    f"$ {med:,.2f}")
    mc3.metric("Escenario Optimista (P90)",   f"$ {p90:,.2f}")
    st.info(f"Win Rate: {win_rate:.1f}% | Ganancia media: ${g_media:.2f} | Pérdida media: ${p_media:.2f}")
else:
    st.warning("No hay suficientes datos para simular. Revisá el debug arriba.")

# ── 8. Tabla de trades ────────────────────────────────────────────────────────
st.subheader("📋 Detalle de Trades")
cols_vista = ['Ticker','ID_Trade','Fecha_In','Fecha_Out',
              'Cant_Total','Precio_Entrada','Inversion_Inicial',
              'Resultado_USD','Rendimiento_%']

st.dataframe(
    resumen[cols_vista]
    .sort_values('Resultado_USD', ascending=False)
    .style.format({
        'Inversion_Inicial': '${:,.2f}',
        'Resultado_USD':     '${:,.2f}',
        'Rendimiento_%':     '{:.2f}%',
        'Precio_Entrada':    '{:.2f}',
    })
    .background_gradient(subset=['Resultado_USD'], cmap='RdYlGn'),
    use_container_width=True,
)
