import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 1. CONFIGURACIÓN INICIAL
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
        st.error(f"❌ Error crítico al leer el CSV: {e}")
        return None

# --- INICIO DE LA APP ---
st.title("🚀 Dashboard de Trading de Alta Precisión (Benchmark 10k)")
df_trades = load_data()

if df_trades is not None:
    try:
        # --- 2. PROCESAMIENTO ---
        # Separamos Abiertos y Cerrados
        df_abiertos = df_trades[df_trades['Estado_Trade'] == 'Abierto'].copy()
        df_cerrados = df_trades[(df_trades['Estado_Trade'] == 'Cerrado') & (df_trades['fecha'].notnull())].copy()

        # Estadísticas de Cerrados
        resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
            Fecha_In=('fecha', 'min'),
            Fecha_Out=('fecha', 'max'),
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()

        resumen_stats['Resultado_USD'] = resumen_stats['Neto_Flujo']
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Rendimiento_%'] = np.where(resumen_stats['Inversion_Inicial'] > 0, 
                                                (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100, 0)
        resumen_stats['Size_vs_10k_%'] = (resumen_stats['Inversion_Inicial'] / 10000) * 100

        ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0]
        perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0]

        # --- 3. MÉTRICAS PONDERADAS (ENCABEZADO REORGANIZADO) ---
        def ponderado(df):
            if df.empty or df['Inversion_Inicial'].sum() == 0: return 0
            return (df['Rendimiento_%'] * df['Inversion_Inicial']).sum() / df['Inversion_Inicial'].sum()

        st.subheader("📌 Análisis de Gestión y Riesgo")
        m1, m2, m3, m4, m5 = st.columns(5)
        
        win_rate = (len(ganadores) / len(resumen_stats) * 100) if not resumen_stats.empty else 0
        
        m1.metric("Win Rate", f"{win_rate:.1f}%")
        m2.metric("Prom. Pond. Ganancia", f"{ponderado(ganadores):.2f}%")
        m3.metric("Prom. Pond. Pérdida", f"{ponderado(perdedores):.2f}%")
        m4.metric("Avg Size (s/10k)", f"{resumen_stats['Size_vs_10k_%'].mean():.2f}%")
        
        p_factor = ganadores['Resultado_USD'].sum() / abs(perdedores['Resultado_USD'].sum()) if not perdedores.empty else 0
        m5.metric("Profit Factor", f"{p_factor:.2f}x")

        # --- 4. TRADES ABIERTOS (NUEVA SECCIÓN PRIORITARIA) ---
        st.write("---")
        st.subheader("📊 Monitoreo de Posiciones Abiertas")
        if not df_abiertos.empty:
            # Agrupamos para ver posición actual por Ticker
            portfolio_viva = df_abiertos.groupby('Ticker').agg({
                'Cantidad_USA': 'sum',
                'Inversion_USA': 'sum' # Asumiendo que esto refleja el costo actual
            }).reset_index()
            portfolio_viva = portfolio_viva[portfolio_viva['Cantidad_USA'] > 0]
            st.dataframe(portfolio_viva.style.format({'Inversion_USA': '${:,.2f}', 'Cantidad_USA': '{:.4f}'}), use_container_width=True)
        else:
            st.info("No hay posiciones abiertas actualmente.")

        # --- 5. CUADRANTE SIMÉTRICO (GRÁFICOS 2x2) ---
        st.write("---")
        fig_size = (8, 5)
        col_f1_1, col_f1_2 = st.columns(2)
        col_f2_1, col_f2_2 = st.columns(2)

        with col_f1_1:
            fig1, ax1 = plt.subplots(figsize=fig_size)
            sns.histplot(resumen_stats['Resultado_USD'], kde=True, color='teal', ax=ax1)
            ax1.set_title("Distribución de Ganancia/Pérdida (USD)")
            st.pyplot(fig1)

        with col_f1_2:
            # GRÁFICO DE TORTA: PESO DE LA INVERSIÓN (ABIERTOS)
            fig2, ax2 = plt.subplots(figsize=fig_size)
            if not df_abiertos.empty:
                pie_data = df_abiertos.groupby('Ticker')['Inversion_USA'].sum().abs()
                ax2.pie(pie_data, labels=pie_data.index, autopct='%1.1f%%', startangle=140, colors=sns.color_palette("viridis", len(pie_data)))
                ax2.set_title("Distribución de Capital (Posiciones Abiertas)")
            else:
                ax2.text(0.5, 0.5, "Sin datos abiertos", ha='center')
            st.pyplot(fig2)

        with col_f2_1:
            fig3, ax3 = plt.subplots(figsize=fig_size)
            colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in resumen_stats['Rendimiento_%']]
            ax3.scatter(resumen_stats.index, resumen_stats['Rendimiento_%'], c=colors, alpha=0.6)
            ax3.axhline(0, color='black', lw=1, ls='--')
            ax3.set_title("Consistencia: ROI % Individual")
            st.pyplot(fig3)

        with col_f2_2:
            fig4, ax4 = plt.subplots(figsize=fig_size)
            equity = 10000 + resumen_stats['Resultado_USD'].cumsum()
            ax4.plot(equity.values, color='royalblue', lw=2.5)
            ax4.fill_between(range(len(equity)), equity, 10000, color='royalblue', alpha=0.15)
            ax4.axhline(10000, color='red', lw=1, ls='--')
            ax4.set_title("Curva de Equidad (Base 10k USD)")
            st.pyplot(fig4)

        # --- 6. MONTE CARLO ---
        st.write("---")
        st.write("### 🎲 Proyección Monte Carlo & Mediana (P50)")
        n_sim = st.sidebar.slider("Simulaciones", 100, 1000, 500)
        
        fig_mc, ax_mc = plt.subplots(figsize=(16, 7))
        all_paths = []
        for _ in range(n_sim):
            draws = np.random.choice(resumen_stats['Resultado_USD'], size=len(resumen_stats), replace=True)
            path = 10000 + np.cumsum(draws)
            all_paths.append(path)
            ax_mc.plot(path, color='gray', alpha=0.03)
        
        median_p50 = np.median(all_paths, axis=0)
        ax_mc.plot(median_p50, color='gold', lw=4, label="Mediana P50 (Camino más probable)")
        ax_mc.axhline(10000, color='red', ls='--', label="Breakeven (10k)")
        ax_mc.legend()
        st.pyplot(fig_mc)

        # --- 7. LISTADO DETALLADO (TABS) ---
        st.write("---")
        st.subheader("📜 Historial Detallado de Operaciones")
        df_disp = resumen_stats.copy()
        df_disp['Fecha_In'] = df_disp['Fecha_In'].dt.date
        df_disp['Fecha_Out'] = df_disp['Fecha_Out'].dt.date
        
        fmt = {
            'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 
            'Rendimiento_%': '{:.2f}%', 'Size_vs_10k_%': '{:.2f}%',
            'Precio_Entrada': '{:.2f}', 'Cant_Total': '{:.4f}'
        }
        cols_tab = ['Ticker', 'Fecha_In', 'Fecha_Out', 'Cant_Total', 'Precio_Entrada', 'Inversion_Inicial', 'Size_vs_10k_%', 'Resultado_USD', 'Rendimiento_%']
        
        t1, t2 = st.tabs(["✅ Cerrados Ganadores", "❌ Cerrados Perdedores"])
        with t1:
            st.dataframe(df_disp[df_disp['Resultado_USD'] > 0].sort_values('Resultado_USD', ascending=False)[cols_tab].style.format(fmt), use_container_width=True)
        with t2:
            st.dataframe(df_disp[df_disp['Resultado_USD'] <= 0].sort_values('Resultado_USD', ascending=True)[cols_tab].style.format(fmt), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Error en el procesamiento: {e}")
