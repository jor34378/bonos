import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 1. CONFIGURACIÓN (Debe ser lo primero)
st.set_page_config(page_title="Analítica de Trades USA", layout="wide")

@st.cache_data
def load_data():
    try:
        # Cargamos el CSV detectando el separador automáticamente
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=None, engine='python')
        
        # LIMPIEZA TOTAL DE COLUMNAS: Sin espacios y todo a MINÚSCULAS para mapear
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Diccionario de mapeo
        mapeo = {
            'ticker': 'Ticker',
            'inversion_usa': 'Inversion_USA',
            'estado_trade': 'Estado_Trade',
            'fecha': 'fecha',
            'cantidad_usa': 'Cantidad_USA',
            'precio_unitario': 'Precio_Unitario',
            'id_trade': 'ID_Trade'
        }
        
        df = df.rename(columns={k: v for k, v in mapeo.items() if k in df.columns})
        
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        else:
            fallback_date = [c for c in df.columns if 'fec' in c.lower() or 'dat' in c.lower()]
            if fallback_date:
                df = df.rename(columns={fallback_date[0]: 'fecha'})
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')

        return df
    except Exception as e:
        st.error(f"❌ Error al leer el archivo: {e}")
        return None

# --- LÓGICA DE LA APP ---
st.title("📊 Dashboard de Trading - Acciones USA")
df_trades = load_data()

if df_trades is not None:
    try:
        # 2. PROCESAMIENTO
        df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

        # Agregación Nombrada para evitar errores de columnas
        resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
            Fecha_In=('fecha', 'min'),
            Fecha_Out=('fecha', 'max'),
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()

        # Cálculos de resultados
        resumen_stats['Resultado_USD'] = resumen_stats['Neto_Flujo']
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Precio_Salida'] = np.where(resumen_stats['Cant_Total'] > 0, 
                                                (resumen_stats['Inversion_Inicial'] + resumen_stats['Resultado_USD']) / resumen_stats['Cant_Total'], 0)
        resumen_stats['Rendimiento_%'] = np.where(resumen_stats['Inversion_Inicial'] > 0, 
                                                (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100, 0)

        ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
        perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()
        
        total_trades = len(resumen_stats)
        win_rate = (len(ganadores) / total_trades * 100) if total_trades > 0 else 0

        # --- 3. MÉTRICAS CLAVE ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Win Rate", f"{win_rate:.1f}%")
        m2.metric("P&L Total", f"${resumen_stats['Resultado_USD'].sum():,.2f}")
        m3.metric("Trade Promedio", f"${resumen_stats['Resultado_USD'].mean():,.2f}")
        m4.metric("Capital Base", "$6,000")

        # --- 4. GRÁFICOS DE PERFORMANCE (Sin duplicados) ---
        st.write("### Análisis de Efectividad y Distribución")
        col_graf1, col_graf2 = st.columns([1, 2])
        
        with col_graf1:
            fig1, ax1 = plt.subplots(figsize=(5, 5))
            ax1.pie([len(ganadores), len(perdedores)], labels=['Wins', 'Losses'], 
                    autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'], startangle=140)
            ax1.set_title("Win Rate %")
            st.pyplot(fig1)

        with col_graf2:
            fig2, ax2 = plt.subplots(figsize=(10, 5))
            sns.histplot(resumen_stats['Resultado_USD'], kde=True, color='skyblue', ax=ax2)
            ax2.axvline(0, color='red', linestyle='--')
            ax2.set_title("Distribución de Ganancia/Pérdida (USD)")
            st.pyplot(fig2)

        # --- 5. SIMULACIÓN MONTE CARLO (Más grande y escalada) ---
        st.write("---")
        st.write("### 🎲 Proyección Monte Carlo (Escenario a Futuro)")
        
        st.sidebar.header("Parámetros de Simulación")
        cap_inicial = st.sidebar.number_input("Capital Inicial ($)", value=6000)
        n_sim = st.sidebar.slider("Simulaciones", 100, 1000, 500)
        volatilidad = st.sidebar.slider("Variabilidad USD", 5, 50, 15)

        if total_trades > 0:
            avg_win = ganadores['Resultado_USD'].mean() if not ganadores.empty else 60
            avg_loss = abs(perdedores['Resultado_USD'].mean()) if not perdedores.empty else 30
            
            fig_mc, ax_mc = plt.subplots(figsize=(16, 8)) # Escala más grande
            final_balances = []

            for _ in range(n_sim):
                eventos = np.random.choice([avg_win, -avg_loss], size=total_trades, p=[win_rate/100, 1-win_rate/100])
                # Aplicamos volatilidad a los eventos para realismo
                ruido = np.random.normal(0, volatilidad, size=total_trades)
                ruta = cap_inicial + np.cumsum(eventos + ruido)
                final_balances.append(ruta[-1])
                ax_mc.plot(ruta, color='royalblue', alpha=0.04, linewidth=1)

            ax_mc.axhline(cap_inicial, color='red', linestyle='--', linewidth=2, label="Capital Inicial")
            ax_mc.set_title(f"Simulación de {n_sim} rutas posibles basado en tu historia", fontsize=15)
            ax_mc.set_xlabel("Número de Operaciones", fontsize=12)
            ax_mc.set_ylabel("Balance de Cuenta (USD)", fontsize=12)
            ax_mc.grid(True, alpha=0.3)
            st.pyplot(fig_mc)
            
            # Estadísticas debajo del gráfico
            c_mc1, c_mc2, c_mc3 = st.columns(3)
            c_mc1.write(f"**Esperanza de Ganancia:** ${np.mean(final_balances)-cap_inicial:,.2f}")
            c_mc2.write(f"**Probabilidad de Éxito:** {(np.array(final_balances) > cap_inicial).mean()*100:.1f}%")
            c_mc3.write(f"**Peor Escenario:** ${min(final_balances):,.2f}")

        # --- 6. LISTADO DE TRADES (Ganadores y Perdedores) ---
        st.write("---")
        st.write("### 📜 Detalle de Operaciones")
        
        cols_finales = ['Ticker', 'Fecha_In', 'Fecha_Out', 'Cant_Total', 'Precio_Entrada', 'Precio_Salida', 'Inversion_Inicial', 'Resultado_USD', 'Rendimiento_%']
        
        tab_gan, tab_per = st.tabs(["✅ Ganadores", "❌ Perdedores"])
        
        with tab_gan:
            st.dataframe(ganadores[cols_finales].sort_values('Resultado_USD', ascending=False).style.format({
                'Precio_Entrada': '{:.2f}', 'Precio_Salida': '{:.2f}',
                'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'
            }), use_container_width=True)
            
        with tab_per:
            st.dataframe(perdedores[cols_finales].sort_values('Resultado_USD', ascending=True).style.format({
                'Precio_Entrada': '{:.2f}', 'Precio_Salida': '{:.2f}',
                'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'
            }), use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error en el procesamiento: {e}")
        st.write("Columnas detectadas:", list(df_trades.columns))
