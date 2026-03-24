import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Performance USA", layout="wide")

@st.cache_data
def cargar_datos():
    nombre = 'reporte_trades_para_USA.csv'
    rutas = [nombre, os.path.join('..', nombre)]
    for r in rutas:
        if os.path.exists(r):
            return pd.read_csv(r, sep=';', encoding='utf-8-sig')
    return None

reporte_trades_para_USA = cargar_datos()

if reporte_trades_para_USA is None:
    st.error("❌ No se encontró 'reporte_trades_para_USA.csv'.")
    st.stop()

# ── 1. Procesamiento ──────────────────────────────────────────────────────────
df_cerrados = reporte_trades_para_USA[reporte_trades_para_USA['Estado_Trade'] == 'Cerrado'].copy()

if df_cerrados.empty:
    st.warning("No hay trades cerrados en el archivo.")
    st.stop()

resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
    Fecha_In       = ('fecha',          'min'),
    Fecha_Out      = ('fecha',          'max'),
    Neto_Flujo     = ('Inversion_USA',  'sum'),
    Cant_Total     = ('Cantidad_USA',   lambda x: x[x > 0].sum()),
    Precio_Entrada = ('Precio_Unitario','first')
).reset_index()

# Compra = +X, Venta = -X → suma por trade negativa = ganancia → *-1 para corregir
resumen_stats['Resultado_USD']     = -resumen_stats['Neto_Flujo']
resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
resumen_stats['Precio_Salida']     = (resumen_stats['Inversion_Inicial'] + resumen_stats['Resultado_USD']) / resumen_stats['Cant_Total']
resumen_stats['Rendimiento_%']     = (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100
resumen_stats['Fecha_In']          = pd.to_datetime(resumen_stats['Fecha_In']).dt.date
resumen_stats['Fecha_Out']         = pd.to_datetime(resumen_stats['Fecha_Out']).dt.date

# ── 2. Clasificación correcta ─────────────────────────────────────────────────
# Resultado_USD > 0 → ganancia ✅ / Resultado_USD <= 0 → pérdida ❌
ganadores  = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()

total_trades  = len(resumen_stats)
win_rate      = (len(ganadores) / total_trades) * 100
loss_rate     = 100 - win_rate
avg_win       = ganadores['Resultado_USD'].mean()        if not ganadores.empty  else 0
avg_loss      = perdedores['Resultado_USD'].abs().mean() if not perdedores.empty else 0
risk_reward   = avg_win / avg_loss if avg_loss != 0 else 0
ganancia_neta = resumen_stats['Resultado_USD'].sum()
roi           = (ganancia_neta / 6000) * 100

# ── 3. Métricas ───────────────────────────────────────────────────────────────
st.title("🇺🇸 Análisis de Estrategia - Acciones USA")
st.caption("Capital Base: $6,000")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Win Rate ✅",      f"{win_rate:.1f}%")
c2.metric("Loss Rate ❌",     f"{loss_rate:.1f}%")
c3.metric("Ganancia Neta",    f"$ {ganancia_neta:,.2f}")
c4.metric("Ratio B/R",        f"1 : {risk_reward:.2f}")
c5.metric("ROI sobre 6k",     f"{roi:.2f}%")
c6.metric("Total Trades",     total_trades)

st.divider()

# ── 4. Pie + Histograma ───────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Efectividad de Trades")
    fig_pie = go.Figure(go.Pie(
        labels        = ['Wins', 'Losses'],
        values        = [len(ganadores), len(perdedores)],
        hole          = 0.4,
        marker_colors = ['#2ecc71', '#e74c3c'],
        pull          = [0.05, 0],
        textinfo      = 'label+percent',
    ))
    fig_pie.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig_pie, use_container_width=True)

with col_right:
    st.subheader("Distribución de Ganancia/Pérdida (USD)")
    fig_hist = go.Figure(go.Histogram(
        x            = resumen_stats['Resultado_USD'],
        nbinsx       = 20,
        marker_color = 'skyblue',
        opacity      = 0.8,
    ))
    fig_hist.add_vline(x=0, line_dash="dash", line_color="red",
                       annotation_text="Break even", annotation_position="top right")
    fig_hist.update_layout(
        xaxis_title = "Resultado USD",
        yaxis_title = "Frecuencia",
        margin      = dict(t=20, b=40),
    )
    st.plotly_chart(fig_hist, use_container_width=True)

