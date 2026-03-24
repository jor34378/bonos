import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Acciones Argentinas", layout="wide")

@st.cache_data
def cargar_datos_argentina():
    archivo = 'reporte_trades_para_ARG.csv'
    
    if not os.path.exists(archivo):
        st.error(f"⚠️ No se encuentra el archivo '{archivo}'.")
        st.info("Asegurate de haber guardado el CSV con ese nombre en la misma carpeta que este script.")
        return None

    # Carga con detección de separador y encoding seguro para Argentina
    df = pd.read_csv(archivo, sep=None, engine='python', encoding='utf-8-sig')
    
    # Limpieza de nombres de columnas (minúsculas y sin espacios)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # Mapeo para estandarizar (Ajusta estos nombres según tu CSV real)
    mapeo = {
        'ticker': 'Ticker',
        'operado': 'fecha',
        'cantidad': 'Cantidad',
        'precio': 'Precio',
        'precio_usd': 'Precio_USD',
        'inversion_usd': 'Inversion_USD',
        'operacion': 'Operacion'
    }
    df = df.rename(columns={k: v for k, v in mapeo.items() if k in df.columns})
    
    # Conversión de fechas
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    
    # --- LÓGICA DE TRADES (Agrupación por Ciclos de Posición) ---
    df = df.sort_values(['Ticker', 'fecha'])
    
    # Calculamos la posición acumulada para saber qué está abierto y qué cerrado
    # Nota: Las ventas deben ser negativas en la columna Cantidad para que esto funcione
    df['Posicion_Acum'] = df.groupby('Ticker')['Cantidad'].cumsum().round(4)
    
    # Identificar cierres (cuando la posición vuelve a cero)
    df['Es_Cierre'] = (df['Posicion_Acum'].abs() < 0.0001)
    
    # Generar ID de Trade único por ciclo
    df['ID_Trade'] = (df.groupby('Ticker')['Es_Cierre'].shift(fill_value=False)
                      .groupby(df['Ticker']).cumsum() + 1)
    
    # Determinar estado final de cada ID_Trade
    status = df.groupby(['Ticker', 'ID_Trade'])['Posicion_Acum'].last().apply(
        lambda x: 'Abierto' if abs(x) >= 0.0001 else 'Cerrado'
    ).reset_index(name='Estado_Trade')
    
    return df.merge(status, on=['Ticker', 'ID_Trade'])

def obtener_precios_merval(tickers):
    # Agregamos .BA para Yahoo Finance
    tickers_yf = [f"{t}.BA" for t in tickers]
    try:
        # Descargamos solo el último precio
        data = yf.download(tickers_yf, period="1d", interval="1m", progress=False)['Close']
        precios = {}
        for t in tickers:
            t_ba = f"{t}.BA"
            if t_ba in data.columns:
                # Tomamos el último valor no nulo
                val = data[t_ba].dropna()
                if not val.empty:
                    precios[t] = val.iloc[-1]
        return precios
    except Exception as e:
        st.warning(f"Error al conectar con Yahoo Finance: {e}")
        return {}

# --- INTERFAZ STREAMLIT ---
st.title("🇦🇷 Cartera de Acciones Argentinas")
st.markdown("---")

df_arg = cargar_datos_argentina()

if df_arg is not None:
    # Cotización MEP de referencia (Podrías automatizarlo también)
    mep_referencia = st.sidebar.number_input("Cotización MEP Referencia", value=1433.21)

    # --- SECCIÓN 1: POSICIONES ABIERTAS ---
    st.subheader("🔵 Posiciones Actuales (En Cartera)")
    df_abiertos = df_arg[df_arg['Estado_Trade'] == 'Abierto'].copy()
    
    if not df_abiertos.empty:
        # Obtenemos precios en tiempo real
        listado_tickers = df_abiertos['Ticker'].unique()
        dict_precios = obtener_precios_merval(listado_tickers)
        
        # Agrupamos por Trade
        resumen_abierto = df_abiertos.groupby(['Ticker', 'ID_Trade']).agg({
            'Posicion_Acum': 'last',
            'Inversion_USD': 'sum',
            'fecha': 'min'
        }).reset_index()
        
        resumen_abierto = resumen_abierto.rename(columns={'fecha': 'Fecha_Inicio'})
        resumen_abierto['Precio_Actual_ARS'] = resumen_abierto['Ticker'].map(dict_precios)
        
        # Valuación y Rendimiento
        resumen_abierto['Valuacion_USD'] = (resumen_abierto['Posicion_Acum'] * resumen_abierto['Precio_Actual_ARS']) / mep_referencia
        resumen_abierto['Ganancia_USD'] = resumen_abierto['Valuacion_USD'] + resumen_abierto['Inversion_USD'] # Inversion_USD es negativa si es compra
        resumen_abierto['Rend_%'] = (resumen_abierto['Ganancia_USD'] / resumen_abierto['Inversion_USD'].abs()) * 100
        
        # Mostrar Tabla
        st.dataframe(resumen_abierto.style.format({
            'Posicion_Acum': '{:,.2f}',
            'Inversion_USD': 'US$ {:,.2f}',
            'Precio_Actual_ARS': '$ {:,.2f}',
            'Valuacion_USD': 'US$ {:,.2f}',
            'Ganancia_USD': 'US$ {:,.2f}',
            'Rend_%': '{:.2f}%'
        }).background_gradient(subset=['Rend_%'], cmap='RdYlGn'), use_container_width=True)
    else:
        st.info("No se detectaron posiciones abiertas.")

    # --- SECCIÓN 2: HISTORIAL (CERRADOS) ---
    st.write("---")
    st.subheader("🟢 Historial de Trades Cerrados")
    df_historial = df_arg[df_arg['Estado_Trade'] == 'Cerrado'].copy()
    
    if not df_historial.empty:
        resumen_cerrado = df_historial.groupby(['Ticker', 'ID_Trade']).agg({
            'fecha': ['min', 'max'],
            'Inversion_USD': 'sum'
        }).reset_index()
        
        # Aplanamos columnas del groupby
        resumen_cerrado.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Resultado_Final_USD']
        
        # En contabilidad de flujo, la suma de Inversion_USD en un trade cerrado es la ganancia neta
        # (Venta (+) y Compra (-) = Resultado)
        resumen_cerrado['Resultado_Final_USD'] = -resumen_cerrado['Resultado_Final_USD'] 
        
        st.dataframe(resumen_cerrado.sort_values('Fecha_Out', ascending=False).style.format({
            'Resultado_Final_USD': 'US$ {:,.2f}'
        }).background_gradient(subset=['Resultado_Final_USD'], cmap='RdYlGn'), use_container_width=True)
        
        # Métricas Rápidas
        c1, c2 = st.columns(2)
        c1.metric("Ganancia Histórica Total", f"US$ {resumen_cerrado['Resultado_Final_USD'].sum():,.2f}")
        c2.metric("Mejor Trade", f"US$ {resumen_cerrado['Resultado_Final_USD'].max():,.2f}")
    else:
        st.info("Aún no tienes trades cerrados registrados.")
