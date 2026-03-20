import streamlit as st
import pandas as pd
import glob
import os
import numpy as np

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard de Inversiones", layout="wide")

# --- FUNCIONES DE CARGA (Con Cache para Performance) ---
@st.cache_data
def cargar_datos():
    # 1. Carga de Movimientos
    archivos_csv = glob.glob("Movimientos_*.csv")
    lista_dataframes = []
    for ruta in archivos_csv:
        nombre_base = os.path.basename(ruta)
        ticker = nombre_base.split('_')[1].split('.')[0]
        df_temp = pd.read_csv(ruta, sep=None, engine='python', encoding='latin-1', dtype=str)
        df_temp.columns = [str(col).strip() for col in df_temp.columns]
        for col in ['Cantidad', 'Precio', 'Importe']:
            if col in df_temp.columns:
                df_temp[col] = df_temp[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce')
        df_temp.insert(0, 'Ticker', ticker)
        lista_dataframes.append(df_temp)

    df_mov = pd.concat(lista_dataframes, ignore_index=True)
    # Normalizamos fechas para evitar errores de cruce
    df_mov["Operado"] = pd.to_datetime(df_mov["Operado"], dayfirst=True, errors='coerce').dt.normalize()
    df_mov["Operación"] = df_mov["Operación"].replace({"CPRA": "Compra", "VTAS": "Venta"})

    # 2. Carga de MEP
    df_mep = pd.read_csv("DOLAR MEP - Cotizaciones historicas.csv")
    df_mep["fecha"] = pd.to_datetime(df_mep["fecha"], errors='coerce').dt.normalize()
    df_mep = df_mep[["fecha", "cierre"]].rename(columns={"cierre": "Cotiz_mep", "fecha": "Operado"})
    df_mep = df_mep.dropna(subset=['Operado']).sort_values('Operado')

    # 3. Carga de Maestro
    archivos_maestro = glob.glob('listado_ticker_bonos*.csv')
    ultimo_maestro = max(archivos_maestro, key=os.path.getctime)
    df_maestro = pd.read_csv(ultimo_maestro, sep=None, engine='python', encoding='latin1')
    df_maestro.columns = [c.strip() for c in df_maestro.columns]
    df_maestro = df_maestro.rename(columns={"Categoría": "Tipo"})

    return df_mov, df_mep, df_maestro

# --- MOTOR DE CÁLCULO ---
def procesar_cartera(df_mov, df_mep, df_maestro, precios_ref):
    MEP_HOY = df_mep['Cotiz_mep'].iloc[-1]

    df_solo_c_v = df_mov[df_mov["Operación"].isin(["Compra", "Venta"])].copy()
    df_solo_c_v = pd.merge(df_solo_c_v, df_maestro[['Ticker', 'Tipo']], on='Ticker', how='left')
    
    # IMPORTANTE: Ambos deben estar ordenados para merge_asof
    df_solo_c_v = df_solo_c_v.sort_values('Operado')
    df_mep = df_mep.sort_values('Operado')

    df_limpio = pd.merge_asof(
        df_solo_c_v, 
        df_mep[['Operado', 'Cotiz_mep']],
        on='Operado', 
        direction='backward', 
        suffixes=('', '_hist')
    )

    # Creamos la columna Cotiz_mep_hist si por algún motivo merge_asof no la creó
    if 'Cotiz_mep_hist' not in df_limpio.columns:
        df_limpio['Cotiz_mep_hist'] = np.nan

    df_limpio['MEP_Final'] = df_limpio['Cotiz_mep'].fillna(df_limpio['Cotiz_mep_hist']).fillna(MEP_HOY)
    df_limpio['Importe_ARS'] = (df_limpio['Precio'] * df_limpio['Cantidad']).abs() / 100
    df_limpio['Importe_USD'] = df_limpio['Importe_ARS'] / df_limpio['MEP_Final']

    resumen = []
    for (tipo, ticker), group in df_limpio.groupby(['Tipo', 'Ticker']):
        c_neta, c_nom, tot_ars_c, tot_usd_c = 0, 0, 0, 0
        v_nom, tot_ars_v, tot_usd_v = 0, 0, 0

        for _, row in group.iterrows():
            if abs(c_neta) < 0.1:
                c_nom, tot_ars_c, tot_usd_c = 0, 0, 0
                v_nom, tot_ars_v, tot_usd_v = 0, 0, 0

            cant = row['Cantidad']
            if cant > 0:
                c_neta += cant; c_nom += cant
                tot_ars_c += row['Importe_ARS']; tot_usd_c += row['Importe_USD']
            else:
                c_neta += cant; v_nom += abs(cant)
                tot_ars_v += row['Importe_ARS']; tot_usd_v += row['Importe_USD']

        estado = "Abierto" if abs(c_neta) > 0.5 else "Cerrado"
        ppp_ars = (tot_ars_c / c_nom * 100) if c_nom > 0 else 0
        ppp_usd = (tot_usd_c / c_nom * 100) if c_nom > 0 else 0
        
        if estado == "Abierto":
            p_exit_ars = precios_ref.get(ticker, ppp_ars)
            p_exit_usd = p_exit_ars / MEP_HOY
        else:
            p_exit_ars = (tot_ars_v / v_nom * 100) if v_nom > 0 else 0
            p_exit_usd = (tot_usd_v / v_nom * 100) if v_nom > 0 else 0

        resumen.append({
            'Ticker': ticker, 'Tipo': tipo, 'Cant_Final': round(c_neta, 0),
            'PPP_ARS': ppp_ars, 'P_Exit_ARS': p_exit_ars, 'Rinde_ARS_%': ((p_exit_ars / ppp_ars) - 1) * 100 if ppp_ars > 0 else 0,
            'PPP_USD': ppp_usd, 'P_Exit_USD': p_exit_usd, 'Rinde_USD_%': ((p_exit_usd / ppp_usd) - 1) * 100 if ppp_usd > 0 else 0,
            'Estado': estado
        })
    return pd.DataFrame(resumen), MEP_HOY

# --- INTERFAZ STREAMLIT ---
st.title("📈 Mi Portafolio de Inversiones")

try:
    df_mov, df_mep, df_maestro = cargar_datos()

    precios_broker = {
        'BB37D': 101880.0, 'CUAP': 38440.0, 'DICP': 47270.0, 'GD38': 113420.0,
        'GD41': 99230.0, 'PARP': 32190.0, 'TX28': 1866.0, 'TZX26': 364.20,
        'TZX28': 304.30, 'TZXM6': 213.778, 'AE38': 109660.0, 'AL30': 65000.0
    }

    df_res, mep_val = procesar_cartera(df_mov, df_mep, df_maestro, precios_broker)

    st.metric("Cotización MEP Hoy", f"${mep_val:,.2f}")

    estado_filtro = st.multiselect("Filtrar por Estado", ["Abierto", "Cerrado"], default=["Abierto"])
    df_filtrado = df_res[df_res['Estado'].isin(estado_filtro)]

    for cat in df_filtrado['Tipo'].unique():
        if pd.isna(cat): continue
        with st.expander(f"Estrategia: {cat.upper()}", expanded=True):
            df_cat = df_filtrado[df_filtrado['Tipo'] == cat]
            st.dataframe(df_cat.style.format({
                'Cant_Final': '{:,.0f}', 'PPP_ARS': '${:,.2f}', 'P_Exit_ARS': '${:,.2f}',
                'Rinde_ARS_%': '{:.2f}%', 'PPP_USD': 'U$S {:,.2f}', 'P_Exit_USD': 'U$S {:,.2f}',
                'Rinde_USD_%': '{:.2f}%'
            }).background_gradient(subset=['Rinde_USD_%'], cmap='RdYlGn', vmin=-10, vmax=10), use_container_width=True)

except Exception as e:
    st.error(f"Error al cargar la aplicación: {e}")
