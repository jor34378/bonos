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
        df_cerrados = df_trades[(df_trades['Estado_Trade'] == 'Cerrado') & (df_trades['fecha'].notnull())].copy()

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

        ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
        perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()

        # --- MÉTRICAS DEL ENCABEZADO ---
        def ponderado(df):
            if df.empty or df['Inversion_Inicial'].sum() == 0: return 0
            return (df['Rendimiento_%'] * df['Inversion_Inicial']).sum() / df['Inversion_Inicial'].sum()

        st.subheader("📌 Métricas de Gestión de Riesgo (Benchmark 10k USD)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Prom. Ponderado Ganancia", f"{ponderado(ganadores):.2f}%")
        m2.metric("Prom. Ponderado Pérdida", f"{ponderado(perdedores):.2f}%")
        m3.metric("Avg Trade Size (s/10k)", f"{resumen_stats['Size_vs_10k_%'].mean():.2f}%")
        m4.metric("Profit Factor", f"{(ganadores['Resultado_USD'].sum() / abs(perdedores['Resultado_USD'].sum())):.2f}x" if not perdedores.empty else "N/A")

        # --- CUADRANTE DE GRÁFICOS (2x2) ---
        st.write("---")
        fila1_col1, fila1_col2 = st.columns(2)
        fila2_col1, fila2_col2 = st.columns(2)
        
        # Ajustamos un tamaño de figura estándar para todos
        fig_size = (7, 4)

        with fila1_col1:
            # G1: Histograma
            fig1, ax1 = plt.subplots(figsize=fig_size)
            sns.histplot(resumen_stats['Resultado_USD'], kde=True, color='teal', ax=ax1)
            ax1.set_title("Distribución de P&L (USD)")
            st.pyplot(fig1)

        with fila1_col2:
            # G2: Win Rate (Torta ajustada)
            fig2, ax2 = plt.subplots(figsize=fig_size)
            ax2.pie([len(ganadores), len(perdedores)], labels=['Wins', 'Losses'], 
                    autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'], startangle=140)
            ax2.set_title("Efectividad (Win Rate)")
            st.pyplot(fig2)

        with fila2_col1:
            # G3: Consistencia ROI
            fig3, ax3 = plt.subplots(figsize=fig_size)
            colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in resumen_stats['Rendimiento_%']]
            ax3.scatter(resumen_stats.index, resumen_stats['Rendimiento_%'], c=colors, alpha=0.6)
            ax3.axhline(0, color='black', lw=1, ls='--')
            ax3.set_title("Consistencia: ROI % por Operación")
            ax3.set_ylabel("Rendimiento %")
            st.pyplot(fig3)

        with fila2_col2:
            # G4: Equity Curve
            fig4, ax4 = plt.subplots(figsize=fig_size)
            equity_curve = (10000 + resumen_stats['Resultado_USD'].cumsum()).values
            ax4.plot(equity_curve, color='royalblue', lw=2, marker='.', markersize=4)
            ax4.fill_between(range(len(equity_curve)), equity_curve, 10000, alpha=0.1, color='royalblue')
            ax4.axhline(10000, color='black', lw=0.8, ls='--')
            ax4.set_title("Evolución del Capital (Base 10k)")
            st.pyplot(fig4)

        # --- MONTE CARLO ---
        st.write("---")
        st.write("### 🎲 Simulación Monte Carlo & Mediana (P50)")
        n_sim = st.sidebar.slider("Simulaciones", 100, 1000, 500)
        
        fig_mc, ax_mc = plt.subplots(figsize=(16, 6))
        rutas = []
        for _ in range(n_sim):
            cambios = np.random.choice(resumen_stats['Resultado_USD'], size=len(resumen_stats), replace=True)
            ruta = 10000 + np.cumsum(cambios)
            rutas.append(ruta)
            ax_mc.plot(ruta, color='gray', alpha=0.03)
        
        # Línea de Mediana (P50)
        ax_mc.plot(np.median(rutas, axis=0), color='gold', lw=4, label="Mediana (Camino más probable)")
        ax_mc.axhline(10000, color='red', ls='--')
        ax_mc.set_ylabel("Balance USD")
        ax_mc.legend()
        st.pyplot(fig_mc)

        # --- TABLAS DE TRADES ---
        st.write("---")
        st.subheader("📜 Detalle de Operaciones")
        
        # Clonamos para formatear sin romper la lógica de los gráficos
        df_display = resumen_stats.copy()
        df_display['Fecha_In'] = pd.to_datetime(df_display['Fecha_In']).dt.date
        df_display['Fecha_Out'] = pd.to_datetime(df_display['Fecha_Out']).dt.date
        
        fmt = {
            'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 
            'Rendimiento_%': '{:.2f}%', 'Size_vs_10k_%': '{:.2f}%',
            'Precio_Entrada': '{:.2f}', 'Cant_Total': '{:.4f}'
        }
        
        gan_disp = df_display[df_display['Resultado_USD'] > 0].sort_values('Resultado_USD', ascending=False)
        per_disp = df_display[df_display['Resultado_USD'] <= 0].sort_values('Resultado_USD', ascending=True)

        t1, t2 = st.tabs(["Ganadores ✅", "Perdedores ❌"])
        cols_tab = ['Ticker', 'Fecha_In', 'Fecha_Out', 'Cant_Total', 'Precio_Entrada', 'Inversion_Inicial', 'Size_vs_10k_%', 'Resultado_USD', 'Rendimiento_%']
        
        with t1: st.dataframe(gan_disp[cols_tab].style.format(fmt), use_container_width=True)
        with t2: st.dataframe(per_disp[cols_tab].style.format(fmt), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Error en el procesamiento: {e}")