st.divider()

# ── 5. Monte Carlo (con datos reales) ─────────────────────────────────────────
st.subheader("🎲 Simulación Monte Carlo — Próximos 107 Trades")

capital_inicial = 6000
ganancia_media  = float(avg_win)  if avg_win  > 0 else 30.0
perdida_media   = float(avg_loss) if avg_loss > 0 else 30.0
prob_win        = win_rate / 100
n_trades        = 107
n_simulaciones  = 1000

resultados_finales = []
fig_mc = go.Figure()

for i in range(n_simulaciones):
    eventos     = np.random.choice(
        [ganancia_media, -perdida_media],
        size = n_trades,
        p    = [prob_win, 1 - prob_win]
    )
    trayectoria = capital_inicial + np.cumsum(eventos)
    resultados_finales.append(float(trayectoria[-1]))
    if i < 200:  # graficamos solo 200 para no saturar el browser
        fig_mc.add_trace(go.Scatter(
            y          = trayectoria.tolist(),
            mode       = 'lines',
            line       = dict(color='royalblue', width=1),
            opacity    = 0.06,
            showlegend = False,
        ))

fig_mc.add_hline(
    y                   = capital_inicial,
    line_dash           = "dash",
    line_color          = "red",
    annotation_text     = f"Capital inicial ${capital_inicial:,}",
    annotation_position = "bottom right",
)
fig_mc.update_layout(
    height      = 420,
    xaxis_title = "Número de Trade",
    yaxis_title = "Capital (USD)",
    margin      = dict(t=20, b=40),
)
st.plotly_chart(fig_mc, use_container_width=True)

ganancia_esperada = np.mean(resultados_finales) - capital_inicial
prob_exito        = (np.array(resultados_finales) > capital_inicial).mean() * 100
p10               = np.percentile(resultados_finales, 10)
p90               = np.percentile(resultados_finales, 90)
media_final       = np.mean(resultados_finales)

mc1, mc2, mc3, mc4, mc5 = st.columns(5)
mc1.metric("Capital Esperado",       f"$ {media_final:,.2f}")
mc2.metric("Ganancia Esperada",      f"$ {ganancia_esperada:,.2f}")
mc3.metric("Prob. de ser rentable",  f"{prob_exito:.1f}%")
mc4.metric("Peor escenario (P10)",   f"$ {p10:,.2f}")
mc5.metric("Mejor escenario (P90)",  f"$ {p90:,.2f}")

st.info(
    f"Win Rate real: {win_rate:.1f}% | "
    f"Ganancia media: ${ganancia_media:.2f} | "
    f"Pérdida media: ${perdida_media:.2f}"
)

st.divider()

# ── 6. Tablas ─────────────────────────────────────────────────────────────────
cols_mostrar = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out',
                'Cant_Total', 'Precio_Entrada', 'Precio_Salida',
                'Inversion_Inicial', 'Resultado_USD', 'Rendimiento_%']
fmt = {
    'Precio_Entrada':    '{:.2f}',
    'Precio_Salida':     '{:.2f}',
    'Inversion_Inicial': '${:,.2f}',
    'Resultado_USD':     '${:,.2f}',
    'Rendimiento_%':     '{:.2f}%',
}

col_g, col_p = st.columns(2)
with col_g:
    st.subheader(f"🟢 Trades Ganadores ({len(ganadores)})")
    if not ganadores.empty:
        st.dataframe(
            ganadores[cols_mostrar].sort_values('Resultado_USD', ascending=False)
            .style.format(fmt).background_gradient(subset=['Resultado_USD'], cmap='Greens'),
            use_container_width=True,
        )

with col_p:
    st.subheader(f"🔴 Trades Perdedores ({len(perdedores)})")
    if not perdedores.empty:
        st.dataframe(
            perdedores[cols_mostrar].sort_values('Resultado_USD', ascending=True)
            .style.format(fmt).background_gradient(subset=['Resultado_USD'], cmap='Reds_r'),
            use_container_width=True,
        )

st.divider()
st.subheader("📋 Todos los Trades")
st.dataframe(
    resumen_stats[cols_mostrar].sort_values('Resultado_USD', ascending=False)
    .style.format(fmt).background_gradient(subset=['Resultado_USD'], cmap='RdYlGn'),
    use_container_width=True,
)
