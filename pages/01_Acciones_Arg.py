import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import os

st.set_page_config(page_title="Acciones Argentinas", layout="wide")

@st.cache_data
def cargar_datos_argentina():
    archivo = 'reporte_trades_para_ARG.csv'
    if not os.path.exists(archivo):
        st.error(f"⚠️ No se encuentra '{archivo}'")
        return None

    df = pd.read_csv(archivo, sep=None, engine='python', encoding='utf-8-sig')
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    mapeo = {
        'ticker': 'Ticker', 'operado': 'fecha', 'cantidad': 'Cantidad',
        'precio': 'Precio', 'precio_usd': 'Precio_USD',
        'inversion_usd': 'Inversion_USD', 'operacion': 'Operacion'
    }
    df = df.rename(columns={k: v for k, v in mapeo.items() if k in df.columns})
    
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    
    # --- PROCESAMIENTO ---
    df = df.sort_values(['Ticker', 'fecha'])
    df['Posicion_Acum'] = df.groupby('Ticker')['Cantidad'].cumsum()

    # Limpieza de residuos para cerrar IRSA y FERR
    df.loc[df['Posicion_Acum'].abs() < 1.0, 'Posicion_Acum'] = 0.0
    
    df['Es_Cierre'] = (df['Posicion_Acum'] == 0)
    df['ID_Trade'] = (df.groupby('Ticker')['Es_Cierre'].shift(fill_value=False)
                      .groupby(df['Ticker']).cumsum() + 1)
    
    status = df.groupby(['Ticker', 'ID_Trade'])['Posicion_Acum'].last().apply(
        lambda x: 'Abierto' if abs(x) >= 1.0 else 'Cerrado'
    ).reset_index(name='Estado_Trade')
    
    return df.merge(status, on=['Ticker', 'ID_Trade'])

def obtener_precios_merval(tickers):
    if not tickers: return {}
    tickers_yf = [f"{t}.BA" for t in tickers]
    try:
        data = yf.download(tickers_yf, period="1d", progress=False)['Close']
        precios = {}
        for t in tickers:
            col = f"{t}.BA"
            if col in data.columns:
                val = data[col].dropna()
                if not val.empty: precios[t] = val.iloc[-1]
            elif len(tickers) == 1:
                precios[t] = data.iloc[-1]
        return precios
    except:
        return {}

# --- INTERFAZ ---
st.title("🇦🇷 Cartera de Acciones Argentinas")
df_arg = cargar_datos_argentina()

if df_arg is not None:
    mep_hoy = st.sidebar.number_input("Cotización MEP", value=1433.21)

    # --- POSICIONES ABIERTAS ---
    st.subheader("🔵 Posiciones Actuales")
    df_abiertos = df_arg[df_arg['Estado_Trade'] == 'Abierto'].copy()
    
    if not df_abiertos.empty:
        dict_precios = obtener_precios_merval(df_abiertos['Ticker'].unique().tolist())
        
        # Agrupamos para obtener el costo y la cantidad actual
        resumen = df_abiertos.groupby(['Ticker', 'ID_Trade']).agg({
            'Posicion_Acum': 'last',
            'Inversion_USD': 'sum', # Este es el flujo neto (usualmente negativo si compraste)
            'fecha': 'min'
        }).reset_index()
        
        resumen['Precio_Actual_ARS'] = resumen['Ticker'].map(dict_precios)
        
        # --- LÓGICA DE CÁLCULO CORREGIDA ---
        # 1. Valuación actual
        resumen['Valuacion_USD'] = (resumen['Posicion_Acum'] * resumen['Precio_Actual_ARS']) / mep_hoy
        
        # 2. Inversión (Costo): La tratamos como positivo para la resta
        # Si Inversion_USD es -100 (compra), el costo es 100.
        resumen['Inversion_Costo_USD'] = resumen['Inversion_USD'].abs()
        
        # 3. Ganancia/Pérdida = Valuación - Inversión
        resumen['Ganancia_USD'] = resumen['Valuacion_USD'] - resumen['Inversion_Costo_USD']
        
        # 4. Rendimiento %
        resumen['Rend_%'] = (resumen['Ganancia_USD'] / resumen['Inversion_Costo_USD']) * 100
        
        # Reordenar y formatear columnas para que sea claro
        cols_mostrar = ['Ticker', 'Posicion_Acum', 'Inversion_Costo_USD', 'Valuacion_USD', 'Ganancia_USD', 'Rend_%']
        
        st.dataframe(resumen[cols_mostrar].style.format({
            'Posicion_Acum': '{:,.0f}', 
            'Inversion_Costo_USD': 'US$ {:,.2f}',
            'Valuacion_USD': 'US$ {:,.2f}', 
            'Ganancia_USD': 'US$ {:,.2f}', 
            'Rend_%': '{:.2f}%'
        }).background_gradient(subset=['Rend_%'], cmap='RdYlGn', vmin=-15, vmax=15), use_container_width=True)
    else:
        st.info("No hay trades abiertos.")

    # --- HISTORIAL ---
    st.subheader("🟢 Historial de Trades Cerrados")
    df_cerrados = df_arg[df_arg['Estado_Trade'] == 'Cerrado'].copy()
    if not df_cerrados.empty:
        resumen_c = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
            'fecha': ['min', 'max'],
            'Inversion_USD': 'sum'
        }).reset_index()
        resumen_c.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'P&L_Final_USD']
        
        # En cerrados, el flujo neto invertido es la ganancia (Venta + y Compra -)
        resumen_c['P&L_Final_USD'] = -resumen_c['P&L_Final_USD'] 
        
        st.dataframe(resumen_c.sort_values('Fecha_Out', ascending=False).style.format({
            'P&L_Final_USD': 'US$ {:,.2f}'
        }).background_gradient(subset=['P&L_Final_USD'], cmap='RdYlGn'), use_container_width=True)
