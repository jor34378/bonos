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
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=None, engine='python')
        # Limpieza estándar que ya sabemos que funciona
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
        st.error(f"❌ Error al leer CSV: {e}")
        return None

def get_live_prices(tickers):
    prices = {}
    for t in tickers:
        try:
            # Quitamos espacios y aseguramos formato ticker USA
            ticker_clean = str(t).strip().upper()
            data = yf.Ticker(ticker_clean).history(period="1d")
            prices[t] = data['Close'].iloc[-1] if not data.empty else 0
        except:
            prices[t] = 0
    return prices

# --- INICIO APP ---
st.title("🚀 Dashboard de Trading de Alta Precisión")
df_trades = load_data()

if df_trades is not None:
    try:
        # --- 2. CIERRE FORZADO (Lógica DIS, F) ---
        check_cierre = df_trades.groupby('ID_Trade')['Cantidad_USA'].sum().abs()
        ids_cerrados = check_cierre[check_cierre < 0.1].index
        df_trades.loc[df_trades['ID_Trade'].isin(ids_cerrados), 'Estado_Trade'] = 'Cerrado'

        # --- 3. SEPARACIÓN DE DATOS ---
        df_trades['Estado_Trade'] = df_trades['Estado_Trade'].fillna('Cerrado').astype(str)
        
        # Filtramos asegurando que las columnas existen
        df_abiertos_raw = df_trades[df_trades['Estado_Trade'].str.contains('Abierto', case=False)].copy()
        df_cerrados_raw = df_trades[df_trades['Estado_Trade'].str.contains('Cerrado', case=False)].copy()

        # --- 4. MÉTRICAS DE CERRADOS ---
        resumen_stats = df_cerrados_raw.groupby(['Ticker', 'ID_Trade']).agg(
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()
        
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Rendimiento_%'] = np.where(resumen_stats['Inversion_Inicial'] > 0, (resumen_stats['Neto_Flujo'] / resumen_stats['Inversion_Inicial']) * 100, 0)
        
        ganadores = resumen_stats[resumen_stats['Neto_Flujo'] > 0]
        perdedores = resumen_stats[resumen_stats['Neto_Flujo'] <= 0]

        st.subheader("📌 Análisis de Gestión y Riesgo")
        m1, m2, m3, m4, m5 = st.columns(5)
        wr = (len(ganadores)/len(resumen_stats)*100) if len(resumen_stats)>0 else 0
        m1.metric("Win Rate", f"{wr:.1f}%")
        pf = ganadores['Neto_Flujo'].sum() / abs(perdedores['Neto_Flujo'].sum()) if not perdedores.empty else 0
        m2.metric("Profit Factor", f"{pf:.2f}x")
        m3.metric("Avg Size (10k)", f"{(resumen_stats['Inversion_Inicial'].mean()/100):.2f}%")
        m4.metric("Prom. Ganancia", f"{ganadores['Rendimiento_%'].mean():.2f}%")
        m5.metric("Prom. Pérdida", f"{perdedores['Rendimiento_%'].mean():.2f}%")

        # --- 5. TABLA POSICIONES ABIERTAS (FOTO + YFINANCE) ---
        st.write("---")
        st.subheader("⚪ Posiciones Actuales (Precios en Tiempo Real)")
        
        if not df_abiertos_raw.empty:
            # Agrupamos por ciclo
            pos_actuales = df_abiertos_raw.groupby(['Ticker', 'ID_Trade']).agg({
                'Cantidad_USA': 'sum',
                'Inversion_USA': 'sum'
            }).reset_index()
            pos_actuales.columns = ['Ticker', 'ID_Trade', 'Posicion_Acum', 'Inversion_Total']
            pos_actuales['Costo_USD'] = pos_actuales['Inversion_Total'].abs()

            with st.spinner('Consultando Yahoo Finance...'):
                live_prices = get_live_prices(pos_actuales['Ticker'].unique())
            
            pos_actuales['Precio_Mercado'] = pos_actuales['Ticker'].map(live_prices)
            pos_actuales['Valuacion_USD'] = pos_actuales['Posicion_Acum'] * pos_actuales['Precio_Mercado']
            pos_actuales['Ganancia_USD'] = pos_actuales['Valuacion_USD'] - pos_actuales['Costo_USD']
            pos_actuales['Rend_%'] = (pos_actuales['Ganancia_USD'] / pos_actuales['Costo_USD']) * 100

            # Aplicar Estilo de la Captura
            def style_pnl(v):
                color = '#910c11' if v < 0 else '#0c633a'
                return f'background-color: {color}; color: white; font-weight: bold'

            cols_mostrar = ['Ticker', 'ID_Trade', 'Posicion_Acum', 'Valuacion_USD', 'Costo_USD', 'Ganancia_USD', 'Rend_%']
            st.dataframe(
                pos_actuales[cols_mostrar].style.format({
                    'Posicion_Acum': '{:.4f}', 'Valuacion_USD': 'U$S {:,.2f}', 
                    'Costo_USD': 'U$S {:,.2f}', 'Ganancia_USD': 'U$S {:,.2f}', 'Rend_%': '{:.2f}%'
                }).applymap(style_pnl, subset=['Ganancia_USD', 'Rend_%']),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No se detectan trades abiertos (Saldo neto < 0.1)")

        # --- 6. GRÁFICOS 2x2 ---
        st.write("---")
        c1, c2 = st.columns(2); c3, c4 = st.columns(2); fig_sz = (8, 4.5)
        with c1:
            f1, ax1 = plt.subplots(figsize=fig_sz); sns.histplot(resumen_stats['Neto_Flujo'], kde=True, color='teal', ax=ax1)
            ax1.set_title("Distribución P&L (USD)"); st.pyplot(f1)
        with c2:
            f2, ax2 = plt.subplots(figsize=fig_sz)
            if not df_abiertos_raw.empty:
                pesos = pos_actuales.groupby('Ticker')['Costo_USD'].sum()
                ax2.pie(pesos, labels=pesos.index, autopct='%1.1f%%', startangle=140); ax2.set_title("Asset Allocation")
            st.pyplot(f2)
        with c3:
            f3, ax3 = plt.subplots(figsize=fig_sz); colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in resumen_stats['Rendimiento_%']]
            ax3.scatter(resumen_stats.index, resumen_stats['Rendimiento_%'], c=colors, alpha=0.6)
            ax3.axhline(0, color='black', lw=1, ls='--'); ax3.set_title("ROI % Individual"); st.pyplot(f3)
        with c4:
            f4, ax4 = plt.subplots(figsize=fig_sz); eq = 10000 + resumen_stats['Neto_Flujo'].cumsum()
            ax4.plot(eq.values, color='royalblue', lw=2.5); ax4.fill_between(range(len(eq)), eq, 10000, alpha=0.15)
            ax4.set_title("Equity Curve (Base 10k)"); st.pyplot(f4)

        # --- 7. MONTE CARLO ---
        st.write("---")
        st.subheader("🎲 Proyección Monte Carlo")
        sims = st.sidebar.slider("Simulaciones", 100, 1000, 500)
        f_mc, ax_mc = plt.subplots(figsize=(16, 6)); all_p = []
        for _ in range(sims):
            draws = np.random.choice(resumen_stats['Neto_Flujo'], size=len(resumen_stats), replace=True)
            path = 10000 + np.cumsum(draws); all_p.append(path); ax_mc.plot(path, color='gray', alpha=0.03)
        ax_mc.plot(np.median(all_p, axis=0), color='gold', lw=4, label="Mediana P50"); ax_mc.legend(); st.pyplot(f_mc)

        # --- 8. REGISTROS CERRADOS ---
        st.write("---")
        t_gan, t_per = st.tabs(["✅ Cerrados Ganadores", "❌ Cerrados Perdedores"])
        fmt_c = {'Cant_Total': '{:.4f}', 'Neto_Flujo': 'U$S {:,.2f}', 'Inversion_Inicial': 'U$S {:,.2f}', 'Rendimiento_%': '{:.2f}%'}
        with t_gan: st.dataframe(ganadores.sort_values('Neto_Flujo', ascending=False).style.format(fmt_c), use_container_width=True, hide_index=True)
        with t_per: st.dataframe(perdedores.sort_values('Neto_Flujo', ascending=True).style.format(fmt_c), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"⚠️ Error en el procesamiento: {e}")
