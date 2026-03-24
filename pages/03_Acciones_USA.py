import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="Performance Avanzada - USA", layout="wide")

@st.cache_data
def load_data():
    try:
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=None, engine='python')
        df.columns = [str(c).strip().lower() for c in df.columns]
        mapeo = {
            'ticker': 'Ticker', 'inversion_usa': 'Inversion_USA',
            'estado_trade': 'Estado_Trade', 'fecha': 'fecha',
            'cantidad_usa': 'Cantidad_USA', 'precio_unitario': 'Precio_Unitario',
            'id_trade': 'ID_Trade'
        }
        df = df.rename(columns={k: v for k, v in mapeo.items() if k in df.columns})
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"❌ Error al leer el archivo: {e}")
        return None

st.title("🚀 Dashboard de Trading de Alta Precisión")
df_trades = load_data()

if df_trades is not None:
    try:
        # --- PROCESAMIENTO ---
        df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()
        resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
            Fecha_In=('fecha', 'min'),
            Fecha_Out=('fecha', 'max'),
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()

        # Cálculos Base
        resumen_stats['Resultado_USD'] = resumen_stats['Neto_Flujo']
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Rendimiento_%'] = np.where(resumen_stats['Inversion_Inicial'] > 0, 
                                                (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100, 0)
        
        # Métrica Solicitada: Tamaño del trade relativo a cuenta de 10k
        resumen_stats['Size_vs_10k_%'] = (resumen_stats['Inversion_Inicial'] / 10000) * 100

        ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
        perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()

        # --- MÉTRICAS SOLICITADAS (ENCABEZADO) ---
        # Promedios Ponderados (Weight = Inversión Inicial)
        def ponderado(df):
            if df.empty or df['Inversion_Inicial'].sum() == 0: return 0
            return (df['Rendimiento_%'] * df['Inversion_Inicial']).sum() / df['Inversion_Inicial'].sum()

        w_avg_gain = ponderado(ganadores)
        w_avg_loss = ponderado(perdedores)
        avg_size_10k = resumen_stats['Size_vs_10k_%'].mean()
        profit_factor = ganadores['Resultado_USD'].sum() / abs(perdedores['Resultado_USD'].sum()) if not perdedores.empty else 0

        st.subheader("📌 Métricas de Gestión de Riesgo (Benchmark 10k USD)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Prom. Ponderado Ganancia", f"{w_avg_gain:.2f}%", delta_color="normal")
        m2.metric("Prom. Ponderado Pérdida", f"{w_avg_loss:.2f}%", delta_color="inverse")
        m3.metric("Avg Trade Size (s/10k)", f"{avg_size_10k:.2f}%")
        m4.metric("Profit Factor", f"{profit_factor:.2f}x")

        # --- GRÁFICOS (MÁXIMO 4) ---
        st.write("---")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            # Gráfico 1: Distribución P&L
            fig1, ax1 = plt.subplots(figsize=(8, 4))
            sns.histplot(resumen_stats['Resultado_USD'], kde=True, color='teal', ax=ax1)
            ax1.set_title("Frecuencia de Ganancias/Pérdidas")
            st.pyplot(fig1)
            
            # Gráfico 3: ROI % por Trade (Scatter plot para ver consistencia)
            fig3, ax3 = plt.subplots(figsize=(8, 4))
            ax3.scatter(resumen_stats.index, resumen_stats['Rendimiento_%'], 
                       c=np.where(resumen_stats['Rendimiento_%'] > 0, 'g', 'r'), alpha=0.6)
            ax3.axhline(0, color='black', lw=1)
            ax3.set_title("Rendimiento % Individual por Trade")
            st.pyplot(fig3)

        with col_g2:
            # Gráfico 2: Win Rate %
            fig2, ax2 = plt.subplots(figsize=(5, 4))
            ax2.pie([len(ganadores), len(perdedores)], labels=['Wins', 'Losses'], 
                    autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'], startangle=140)
            ax2.set_title("Efectividad")
            st.pyplot(fig2)
            
            # Gráfico 4: Evolución del Capital (Equity Curve Real)
            fig4, ax4 = plt.subplots(figsize=(8, 4))
            equity_real = 10000 + resumen_stats['Resultado_USD'].cumsum()
            ax4.plot(equity_real, marker='o', linestyle='-', color='royalblue')
            ax4.set_title("Curva de Equidad Real (Base 10k)")
            st.pyplot(fig4)

        # --- SIMULACIÓN MONTE CARLO CON MEDIANA ---
        st.write("---")
        st.write("### 🎲 Simulación Monte Carlo & Mediana Estadística")
        
        n_sim = st.sidebar.slider("Simulaciones", 100, 1000, 500)
        n_trades_future = st.sidebar.number_input("Trades a proyectar", value=len(resumen_stats))

        if not resumen_stats.empty:
            fig_mc, ax_mc = plt.subplots(figsize=(16, 7))
            all_paths = []
            
            for _ in range(n_sim):
                draws = np.random.choice(resumen_stats['Resultado_USD'], size=n_trades_future, replace=True)
                path = 10000 + np.cumsum(draws)
                all_paths.append(path)
                ax_mc.plot(path, color='gray', alpha=0.03) # Caminos aleatorios en gris tenue

            # Cálculo de la Mediana (P50)
            median_path = np.median(all_paths, axis=0)
            ax_mc.plot(median_path, color='gold', linewidth=3, label="Mediana Estadística (P50)")
            ax_mc.axhline(10000, color='red', linestyle='--', label="Breakeven")
            
            ax_mc.set_title(f"Proyección de {n_trades_future} trades futuros (Basado en tu histórico)")
            ax_mc.legend()
            st.pyplot(fig_mc)

        # --- LISTADO DE TRADES DETALLADO ---
        st.write("---")
        st.write("### 📜 Detalle de Operaciones Cerradas")
        
        # Formateo de fechas y redondeo solicitado
        resumen_stats['Fecha_In'] = pd.to_datetime(resumen_stats['Fecha_In']).dt.date
        resumen_stats['Fecha_Out'] = pd.to_datetime(resumen_stats['Fecha_Out']).dt.date
        resumen_stats['Cant_Total'] = resumen_stats['Cant_Total'].round(4)
        
        cols_finales = ['Ticker', 'Fecha_In', 'Fecha_Out', 'Cant_Total', 'Precio_Entrada', 'Inversion_Inicial', 'Size_vs_10k_%', 'Resultado_USD', 'Rendimiento_%']
        
        tab1, tab2 = st.tabs(["✅ Ganadores", "❌ Perdedores"])
        fmt_config = {
            'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 
            'Rendimiento_%': '{:.2f}%', 'Size_vs_10k_%': '{:.2f}%',
            'Precio_Entrada': '{:.2f}', 'Cant_Total': '{:.4f}'
        }
        
        with tab1:
            st.dataframe(ganadores[cols_finales].style.format(fmt_config), use_container_width=True)
        with tab2:
            st.dataframe(perdedores[cols_finales].style.format(fmt_config), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Hubo un problema procesando los datos: {e}")
