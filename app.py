import streamlit as st
import pandas as pd
import glob
import os
import numpy as np

st.set_page_config(page_title="Dashboard de Inversiones", layout="wide")

# ... (Mantené tu función cargar_datos() igual a la anterior) ...

# --- MOTOR DE CÁLCULO ---
def procesar_cartera(df_mov, df_mep, df_maestro, precios_manuales):
    MEP_HOY = df_mep['Cotiz_mep'].iloc[-1]
    df_solo_c_v = df_mov[df_mov["Operación"].isin(["Compra", "Venta"])].copy()
    
    # Merge con Maestro y limpieza
    df_solo_c_v = pd.merge(df_solo_c_v, df_maestro[['Ticker', 'Tipo']], on='Ticker', how='left')
    df_solo_c_v['Tipo'] = df_solo_c_v['Tipo'].fillna('Otros')
    df_solo_c_v = df_solo_c_v.sort_values('Operado')
    
    df_limpio = pd.merge_asof(df_solo_c_v, df_mep[['Operado', 'Cotiz_mep']], on='Operado', direction='backward')
    df_limpio['MEP_Final'] = df_limpio['Cotiz_mep'].fillna(MEP_HOY)
    df_limpio['Importe_ARS'] = (df_limpio['Precio'] * df_limpio['Cantidad']).abs() / 100
    df_limpio['Importe_USD'] = df_limpio['Importe_ARS'] / df_limpio['MEP_Final']

    resumen = []
    for (tipo, ticker), group in df_limpio.groupby(['Tipo', 'Ticker']):
        c_neta, c_nom, tot_ars_c, tot_usd_c = 0, 0, 0, 0
        
        for _, row in group.iterrows():
            if abs(c_neta) < 0.1: # Reset de ciclo si la posición se cerró
                c_nom, tot_ars_c, tot_usd_c = 0, 0, 0
            cant = row['Cantidad']
            if cant > 0:
                c_neta += cant; c_nom += cant
                tot_ars_c += row['Importe_ARS']; tot_usd_c += row['Importe_USD']
            else:
                c_neta += cant

        estado = "Abierto" if abs(c_neta) > 0.5 else "Cerrado"
        ppp_ars = (tot_ars_c / c_nom * 100) if c_nom > 0 else 0
        ppp_usd = (tot_usd_c / c_nom * 100) if c_nom > 0 else 0
        
        # --- LÓGICA DE PRECIO MANUAL ---
        # Buscamos si el usuario ingresó un precio en el editor, sino usamos el PPP
        p_exit_usd = precios_manuales.get(ticker, ppp_usd)

        resumen.append({
            'Ticker': ticker, 'Tipo': tipo, 'Cant_Final': round(c_neta, 0),
            'PPP_USD': ppp_usd, 'P_Exit_USD': p_exit_usd, 
            'Rinde_USD_%': ((p_exit_usd / ppp_usd) - 1) * 100 if ppp_usd > 0 else 0,
            'Estado': estado
        })
    return pd.DataFrame(resumen), MEP_HOY

# --- INTERFAZ STREAMLIT ---
try:
    df_mov, df_mep, df_maestro = cargar_datos()

    if df_mov is not None:
        # --- SECCIÓN DE PRECIOS MANUALES EN SIDEBAR ---
        st.sidebar.header("⚙️ Ajuste de Precios USD")
        st.sidebar.write("Editá la columna 'Precio_USD' para actualizar los bonos:")
        
        # Creamos un DF inicial con los tickers únicos abiertos
        tickers_unicos = df_mov['Ticker'].unique()
        df_precios_init = pd.DataFrame({'Ticker': tickers_unicos, 'Precio_USD': 0.0})
        
        # El Data Editor permite escribir sobre la tabla
        df_editado = st.sidebar.data_editor(
            df_precios_init, 
            column_config={"Precio_USD": st.column_config.NumberColumn(format="U$S %.2f")},
            disabled=["Ticker"], # Que no puedan cambiar el nombre del bono
            hide_index=True
        )
        
        # Convertimos el DF editado en un diccionario {Ticker: Precio}
        # Solo tomamos los que tienen precio mayor a 0
        precios_manuales = df_editado[df_editado['Precio_USD'] > 0].set_index('Ticker')['Precio_USD'].to_dict()

        # Procesamos con los precios que el usuario escribió
        df_res, mep_val = procesar_cartera(df_mov, df_mep, df_maestro, precios_manuales)

        st.title("📈 Mi Portafolio de Inversiones")
        st.metric("Cotización MEP Hoy", f"${mep_val:,.2f}")

        # ... (Resto de los filtros y visualización de tablas igual que antes) ...
        # [Asegurate de que las tablas muestren las columnas USD que calculamos]

except Exception as e:
    st.error(f"Error: {e}")
