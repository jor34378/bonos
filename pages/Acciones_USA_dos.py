import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Configuración de la página
st.set_page_config(page_title="Trading Analytics Dashboard", layout="wide")

st.title("📊 Dashboard de Performance & Simulación Monte Carlo")

# --- 1. CARGA DE DATOS ---
@st.cache_data # Para que no recargue el CSV en cada interacción
def load_data():
    try:
        # Cargamos el dataframe
        df = pd.read_csv('reporte_trades_para_USA.csv')
        # Limpieza básica de Tickers por si hay nulos
        df['Ticker'] = df['Ticker'].astype(str).str.strip()
        df = df[df['Ticker'] != 'nan']
        return df
    except FileNotFoundError:
        st.error("❌ No se encontró el archivo 'reporte_trades_para_USA.csv'")
        return None

df_trades = load_data()

if df_trades is not None:
    # --- 2. PROCESAMIENTO ---
    df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

    resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
        'fecha': ['min', 'max'],
        'Inversion_USA': 'sum',
        'Cantidad_USA': lambda x: x[x > 0].sum(),
        'Precio_Unitario': 'first'
    }).reset_index()

    resumen_stats.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Neto_Flujo', 'Cant_Total', 'Precio_Entrada']
    
    # Lógica Directa
    resumen_stats['Resultado_USD'] = resumen_stats['Neto_Flujo']
    resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
    resumen_stats['Precio_Salida'] = (resumen_stats['Inversion_Inicial'] + resumen_stats['Resultado_USD']) / resumen_stats['Cant_Total']
    resumen_stats['Rendimiento_%'] = (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100

    # Métricas principales
    ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
    perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()
    total_trades = len(resumen_stats)
    win_rate = (len(ganadores) / total_trades) * 100 if total_trades > 0 else 0
    ganancia_neta = resumen_stats['Resultado_USD'].sum()
    
    # --- 3. SIDEBAR (Parámetros Simulación) ---
    st.sidebar.header("Configuración Monte Carlo")
    cap_inicial = st.sidebar.number_input("Capital Inicial ($)", value=6000)
    sim_win_rate = st.sidebar.slider("Win Rate Simulado", 0.0, 1.0, float(win_rate/100))
    n_sim = st.sidebar.number_input("Número de Simulaciones", value=1000)
    volatilidad = st.sidebar.slider("Volatilidad de Retornos", 5, 50, 15)

    # --- 4. LAYOUT: MÉTRICAS TOP ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Win Rate", f"{win_rate:.1f}%")
    col2.metric("Ganancia Neta", f"${ganancia_neta:,.2f}")
    col3.metric("Trades Totales", total_trades)
    col4.metric("ROI s/ Base", f"{(ganancia_neta/cap_inicial)*100:.2f}%")

    # --- 5. GRÁFICOS DE PERFORMANCE ---
    st.subheader("Análisis de Ejecución")
    fig_perf, ax_perf = plt.subplots(1, 2, figsize=(12, 4))
    
    # Pie Chart
    ax_perf[0].pie([len(ganadores), len(perdedores)], labels=['Wins', 'Losses'],
                   autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'], startangle=140)
    ax_perf[0].set_title('Efectividad (Win Rate)')
    
    # Histograma
    sns.histplot(resumen_stats['Resultado_USD'], bins=20, color='skyblue', kde=True, ax=ax_perf[1])
    ax_perf[1].axvline(0, color='red', linestyle='--')
    ax_perf[1].set_title('Distribución de Ganancia/Pérdida')
    
    st.pyplot(fig_perf)

    # --- 6. SIMULACIÓN MONTE CARLO ---
    st.subheader(f"Simulación Monte Carlo ({n_sim} escenarios)")
    
    perdida_media = abs(perdedores['Resultado_USD'].mean()) if not perdedores.empty else 30.0
    ganancia_media = ganadores['Resultado_USD'].mean() if not ganadores.empty else 60.0
    n_trades_sim = total_trades if total_trades > 0 else 107

    resultados_finales = []
    fig_mc, ax_mc = plt.subplots(figsize=(10, 5))

    for _ in range(n_sim):
        resultado_binario = np.random.choice([1, 0], size=n_trades_sim, p=[sim_win_rate, 1-sim_win_rate])
        montos = np.where(
            resultado_binario == 1,
            np.random.normal(ganancia_media, volatilidad, n_trades_sim),
            np.random.normal(-perdida_media, volatilidad/2, n_trades_sim)
        )
        trayectoria = cap_inicial + np.cumsum(montos)
        resultados_finales.append(trayectoria[-1])
        ax_mc.plot(trayectoria, color='royalblue', alpha=0.03)

    ax_mc.axhline(cap_inicial, color='red', linestyle='--', label='Capital Inicial')
    ax_mc.set_title("Proyección de Rutas de Capital")
    ax_mc.set_xlabel("Número de Trade")
    ax_mc.set_ylabel("Capital (USD)")
    st.pyplot(fig_mc)

    # Estadísticas Monte Carlo
    resultados_finales = np.array(resultados_finales)
    st.write(f"**Esperanza de Ganancia Neta:** ${np.mean(resultados_finales)-cap_inicial:,.2f}")
    st.write(f"**Probabilidad de terminar en positivo:** {(resultados_finales > cap_inicial).mean()*100:.1f}%")

    # --- 7. TABLAS DE DETALLE ---
    st.subheader("Detalle de Operaciones")
    col_tab1, col_tab2 = st.tabs(["Ganadores 🟢", "Perdedores 🔴"])
    
    cols_mostrar = ['Ticker', 'Fecha_In', 'Fecha_Out', 'Cant_Total', 'Precio_Entrada', 'Precio_Salida', 'Inversion_Inicial', 'Resultado_USD', 'Rendimiento_%']
    
    with col_tab1:
        st.dataframe(ganadores[cols_mostrar].sort_values('Resultado_USD', ascending=False))
    
    with col_tab2:
        st.dataframe(perdedores[cols_mostrar].sort_values('Resultado_USD', ascending=True))
