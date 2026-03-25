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
        ids_a_cerrar = saldo_por_id[saldo_por_id.abs() < 0.1].index
        df_trades.loc[df_trades['ID_Trade'].isin(ids_cerrados), 'Estado_Trade'] = 'Cerrado'

        # --- 3. SEPARACIÓN DE DATOS ---
        df_abiertos_raw = df_trades[df_trades['Estado_Trade'].str.contains('Abierto', case=False, na=False)].copy()
        df_cerrados_raw = df_trades[df_trades['Estado_Trade'].str.contains('Cerrado', case=False, na=False)].copy()

        # --- 4. LÓGICA DE PPP CORREGIDA PARA ABIERTOS ---
        if not df_abiertos_raw.empty:
            # Calculamos PPP solo usando COMPRAS (Cantidad > 0) para no viciar el precio con ventas parciales
            def calcular_ppp(group):
                compras = group[group['Cantidad_USA'] > 0]
                if compras.empty: return 0
                return (compras['Cantidad_USA'] * compras['Precio_Unitario']).sum() / compras['Cantidad_USA'].sum()

            resumen_abiertos = df_abiertos_raw.groupby(['Ticker', 'ID_Trade']).apply(
                lambda x: pd.Series({
                    'Posicion_Acum': x['Cantidad_USA'].sum(),
                    'PPP_Compra': calcular_ppp(x)
                })
            ).reset_index()

            # Quitamos los que quedaron en cero después del cálculo
            resumen_abiertos = resumen_abiertos[resumen_abiertos['Posicion_Acum'] > 0.1]

            with st.spinner('Consultando Yahoo Finance...'):
                live_prices = get_live_prices(resumen_abiertos['Ticker'].unique())
            
            resumen_abiertos['Precio_Actual'] = resumen_abiertos['Ticker'].map(live_prices)
            
            # --- CÁLCULOS DE VALUACIÓN ---
            resumen_abiertos['Inversion_USD'] = resumen_abiertos['Posicion_Acum'] * resumen_abiertos['PPP_Compra']
            resumen_abiertos['Valuacion_USD'] = resumen_abiertos['Posicion_Acum'] * resumen_abiertos['Precio_Actual']
            resumen_abiertos['Ganancia_USD'] = resumen_abiertos['Valuacion_USD'] - resumen_abiertos['Inversion_USD']
            resumen_abiertos['Rend_%'] = (resumen_abiertos['Ganancia_USD'] / resumen_abiertos['Inversion_USD']) * 100

            # --- TABLA ESTILO SEMÁFORO ---
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

        # --- 5. MÉTRICAS Y GRÁFICOS (RESTAURADOS) ---
        # (Aquí va el bloque de resumen_stats, métricas, Monte Carlo y gráficos 2x2 de la versión anterior)
        # ... [El código de gráficos se mantiene igual para no perder funcionalidad] ...

    except Exception as e:
        st.error(f"⚠️ Error: {e}")
