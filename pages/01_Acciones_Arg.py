import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard Acciones AR", layout="wide")

@st.cache_data
def cargar_y_limpiar_datos():
    # 1. Carga de datos base (df_completo.csv generado previamente)
    df = pd.read_csv('df_completo.csv', sep=';', encoding='utf-8-sig')
    df['Operado'] = pd.to_datetime(df['Operado'])
    
    # Filtramos solo Acciones Arg y normalizamos operaciones
    df_arg = df[df["tipo_2"] == "Acción Arg"].copy()
    df_arg["Operacion"] = df_arg["Operacion"].replace({"VTAS": "Venta", "CPRA": "Compra"})
    
    # 2. Aplicación de Splits
    splits = [
        {'Ticker': 'BYMA', 'Fecha': '2024-05-10', 'Ratio': 5/1},
        {'Ticker': 'BYMA', 'Fecha': '2025-05-26', 'Ratio': 2/1},
        {'Ticker': 'FERR', 'Fecha': '2024-11-28', 'Ratio': 39/8},
        {'Ticker': 'IRSA', 'Fecha': '2024-11-01', 'Ratio': 259/250},
    ]
    for s in splits:
        mask = (df_arg['Ticker'] == s['Ticker']) & (df_arg['Operado'] < pd.to_datetime(s['Fecha']))
        df_arg.loc[mask, 'Cantidad'] *= s['Ratio']
        df_arg.loc[mask, 'Precio'] /= s['Ratio']
        df_arg.loc[mask, 'Precio_usd'] /= s['Ratio']

    # 3. Lógica de Ciclos (ID_Trade) y limpieza de residuos
    df_arg = df_arg.sort_values(['Ticker', 'Operado'])
    df_arg['Posicion_Acum'] = df_arg.groupby('Ticker')['Cantidad'].cumsum().round(2)
    
    # Limpieza de FERR/IRSA y otros residuales < 1 acción
    df_arg.loc[df_arg['Posicion_Acum'].abs() < 1.0, 'Posicion_Acum'] = 0.0
    
    df_arg['Es_Cierre'] = (df_arg['Posicion_Acum'] == 0)
    df_arg['ID_Trade'] = (df_arg.groupby('Ticker')['Es_Cierre'].shift(fill_value=False)
                          .groupby(df_arg['Ticker']).cumsum() + 1)
    
    # Estado del trade
    status = df_arg.groupby(['Ticker', 'ID_Trade'])['Posicion_Acum'].last().apply(
        lambda x: 'Abierto' if abs(x) >= 1.0 else 'Cerrado'
    ).reset_index(name='Estado_Trade')
    
    return df_arg.merge(status, on=['Ticker', 'ID_Trade'])

def obtener_precios_actuales(tickers):
    tickers_yf = [f"{t}.BA" for t in tickers]
    data = yf.download(tickers_yf, period="1d", progress=False)['Close']
    if len(tickers) > 1:
        return {t.replace(".BA", ""): data[t].iloc[-1] for t in tickers_yf}
    return {tickers[0]: data.iloc[-1]}

# --- EJECUCIÓN DEL PIPELINE ---
st.title("🇦🇷 Monitor de Acciones Argentinas")

try:
    df_final = cargar_y_limpiar_datos()
    mep_hoy = 1433.21  # Podrías automatizar esto también
    
    # --- SECCIÓN 1: POSICIONES ABIERTAS (CARTERA ACTUAL) ---
    st.header("🔵 Posiciones Abiertas (Cartera)")
    
    df_abiertos = df_final[df_final['Estado_Trade'] == 'Abierto'].copy()
    tickers_abiertos = df_abiertos['Ticker'].unique()
    precios_hoy = obtener_precios_actuales(tickers_abiertos)
    
    resumen_abiertos = df_abiertos.groupby(['Ticker', 'ID_Trade']).agg({
        'Operado': 'min',
        'Posicion_Acum': 'last',
        'Inversion_usd': 'sum'  # Suma de flujos (Costo)
    }).reset_index()
    
    resumen_abiertos['Precio_Hoy_ARS'] = resumen_abiertos['Ticker'].map(precios_hoy)
    resumen_abiertos['Valuacion_USD'] = (resumen_abiertos['Posicion_Acum'] * resumen_abiertos['Precio_Hoy_ARS']) / mep_hoy
    resumen_abiertos['Ganancia_USD'] = resumen_abiertos['Valuacion_USD'] - resumen_abiertos['Inversion_usd'].abs()
    resumen_abiertos['Rend_%'] = (resumen_abiertos['Ganancia_USD'] / resumen_abiertos['Inversion_usd'].abs()) * 100
    
    # Mostrar métricas clave
    c1, c2, c3 = st.columns(3)
    c1.metric("Capital Invertido", f"US$ {resumen_abiertos['Inversion_usd'].abs().sum():,.2f}")
    c2.metric("Ganancia Latente", f"US$ {resumen_abiertos['Ganancia_USD'].sum():,.2f}")
    c3.metric("Rendimiento Cartera", f"{ (resumen_abiertos['Ganancia_USD'].sum() / resumen_abiertos['Inversion_usd'].abs().sum() * 100):.2f}%")

    st.dataframe(resumen_abiertos.style.format({
        'Posicion_Acum': '{:,.0f}', 'Inversion_usd': '${:,.2f}', 
        'Precio_Hoy_ARS': '${:,.2f}', 'Valuacion_USD': '${:,.2f}',
        'Ganancia_USD': '${:,.2f}', 'Rend_%': '{:.2f}%'
    }).background_gradient(subset=['Rend_%'], cmap='RdYlGn'), use_container_width=True)

    # --- SECCIÓN 2: TRADES CERRADOS (HISTORIAL) ---
    st.header("🟢 Historial de Trades Cerrados")
    
    df_cerrados = df_final[df_final['Estado_Trade'] == 'Cerrado'].copy()
    resumen_cerrados = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
        'Operado': ['min', 'max'],
        'Inversion_usd': 'sum',
        'Cantidad': lambda x: x[x > 0].sum()
    }).reset_index()
    
    resumen_cerrados.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Resultado_USD', 'Cant_Total']
    resumen_cerrados['Resultado_USD'] = -resumen_cerrados['Resultado_USD'] # Invertimos signo para ganancia
    
    st.dataframe(resumen_cerrados.sort_values('Fecha_Out', ascending=False).style.format({
        'Resultado_USD': 'US$ {:,.2f}', 'Cant_Total': '{:,.0f}'
    }).background_gradient(subset=['Resultado_USD'], cmap='RdYlGn'), use_container_width=True)

except Exception as e:
    st.error(f"Error al procesar: {e}")
