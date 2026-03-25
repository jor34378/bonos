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
        st.error(f"❌ Error al leer CSV: {e}")
        return None

def get_live_prices(tickers):
    prices = {}
    for t in tickers:
        try:
            tk = yf.Ticker(str(t).strip().upper())
            data = tk.history(period="1d")
            prices[t] = data['Close'].iloc[-1] if not data.empty else 0
        except:
            prices[t] = 0
    return prices

# --- INICIO APP ---
st.title("🚀 Dashboard de Trading de Alta Precisión")
df_trades = load_data()

if df_trades is not None:
    try:
        # --- 2. FORZAR CIERRE (Limpieza de DIS, F y decimales < 0.1) ---
        saldo_por_id = df_trades.groupby('ID_Trade')['Cantidad_USA'].sum()
        # Definimos los IDs que deben estar cerrados por tener saldo despreciable
        ids_para_cerrar = saldo_por_id[saldo_por_id.abs() < 0.1].index
        df_trades.loc[df_trades['ID_Trade'].isin(ids_para_cerrar), 'Estado_Trade'] = 'Cerrado'

        # --- 3. SEPARACIÓN DE DATOS ---
        df_abiertos_raw = df_trades[df_trades['Estado_Trade'].str.contains('Abierto', case=False, na=False)].copy()
        df_cerrados_raw = df_trades[df_trades['Estado_Trade'].str.contains('Cerrado', case=False, na=False)].copy()

        # --- 4. LÓGICA DE PPP CORREGIDA PARA ABIERTOS ---
        if not df_abiertos_raw.empty:
            # Función para calcular PPP real (solo promediando COMPRAS)
            def calcular_ppp_real(group):
                compras = group[group['Cantidad_USA'] > 0]
                if compras.empty: return 0
                return (compras['Cantidad_USA'] * compras['Precio_Unitario']).sum() / compras['Cantidad_USA'].sum()

            resumen_abiertos = df_abiertos_raw.groupby(['Ticker', 'ID_Trade']).apply(
                lambda x: pd.Series({
                    'Posicion_Acum': x['Cantidad_USA'].sum(),
                    'PPP_Compra': calcular_ppp_real(x)
                })
            ).reset_index()

            # Filtrar posiciones que ya no existen (seguridad extra)
            resumen_abiertos = resumen_abiertos[resumen_abiertos['Posicion_Acum'] > 0.1]

            with st.spinner('Actualizando precios desde Yahoo Finance...'):
                live_prices = get_live_prices(resumen_abiertos['Ticker'].unique())
            
            resumen_abiertos['Precio_Actual'] = resumen_abiertos['Ticker'].map(live_prices)
            
            # --- CÁLCULOS SOLICITADOS ---
            resumen_abiertos['Inversion_USD'] = resumen_abiertos['Posicion_Acum'] * resumen_abiertos['PPP_Compra']
            resumen_abiertos['Valuacion_USD'] = resumen_abiertos['Posicion_Acum'] * resumen_abiertos['Precio_Actual']
            resumen_abiertos['Ganancia_USD'] = resumen_abiertos['Valuacion_USD'] - resumen_abiertos['Inversion_USD']
            resumen_abiertos['Rend_%'] = (resumen_abiertos['Ganancia_USD'] / resumen_abiertos['Inversion_USD']) * 100

            # --- TABLA ESTILO SEMÁFORO (COMO TU FOTO) ---
            st.subheader("⚪ Posiciones Actuales")
            def style_pnl(v):
                color = '#910c11' if v < 0 else '#0c633a'
                return f'background-color: {color}; color: white; font-weight: bold'

            cols_ab = ['Ticker', 'ID_Trade', 'Posicion_Acum', 'PPP_Compra', 'Precio_Actual', 'Inversion_USD', 'Valuacion_USD', 'Ganancia_USD', 'Rend_%']
            st.dataframe(
                resumen_abiertos[cols_ab].style.format({
                    'Posicion_Acum': '{:.4f}', 'PPP_Compra': 'U$S {:,.2f}', 'Precio_Actual': 'U$S {:,.2f}',
                    'Inversion_USD': 'U$S {:,.2f}', 'Valuacion_USD': 'U$S {:,.2f}', 
                    'Ganancia_USD': 'U$S {:,.2f}', 'Rend_%': '{:.2f}%'
                }).applymap(style_pnl, subset=['Ganancia_USD', 'Rend_%']),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No hay trades abiertos (Saldo neto < 0.1)")

        # --- 5. MÉTRICAS Y GRÁFICOS (RESTAURADOS TOTALMENTE) ---
        st.write("---")
        resumen_stats = df_cerrados_raw.groupby(['Ticker', 'ID_Trade']).agg(
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Rendimiento_%'] = np.where(resumen_stats['Inversion_Inicial'] > 0, (resumen_stats['Neto_Flujo'] / resumen_stats['Inversion_Inicial']) * 100, 0)
        
        c1, c2 = st.columns(2); c3, c4 = st.columns(2); fig_sz = (8, 4.5)
        with c1:
            f1, ax1 = plt.subplots(figsize=fig_sz); sns.histplot(resumen_stats['Neto_Flujo'], kde=True, color='teal', ax=ax1)
            ax1.set_title("Distribución P&L (USD)"); st.pyplot(f1)
        with c2:
            f2, ax2 = plt.subplots(figsize=fig_sz)
            if not df_abiertos_raw.empty:
                pesos = resumen_abiertos.groupby('Ticker')['Inversion_USD'].sum()
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

        # --- 6. MONTE CARLO ---
        st.write("---")
        st.subheader("🎲 Proyección Monte Carlo")
        all_p = []
        for _ in range(300):
            draws = np.random.choice(resumen_stats['Neto_Flujo'], size=len(resumen_stats), replace=True)
            all_p.append(10000 + np.cumsum(draws))
        f_mc, ax_mc = plt.subplots(figsize=(16, 6))
        for p in all_p: ax_mc.plot(p, color='gray', alpha=0.03)
        ax_mc.plot(np.median(all_p, axis=0), color='gold', lw=4, label="P50"); ax_mc.legend(); st.pyplot(f_mc)

        # --- 7. TABS HISTÓRICOS ---
        st.write("---")
        t_gan, t_per = st.tabs(["✅ Cerrados Ganadores", "❌ Cerrados Perdedores"])
        fmt_h = {'Neto_Flujo': 'U$S {:,.2f}', 'Inversion_Inicial': 'U$S {:,.2f}', 'Rendimiento_%': '{:.2f}%'}
        with t_gan: st.dataframe(resumen_stats[resumen_stats['Neto_Flujo'] > 0].sort_values('Neto_Flujo', ascending=False).style.format(fmt_h), use_container_width=True, hide_index=True)
        with t_per: st.dataframe(resumen_stats[resumen_stats['Neto_Flujo'] <= 0].sort_values('Neto_Flujo', ascending=True).style.format(fmt_h), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"⚠️ Error en el procesamiento: {e}")
