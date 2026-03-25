import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import yfinance as yf

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Performance Avanzada - USA", layout="wide")

@st.cache_data
def load_data():
    try:
        # Cargamos detectando separador automáticamente
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=None, engine='python')
        
        # Limpieza de encabezados (Mantenemos la lógica que te funcionaba)
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
        else:
            cols_fec = [c for c in df.columns if 'fec' in c or 'dat' in c]
            if cols_fec:
                df = df.rename(columns={cols_fec[0]: 'fecha'})
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"❌ Error crítico al leer el CSV: {e}")
        return None

def get_live_prices(tickers):
    prices = {}
    for t in tickers:
        try:
            # Limpiamos el ticker por si tiene espacios
            tk = yf.Ticker(str(t).strip().upper())
            data = tk.history(period="1d")
            prices[t] = data['Close'].iloc[-1] if not data.empty else 0
        except:
            prices[t] = 0
    return prices

# --- INICIO DE LA APP ---
st.title("🚀 Dashboard de Trading de Alta Precisión")
df_trades = load_data()

if df_trades is not None:
    try:
        # --- 2. LÓGICA DE CIERRE FORZADO (DIS, F) ---
        # Si la suma de cantidades es casi cero, forzamos estado a 'Cerrado'
        check_cierre = df_trades.groupby('ID_Trade')['Cantidad_USA'].sum().abs()
        ids_cerrados = check_cierre[check_cierre < 0.1].index
        df_trades.loc[df_trades['ID_Trade'].isin(ids_cerrados), 'Estado_Trade'] = 'Cerrado'

        # --- 3. SEPARACIÓN DE DATOS ---
        df_trades['Estado_Trade'] = df_trades['Estado_Trade'].astype(str).str.strip().str.capitalize()
        df_abiertos_raw = df_trades[df_trades['Estado_Trade'] == 'Abierto'].copy()
        df_cerrados_raw = df_trades[(df_trades['Estado_Trade'] == 'Cerrado') & (df_trades['fecha'].notnull())].copy()

        # --- 4. CÁLCULO DE CERRADOS (ESTADÍSTICAS) ---
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

        # --- 5. MÉTRICAS PONDERADAS ---
        st.subheader("📌 Análisis de Gestión y Riesgo")
        m1, m2, m3, m4, m5 = st.columns(5)
        
        wr = (len(ganadores)/len(resumen_stats)*100) if not resumen_stats.empty else 0
        m1.metric("Win Rate", f"{wr:.1f}%")
        
        def ponderado(df):
            if df.empty or df['Inversion_Inicial'].sum() == 0: return 0
            return (df['Rendimiento_%'] * df['Inversion_Inicial']).sum() / df['Inversion_Inicial'].sum()

        m2.metric("Pond. Ganancia", f"{ponderado(ganadores):.2f}%")
        m3.metric("Pond. Pérdida", f"{ponderado(perdedores):.2f}%")
        m4.metric("Avg Size (10k)", f"{resumen_stats['Size_vs_10k_%'].mean():.2f}%")
        
        pf = ganadores['Resultado_USD'].sum() / abs(perdedores['Resultado_USD'].sum()) if not perdedores.empty else 0
        m5.metric("Profit Factor", f"{pf:.2f}x")

        # --- 6. TABLA POSICIONES ABIERTAS (ESTILO CAPTURA + LIVE) ---
        st.write("---")
        st.subheader("⚪ Posiciones Actuales (Ciclos Abiertos)")
        
        if not df_abiertos_raw.empty:
            resumen_abiertos = df_abiertos_raw.groupby(['Ticker', 'ID_Trade']).agg(
                Posicion_Acum=('Cantidad_USA', 'sum'),
                Costo_USD=('Inversion_USA', lambda x: abs(x.sum()))
            ).reset_index()

            with st.spinner('Consultando yfinance...'):
                precios_live = get_live_prices(resumen_abiertos['Ticker'].unique())
            
            resumen_abiertos['Precio_Mercado'] = resumen_abiertos['Ticker'].map(precios_live)
            resumen_abiertos['Valuacion_USD'] = resumen_abiertos['Posicion_Acum'] * resumen_abiertos['Precio_Mercado']
            resumen_abiertos['Ganancia_USD'] = resumen_abiertos['Valuacion_USD'] - resumen_abiertos['Costo_USD']
            resumen_abiertos['Rend_%'] = (resumen_abiertos['Ganancia_USD'] / resumen_abiertos['Costo_USD']) * 100

            # Estilo semáforo
            def style_pnl(v):
                color = '#910c11' if v < 0 else '#0c633a'
                return f'background-color: {color}; color: white; font-weight: bold'

            cols_ab = ['Ticker', 'ID_Trade', 'Posicion_Acum', 'Valuacion_USD', 'Costo_USD', 'Ganancia_USD', 'Rend_%']
            st.dataframe(
                resumen_abiertos[cols_ab].style.format({
                    'Posicion_Acum': '{:.4f}', 'Valuacion_USD': 'U$S {:,.2f}', 
                    'Costo_USD': 'U$S {:,.2f}', 'Ganancia_USD': 'U$S {:,.2f}', 'Rend_%': '{:.2f}%'
                }).applymap(style_pnl, subset=['Ganancia_USD', 'Rend_%']),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No hay trades abiertos.")

        # --- 7. CUADRANTE DE GRÁFICOS (2x2) ---
        st.write("---")
        col_f1_1, col_f1_2 = st.columns(2)
        col_f2_1, col_f2_2 = st.columns(2)
        fig_sz = (8, 5)

        with col_f1_1:
            fig1, ax1 = plt.subplots(figsize=fig_sz)
            sns.histplot(resumen_stats['Resultado_USD'], kde=True, color='teal', ax=ax1)
            ax1.set_title("Distribución de Ganancia/Pérdida (USD)")
            st.pyplot(fig1)

        with col_f1_2:
            fig2, ax2 = plt.subplots(figsize=fig_sz)
            if not df_abiertos_raw.empty:
                pesos = resumen_abiertos.groupby('Ticker')['Costo_USD'].sum()
                ax2.pie(pesos, labels=pesos.index, autopct='%1.1f%%', startangle=140)
                ax2.set_title("Asset Allocation (Abiertos)")
            else:
                ax2.text(0.5, 0.5, "Sin posiciones", ha='center')
            st.pyplot(fig2)

        with col_f2_1:
            fig3, ax3 = plt.subplots(figsize=fig_sz)
            colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in resumen_stats['Rendimiento_%']]
            ax3.scatter(resumen_stats.index, resumen_stats['Rendimiento_%'], c=colors, alpha=0.6)
            ax3.axhline(0, color='black', lw=1, ls='--')
            ax3.set_title("Consistencia: ROI % Individual")
            st.pyplot(fig3)

        with col_f2_2:
            fig4, ax4 = plt.subplots(figsize=fig_sz)
            equity = 10000 + resumen_stats['Resultado_USD'].cumsum()
            ax4.plot(equity.values, color='royalblue', lw=2.5)
            ax4.fill_between(range(len(equity)), equity, 10000, alpha=0.15)
            ax4.axhline(10000, color='red', lw=1, ls='--')
            ax4.set_title("Curva de Equidad (Cerrados)")
            st.pyplot(fig4)

        # --- 8. MONTE CARLO ---
        st.write("---")
        st.subheader("🎲 Proyección Monte Carlo & Mediana (P50)")
        n_sim = st.sidebar.slider("Simulaciones", 100, 1000, 500)
        fig_mc, ax_mc = plt.subplots(figsize=(16, 7))
        all_paths = []
        for _ in range(n_sim):
            draws = np.random.choice(resumen_stats['Resultado_USD'], size=len(resumen_stats), replace=True)
            path = 10000 + np.cumsum(draws)
            all_paths.append(path)
            ax_mc.plot(path, color='gray', alpha=0.03)
        ax_mc.plot(np.median(all_paths, axis=0), color='gold', lw=4, label="Mediana P50")
        ax_mc.axhline(10000, color='red', ls='--')
        ax_mc.legend()
        st.pyplot(fig_mc)

        # --- 9. TABS DE REGISTROS HISTÓRICOS ---
        st.write("---")
        st.subheader("📜 Detalle de Operaciones Cerradas")
        df_disp = resumen_stats.copy()
        df_disp['Fecha_In'] = df_disp['Fecha_In'].dt.date
        df_disp['Fecha_Out'] = df_disp['Fecha_Out'].dt.date
        
        fmt_h = {'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 'Rendimiento_%': '{:.2f}%'}
        cols_h = ['Ticker', 'Fecha_In', 'Fecha_Out', 'Cant_Total', 'Precio_Entrada', 'Inversion_Inicial', 'Resultado_USD', 'Rendimiento_%']
        
        t1, t2 = st.tabs(["✅ Ganadores", "❌ Perdedores"])
        with t1:
            st.dataframe(df_disp[df_disp['Resultado_USD'] > 0].sort_values('Resultado_USD', ascending=False)[cols_h].style.format(fmt_h), use_container_width=True, hide_index=True)
        with t2:
            st.dataframe(df_disp[df_disp['Resultado_USD'] <= 0].sort_values('Resultado_USD', ascending=True)[cols_h].style.format(fmt_h), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"⚠️ Error en el procesamiento: {e}")
