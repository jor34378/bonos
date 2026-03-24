import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 1. CONFIGURACIÓN DE PÁGINA (Debe ser lo primero de Streamlit)
st.set_page_config(page_title="Analítica de Trades USA", layout="wide")

# 2. FUNCIÓN DE CARGA ROBUSTA
@st.cache_data
def load_data():
    try:
        # Cargamos el CSV detectando el separador automáticamente
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=None, engine='python')
        
        # Limpiamos espacios en blanco en los nombres de las columnas
        df.columns = [str(c).strip() for c in df.columns]
        
        # Normalizamos nombres de columnas clave a minúsculas para buscarlas
        col_map = {c.lower(): c for c in df.columns}
        
        # Mapeo de nombres necesarios para que el código no falle
        mapeo_necesario = {
            'ticker': 'Ticker',
            'inversion_usa': 'Inversion_USA',
            'estado_trade': 'Estado_Trade',
            'fecha': 'fecha',
            'cantidad_usa': 'Cantidad_USA',
            'precio_unitario': 'Precio_Unitario',
            'id_trade': 'ID_Trade'
        }
        
        for min_name, standard_name in mapeo_necesario.items():
            if min_name in col_map:
                df = df.rename(columns={col_map[min_name]: standard_name})
        
        # Convertir fecha a datetime
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            
        return df
    except Exception as e:
        st.error(f"❌ Error crítico al cargar el CSV: {e}")
        return None

# --- EJECUCIÓN PRINCIPAL ---
st.title("📊 Análisis de Estrategia - Acciones USA")

df_trades = load_data()

if df_trades is not None:
    # 3. PROCESAMIENTO DE TRADES CERRADOS
    # Verificamos que existan las columnas antes de filtrar
    try:
        df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

        # Agrupamos por Ticker e ID_Trade
        resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
            'fecha': ['min', 'max'],
            'Inversion_USA': 'sum',
            'Cantidad_USA': lambda x: x[x > 0].sum(), # Cantidad total comprada
            'Precio_Unitario': 'first'               # Precio de la primera compra
        }).reset_index()

        # Aplanamos columnas
        resumen_stats.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Neto_Flujo', 'Cant_Total', 'Precio_Entrada']

        # LÓGICA DIRECTA: El resultado es la suma de flujos
        resumen_stats['Resultado_USD'] = resumen_stats['Neto_Flujo']
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Precio_Salida'] = (resumen_stats['Inversion_Inicial'] + resumen_stats['Resultado_USD']) / resumen_stats['Cant_Total']
        resumen_stats['Rendimiento_%'] = (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100

        # Métricas de efectividad
        ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
        perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()

        total_trades = len(resumen_stats)
        win_rate = (len(ganadores) / total_trades) * 100 if total_trades > 0 else 0
        avg_win = ganadores['Resultado_USD'].mean() if not ganadores.empty else 0
        avg_loss = abs(perdedores['Resultado_USD'].mean()) if not perdedores.empty else 1 # Evitar div/0
        risk_reward = avg_win / avg_loss

        # --- 4. DASHBOARD INTERACTIVO ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Win Rate", f"{win_rate:.1f}%")
        col2.metric("Ganancia Neta", f"${resumen_stats['Resultado_USD'].sum():,.2f}")
        col3.metric("Ratio B/R", f"1 : {risk_reward:.2f}")
        col4.metric("ROI (Base 6k)", f"{(resumen_stats['Resultado_USD'].sum()/6000)*100:.2f}%")

        # Gráficos de Performance
        st.write("---")
        fig, ax = plt.subplots(1, 2, figsize=(14, 5))
        
        # Pie Chart
        ax[0].pie([len(ganadores), len(perdedores)], labels=['Wins', 'Losses'],
                autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'], startangle=140)
        ax[0].set_title('Efectividad de Trades')

        # Histograma
        sns.histplot(resumen_stats['Resultado_USD'], bins=20, color='skyblue', kde=True, ax=ax[1])
        ax[1].axvline(0, color='red', linestyle='--')
        ax[1].set_title('Distribución de Ganancia/Pérdida (USD)')
        st.pyplot(fig)

        # --- 5. SIMULACIÓN MONTE CARLO ---
        st.sidebar.header("Parámetros Monte Carlo")
        cap_inicial = st.sidebar.number_input("Capital Inicial", value=6000)
        n_sim = st.sidebar.slider("Simulaciones", 100, 2000, 1000)
        volatilidad = st.sidebar.slider("Volatilidad USD", 5, 50, 15)

        st.subheader(f"Simulación Monte Carlo: {total_trades} Trades")
        
        resultados_finales = []
        fig_mc, ax_mc = plt.subplots(figsize=(12, 6))

        for _ in range(n_sim):
            resultado_binario = np.random.choice([1, 0], size=total_trades if total_trades > 0 else 107, p=[win_rate/100, 1-(win_rate/100)])
            montos = np.where(
                resultado_binario == 1,
                np.random.normal(avg_win if avg_win > 0 else 60, volatilidad, len(resultado_binario)),
                np.random.normal(-avg_loss if avg_loss > 0 else -30, volatilidad/2, len(resultado_binario))
            )
            trayectoria = cap_inicial + np.cumsum(montos)
            resultados_finales.append(trayectoria[-1])
            ax_mc.plot(trayectoria, color='royalblue', alpha=0.03)

        ax_mc.axhline(cap_inicial, color='red', linestyle='--')
        ax_mc.set_title("Proyección de Rutas de Capital")
        st.pyplot(fig_mc)

        # Tablas de Detalle
        st.write("---")
        st.subheader("Listado de Trades")
        cols_mostrar = ['Ticker', 'Fecha_In', 'Fecha_Out', 'Cant_Total', 'Precio_Entrada', 'Precio_Salida', 'Inversion_Inicial', 'Resultado_USD', 'Rendimiento_%']
        
        tab1, tab2 = st.tabs(["Ganadores ✅", "Perdedores ❌"])
        with tab1:
            st.dataframe(ganadores[cols_mostrar].sort_values('Resultado_USD', ascending=False))
        with tab2:
            st.dataframe(perdedores[cols_mostrar].sort_values('Resultado_USD', ascending=True))

    except Exception as e:
        st.error(f"❌ Error en el procesamiento de datos: {e}")
        st.info("Asegúrate de que las columnas 'Inversion_USA', 'Cantidad_USA' y 'Estado_Trade' existan en el CSV.")

else:
    st.warning("⚠️ Esperando el archivo CSV para procesar...")
