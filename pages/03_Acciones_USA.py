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
        # Calculamos el saldo neto real por cada ID de Trade
        saldo_por_id = df_trades.groupby('ID_Trade')['Cantidad_USA'].sum()
        ids_a_cerrar = saldo_por_id[saldo_por_id.abs() < 0.1].index
        
        # Forzamos el estado a 'Cerrado' para esos IDs
        df_trades.loc[df_trades['ID_Trade'].isin(ids_a_cerrar), 'Estado_Trade'] = 'Cerrado'

        # --- 3. SEPARACIÓN DE DATOS ---
        df_abiertos_raw = df_trades[df_trades['Estado_Trade'].str.contains('Abierto', case=False, na=False)].copy()
        df_cerrados_raw = df_trades[df_trades['Estado_Trade'].str.contains('Cerrado', case=False, na=False)].copy()

        # --- 4. PROCESAMIENTO DE ABIERTOS (EL CICLO) ---
        if not df_abiertos_raw.empty:
            # Agrupamos para obtener Cantidad Actual y PPP de compra
            # El PPP lo calculamos solo sobre las COMPRAS (cant > 0) para no distorsionar con ventas parciales
            pos_actuales = df_abiertos_raw.groupby(['Ticker', 'ID_Trade']).agg(
                Posicion_Acum=('Cantidad_USA', 'sum'),
                Inversion_Total=('Inversion_USA', lambda x: abs(x.sum())) 
            ).reset_index()

            # Calculamos el PPP implícito del trade
            pos_actuales['PPP_Compra'] = pos_actuales['Inversion_Total'] / pos_actuales['Posicion_Acum']

            with st.spinner('Consultando Yahoo Finance...'):
                live_prices = get_live_prices(pos_actuales['Ticker'].unique())
            
            pos_actuales['Precio_Actual'] = pos_actuales['Ticker'].map(live_prices)
            
            # --- LÓGICA SOLICITADA ---
            # Inversión = Cantidad * PPP
            pos_actuales['Inversion_USD'] = pos_actuales['Posicion_Acum'] * pos_actuales['PPP_Compra']
            # Valuación = Cantidad * Precio Actual
            pos_actuales['Valuacion_USD'] = pos_actuales['Posicion_Acum'] * pos_actuales['Precio_Actual']
            # Ganancia = Valuación - Inversión
            pos_actuales['Ganancia_USD'] = pos_actuales['Valuacion_USD'] - pos_actuales['Inversion_USD']
            # Rendimiento %
            pos_actuales['Rend_%'] = (pos_actuales['Ganancia_USD'] / pos_actuales['Inversion_USD']) * 100

            # --- 5. TABLA POSICIONES ABIERTAS (ESTILO SEMÁFORO) ---
            st.subheader("⚪ Posiciones Actuales")
            
            def style_pnl(v):
                color = '#910c11' if v < 0 else '#0c633a'
                return f'background-color: {color}; color: white; font-weight: bold'

            cols_ab = ['Ticker', 'ID_Trade', 'Posicion_Acum', 'PPP_Compra', 'Precio_Actual', 'Inversion_USD', 'Valuacion_USD', 'Ganancia_USD', 'Rend_%']
            st.dataframe(
                pos_actuales[cols_ab].style.format({
                    'Posicion_Acum': '{:.4f}', 'PPP_Compra': 'U$S {:,.2f}', 'Precio_Actual': 'U$S {:,.2f}',
                    'Inversion_USD': 'U$S {:,.2f}', 'Valuacion_USD': 'U$S {:,.2f}', 
                    'Ganancia_USD': 'U$S {:,.2f}', 'Rend_%': '{:.2f}%'
                }).applymap(style_pnl, subset=['Ganancia_USD', 'Rend_%']),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No hay trades abiertos significativos (DIS y F han sido filtradas).")

        # --- 6. CERRADOS Y GRÁFICOS (RESTAURADOS) ---
        resumen_stats = df_cerrados_raw.groupby(['Ticker', 'ID_Trade']).agg(
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Rendimiento_%'] = np.where(resumen_stats['Inversion_Inicial'] > 0, (resumen_stats['Neto_Flujo'] / resumen_stats['Inversion_Inicial']) * 100, 0)
        
        st.write("---")
        c1, c2 = st.columns(2); c3, c4 = st.columns(2)
        with c1:
            f1, ax1 = plt.subplots(figsize=(8,4)); sns.histplot(resumen_stats['Neto_Flujo'], kde=True, color='teal', ax=ax1)
            ax1.set_title("Distribución P&L (Cerrados)"); st.pyplot(f1)
        with c2:
            f2, ax2 = plt.subplots(figsize=(8,4)); eq = 10000 + resumen_stats['Neto_Flujo'].cumsum()
            ax2.plot(eq.values, color='royalblue', lw=2); ax2.set_title("Equity Curve"); st.pyplot(f2)
        
        # --- MONTE CARLO ---
        st.write("---")
        st.subheader("🎲 Proyección Monte Carlo")
        all_p = []
        for _ in range(300):
            d = np.random.choice(resumen_stats['Neto_Flujo'], size=len(resumen_stats), replace=True)
            all_p.append(10000 + np.cumsum(d))
        f_mc, ax_mc = plt.subplots(figsize=(16, 5))
        for p in all_p: ax_mc.plot(p, color='gray', alpha=0.05)
        ax_mc.plot(np.median(all_p, axis=0), color='gold', lw=3); st.pyplot(f_mc)

        # --- TABS HISTÓRICOS ---
        st.write("---")
        t1, t2 = st.tabs(["✅ Ganadores", "❌ Perdedores"])
        fmt_h = {'Neto_Flujo': 'U$S {:,.2f}', 'Inversion_Inicial': 'U$S {:,.2f}', 'Rendimiento_%': '{:.2f}%'}
        with t1: st.dataframe(resumen_stats[resumen_stats['Neto_Flujo'] > 0].style.format(fmt_h), use_container_width=True)
        with t2: st.dataframe(resumen_stats[resumen_stats['Neto_Flujo'] <= 0].style.format(fmt_h), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Error: {e}")
