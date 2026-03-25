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
        df.columns = [str(c).strip() for c in df.columns]
        
        cols_map = {c.lower(): c for c in df.columns}
        def get_col(target): return cols_map.get(target.lower())

        rename_dict = {}
        for oficial in ['Ticker', 'Inversion_USA', 'Estado_Trade', 'fecha', 'Cantidad_USA', 'Precio_Unitario', 'ID_Trade']:
            col_real = get_col(oficial)
            if col_real: rename_dict[col_real] = oficial
        
        df = df.rename(columns=rename_dict)
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
        # --- 2. LÓGICA DE CIERRE FORZADO (DIS, F y otros con decimales) ---
        # Primero agrupamos TODO por ID_Trade para ver el saldo real
        verificacion_cierre = df_trades.groupby(['Ticker', 'ID_Trade']).agg({
            'Cantidad_USA': 'sum',
            'Inversion_USA': 'sum'
        }).reset_index()

        # Definimos umbral de "Polvo de acciones" (Menos de 0.1 nominal se considera CERRADO)
        UMBRAL_CIERRE = 0.1
        tickers_a_cerrar = verificacion_cierre[verificacion_cierre['Cantidad_USA'].abs() < UMBRAL_CIERRE]['ID_Trade'].unique()
        
        # Forzamos el estado en el DF original basado en el ID_Trade
        df_trades.loc[df_trades['ID_Trade'].isin(tickers_a_cerrar), 'Estado_Trade'] = 'Cerrado'
        
        # --- 3. SEPARACIÓN DE DATOS ---
        df_trades['Estado_Trade'] = df_trades['Estado_Trade'].astype(str).str.strip().str.capitalize()
        
        df_abiertos_raw = df_trades[df_trades['Estado_Trade'] == 'Abierto'].copy()
        df_cerrados_raw = df_trades[(df_trades['Estado_Trade'] == 'Cerrado') & (df_trades['fecha'].notnull())].copy()

        # --- 4. CONSOLIDACIÓN DE TRADES ABIERTOS (EL CICLO) ---
        resumen_abiertos = df_abiertos_raw.groupby(['Ticker', 'ID_Trade']).agg(
            Fecha_In=('fecha', 'min'),
            Cant_Actual=('Cantidad_USA', 'sum'),
            Inversion_Total=('Inversion_USA', 'sum'),
            PPP_Compra=('Precio_Unitario', lambda x: (df_abiertos_raw.loc[x.index, 'Cantidad_USA'] * x).sum() / df_abiertos_raw.loc[x.index, 'Cantidad_USA'].sum() if df_abiertos_raw.loc[x.index, 'Cantidad_USA'].sum() != 0 else x.mean())
        ).reset_index()
        
        # Solo mostrar lo que realmente tiene saldo
        resumen_abiertos = resumen_abiertos[resumen_abiertos['Cant_Actual'].abs() >= UMBRAL_CIERRE]

        # Estadísticas de Cerrados (Para métricas)
        resumen_stats = df_cerrados_raw.groupby(['Ticker', 'ID_Trade']).agg(
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

        # --- 5. MÉTRICAS ---
        st.subheader("📌 Análisis de Gestión y Riesgo")
        m1, m2, m3, m4, m5 = st.columns(5)
        
        win_rate = (len(ganadores) / len(resumen_stats) * 100) if not resumen_stats.empty else 0
        m1.metric("Win Rate %", f"{win_rate:.1f}%")

        def ponderado(df):
            if df.empty or df['Inversion_Inicial'].sum() == 0: return 0
            return (df['Rendimiento_%'] * df['Inversion_Inicial']).sum() / df['Inversion_Inicial'].sum()

        m2.metric("Prom. Pond. Ganancia", f"{ponderado(ganadores):.2f}%")
        m3.metric("Prom. Pond. Pérdida", f"{ponderado(perdedores):.2f}%")
        m4.metric("Avg Trade Size (10k)", f"{resumen_stats['Size_vs_10k_%'].mean():.2f}%")
        p_factor = ganadores['Resultado_USD'].sum() / abs(perdedores['Resultado_USD'].sum()) if not perdedores.empty else 0
        m5.metric("Profit Factor", f"{p_factor:.2f}x")

        # --- 6. LISTADO DE TRADES ABIERTOS (CONSOLIDADO) ---
        st.write("---")
        st.subheader("📂 Posiciones Abiertas (Ciclos Vigentes)")
        if not resumen_abiertos.empty:
            st.write("Ingresá el Precio Actual para ver el Profit/Loss latente:")
            
            # Creamos editor para precio actual
            df_input_precios = pd.DataFrame({
                'Ticker': resumen_abiertos['Ticker'],
                'Precio_Actual': resumen_abiertos['PPP_Compra'] # Default es el PPP
            })
            
            # Sidebar o tabla para editar precios
            edited_prices = st.data_editor(df_input_precios, hide_index=True, use_container_width=True)
            
            # Mezclamos y calculamos
            resumen_abiertos = pd.merge(resumen_abiertos, edited_prices, on='Ticker')
            resumen_abiertos['P&L_Latente_USD'] = (resumen_abiertos['Precio_Actual'] - resumen_abiertos['PPP_Compra']) * resumen_abiertos['Cant_Actual']
            resumen_abiertos['Rinde_Latente_%'] = ((resumen_abiertos['Precio_Actual'] / resumen_abiertos['PPP_Compra']) - 1) * 100

            st.dataframe(resumen_abiertos.style.format({
                'Cant_Actual': '{:.4f}', 'PPP_Compra': '${:,.2f}', 
                'Precio_Actual': '${:,.2f}', 'P&L_Latente_USD': '${:,.2f}',
                'Rinde_Latente_%': '{:.2f}%'
            }).background_gradient(subset=['Rinde_Latente_%'], cmap='RdYlGn'), use_container_width=True)
        else:
            st.info("No hay trades abiertos (Saldo nominal < 0.1).")

        # --- 7. CUADRANTE SIMÉTRICO (2x2) ---
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
            fig2, ax2 = plt.subplots(figsize=fig_size)
            if not resumen_abiertos.empty:
                pesos = resumen_abiertos.groupby('Ticker')['Inversion_Total'].sum().abs()
                ax2.pie(pesos, labels=pesos.index, autopct='%1.1f%%', startangle=140, colors=sns.color_palette("viridis"))
                ax2.set_title("Asset Allocation (Trades Abiertos)")
            else:
                ax2.text(0.5, 0.5, "Sin datos abiertos", ha='center')
            st.pyplot(fig2)

        with col_f2_1:
            fig3, ax3 = plt.subplots(figsize=fig_size)
            colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in resumen_stats['Rendimiento_%']]
            ax3.scatter(resumen_stats.index, resumen_stats['Rendimiento_%'], c=colors, alpha=0.6)
            ax3.axhline(0, color='black', lw=1, ls='--')
            ax3.set_title("ROI % Individual")
            st.pyplot(fig3)

        with col_f2_2:
            fig4, ax4 = plt.subplots(figsize=fig_size)
            equity = 10000 + resumen_stats['Resultado_USD'].cumsum()
            ax4.plot(equity.values, color='royalblue', lw=2.5)
            ax4.fill_between(range(len(equity)), equity, 10000, color='royalblue', alpha=0.15)
            ax4.axhline(10000, color='red', lw=1, ls='--')
            ax4.set_title("Curva de Equidad (Cerrados)")
            st.pyplot(fig4)

        # --- 8. MONTE CARLO ---
        st.write("---")
        st.write("### 🎲 Proyección Monte Carlo")
        n_sim = st.sidebar.slider("Simulaciones", 100, 1000, 500)
        fig_mc, ax_mc = plt.subplots(figsize=(16, 7))
        all_paths = []
        for _ in range(n_sim):
            draws = np.random.choice(resumen_stats['Resultado_USD'], size=len(resumen_stats), replace=True)
            path = 10000 + np.cumsum(draws)
            all_paths.append(path)
            ax_mc.plot(path, color='gray', alpha=0.03)
        median_p50 = np.median(all_paths, axis=0)
        ax_mc.plot(median_p50, color='gold', lw=4, label="Mediana P50")
        ax_mc.legend()
        st.pyplot(fig_mc)

        # --- 9. TABS FINALES ---
        st.write("---")
        tab_ab, tab_gan, tab_per = st.tabs(["📂 Ciclos Abiertos", "✅ Ganadores", "❌ Perdedores"])
        with tab_ab:
            st.dataframe(resumen_abiertos, use_container_width=True)
        with tab_gan:
            st.dataframe(resumen_stats[resumen_stats['Resultado_USD'] > 0].sort_values('Resultado_USD', ascending=False), use_container_width=True)
        with tab_per:
            st.dataframe(resumen_stats[resumen_stats['Resultado_USD'] <= 0].sort_values('Resultado_USD', ascending=True), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Error en el procesamiento: {e}")
