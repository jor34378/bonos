import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Acciones Argentinas", layout="wide")

@st.cache_data
def procesar_datos_desde_cero():
    # 1. Cargar el archivo original (el que bajás de la plataforma)
    # Ajustá el nombre si en GitHub se llama distinto
    archivo_base = 'df_veta_consolidado.csv' 
    
    if not os.path.exists(archivo_base):
        st.error(f"⚠️ No se encuentra el archivo {archivo_base} en GitHub.")
        return None

    df = pd.read_csv(archivo_base, encoding='latin1', sep=None, engine='python')
    
    # 2. Lógica de Tickers y Categorías (Tu "Diccionario" de la notebook)
    data_tickers = [
        ['BONOS REP. ARG. U$S STEP UP V.09/07/41', 'AL41', 'Soberano'],
        ['ALUAR ALUMINIO ARG.ORD 1 V', 'ALUA', 'Acción Arg'],
        ['MIRGOR', 'MIRG', 'Acción Arg'],
        ['BOLSAS Y MERCADOS ARG. $ ORD. (BYMA)', 'BYMA', 'Acción Arg'],
        ['MOLINOS R.L.P. "B"', 'MOLI', 'Acción Arg'],
        ['TERNIUM ARG S.A.ORDS. A 1 VOTO ESC', 'TXAR', 'Acción Arg'],
        ['SOCIEDAD COMERCIAL DEL PLATA ORD.1V', 'COME', 'Acción Arg'],
        ['HAVANNA HOLDING ACC.ORD', 'HAVA', 'Acción Arg'],
        ['TRANSENER S.A. ESCRIT. B 1 VOTO', 'TRAN', 'Acción Arg'],
        ['ACC.ORD. LOMA NEGRA S.A. 1 VOTO $ ESC.', 'LOMA', 'Acción Arg'],
        ['Y.P.F. S.A.', 'YPFD', 'Acción Arg'],
        ['BCO HIPOTECARIO ESCRIT. D (CAT 1 Y 2)', 'BHIP', 'Acción Arg'],
        ['AGROMETAL "B" ORDS 1V', 'AGRO', 'Acción Arg'],
        ['INVERSORA JURAMENTO SA', 'INJU', 'Acción Arg'],
        ['FERRUM S.A. "B"', 'FERR', 'Acción Arg'],
        ['SAN MIGUEL S.A. ESCRIT. CLASE B 1', 'SAMI', 'Acción Arg'],
        ['LONGVIE "B"', 'LONG', 'Acción Arg'],
        ['CONSULTATIO SA ORD 1 VOTO', 'CTIO', 'Acción Arg'],
        ['CELULOSA "B"', 'CELU', 'Acción Arg'],
        ['BCO PATAGONIA ACC CL B', 'BPAT', 'Acción Arg'],
        ['CAMUZZI GAS DEL SUR', 'CGAS', 'Acción Arg'],
        ['TRANSPORTADORA DE GAS DEL NORTE', 'TGNO4', 'Acción Arg'],
        ['BANCO BBVA ARG ESC S 1 V.', 'BBAR', 'Acción Arg'],
        ['BANCO MACRO S.A. B 1 V. ESCRIT', 'BMA', 'Acción Arg'],
        ['METRO GAS', 'METR', 'Acción Arg'],
        ['EDENOR S.A. B 1 VOTO', 'EDN', 'Acción Arg'],
        ['IRSA ESCRIT. ORD. 1 V', 'IRSA', 'Acción Arg'],
        ['CTRAL COSTANERA "B"', 'CECO2', 'Acción Arg'],
        ['MOLINOS AGRO S.A.', 'MOLA', 'Acción Arg'],
        ['TRANS. DE GAS DEL SUR', 'TGSU2', 'Acción Arg'],
        ['IMP. Y E. PATAGONIA', 'PATA', 'Acción Arg']
    ]
    listado_tickers = pd.DataFrame(data_tickers, columns=['Especie', 'Ticker', 'Categoría'])
    
    # 3. Merge y Limpieza (Igual que en tu notebook)
    df_completo = df.merge(listado_tickers[["Especie","Ticker","Categoría"]], on="Especie", how="left")
    df_completo["Ticker"] = df_completo["Ticker_x"].fillna(df_completo["Ticker_y"])
    df_completo["tipo_2"] = df_completo["Categoría"].fillna(df_completo["tipo"])
    df_completo = df_completo.rename(columns={"OperaciÃ³n":"Operacion", "ï»¿Operado":"Operado"})
    
    # Filtrar solo acciones y limpiar nombres de operación
    df_arg = df_completo[df_completo["tipo_2"] == "Acción Arg"].copy()
    df_arg["Operacion"] = df_arg["Operacion"].replace({"CPRA":"Compra", "VTAS":"Venta"})
    df_arg['Operado'] = pd.to_datetime(df_arg['Operado'])

    # 4. Aplicación de SPLITS
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

    # 5. Lógica de Trades y limpieza de residuos (< 1 nominal)
    df_arg = df_arg.sort_values(['Ticker', 'Operado'])
    df_arg['Posicion_Acum'] = df_arg.groupby('Ticker')['Cantidad'].cumsum().round(2)
    df_arg.loc[df_arg['Posicion_Acum'].abs() < 1.0, 'Posicion_Acum'] = 0.0
    
    df_arg['Es_Cierre'] = (df_arg['Posicion_Acum'] == 0)
    df_arg['ID_Trade'] = (df_arg.groupby('Ticker')['Es_Cierre'].shift(fill_value=False)
                          .groupby(df_arg['Ticker']).cumsum() + 1)
    
    status = df_arg.groupby(['Ticker', 'ID_Trade'])['Posicion_Acum'].last().apply(
        lambda x: 'Abierto' if abs(x) >= 1.0 else 'Cerrado'
    ).reset_index(name='Estado_Trade')
    
    return df_arg.merge(status, on=['Ticker', 'ID_Trade'])

def obtener_precios(tickers):
    tickers_yf = [f"{t}.BA" for t in tickers]
    try:
        data = yf.download(tickers_yf, period="1d", progress=False)['Close']
        if len(tickers) > 1:
            return {t.replace(".BA", ""): data[t].iloc[-1] for t in tickers_yf}
        return {tickers[0]: data.iloc[-1]}
    except:
        return {}

# --- LÓGICA DE VISUALIZACIÓN ---
st.title("🇦🇷 Cartera de Acciones Argentinas")

df_final = procesar_datos_desde_cero()

if df_final is not None:
    mep_hoy = 1433.21  # MEP de referencia actualizado
    
    # --- ABIERTOS ---
    st.subheader("🔵 Posiciones Actuales")
    df_abiertos = df_final[df_final['Estado_Trade'] == 'Abierto'].copy()
    if not df_abiertos.empty:
        precios = obtener_precios(df_abiertos['Ticker'].unique())
        resumen = df_abiertos.groupby(['Ticker', 'ID_Trade']).agg({
            'Posicion_Acum': 'last',
            'Inversion_usd': 'sum'
        }).reset_index()
        
        resumen['Precio_Hoy_ARS'] = resumen['Ticker'].map(precios)
        resumen['Valuacion_USD'] = (resumen['Posicion_Acum'] * resumen['Precio_Hoy_ARS']) / mep_hoy
        resumen['Rend_%'] = ((resumen['Valuacion_USD'] / resumen['Inversion_usd'].abs()) - 1) * 100
        
        st.dataframe(resumen.style.format({
            'Posicion_Acum': '{:,.0f}', 'Inversion_usd': 'US$ {:,.2f}',
            'Precio_Hoy_ARS': '$ {:,.2f}', 'Valuacion_USD': 'US$ {:,.2f}', 'Rend_%': '{:.2f}%'
        }).background_gradient(subset=['Rend_%'], cmap='RdYlGn'), use_container_width=True)
    else:
        st.info("No hay posiciones abiertas actualmente.")

    # --- CERRADOS ---
    st.subheader("🟢 Historial de Ganancias/Pérdidas")
    df_cerrados = df_final[df_final['Estado_Trade'] == 'Cerrado'].copy()
    if not df_cerrados.empty:
        resumen_c = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg({
            'Operado': ['min', 'max'],
            'Inversion_usd': 'sum'
        }).reset_index()
        resumen_c.columns = ['Ticker', 'ID_Trade', 'Fecha_In', 'Fecha_Out', 'Resultado_USD']
        resumen_c['Resultado_USD'] = -resumen_c['Resultado_USD']
        
        st.dataframe(resumen_c.sort_values('Fecha_Out', ascending=False).style.format({
            'Resultado_USD': 'US$ {:,.2f}'
        }).background_gradient(subset=['Resultado_USD'], cmap='RdYlGn'), use_container_width=True)
