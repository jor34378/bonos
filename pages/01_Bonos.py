import streamlit as st
import pandas as pd
import glob
import os
import numpy as np

st.set_page_config(page_title="Dashboard de Inversiones", layout="wide")

@st.cache_data
def cargar_datos():
    archivos_csv = glob.glob("Movimientos_*.csv")
    if not archivos_csv: return None, None, None
        
    lista_dataframes = []
    for ruta in archivos_csv:
        nombre_base = os.path.basename(ruta)
        ticker = nombre_base.split('_')[1].split('.')[0]
        df_temp = pd.read_csv(ruta, sep=None, engine='python', encoding='latin-1', dtype=str)
        df_temp.columns = [str(col).strip().replace('ï»¿', '') for col in df_temp.columns]
        
        for col in ['Cantidad', 'Precio', 'Importe']:
            if col in df_temp.columns:
                df_temp[col] = df_temp[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce')
        
        df_temp.insert(0, 'Ticker', ticker)
        lista_dataframes.append(df_temp)

    df_mov = pd.concat(lista_dataframes, ignore_index=True)
    df_mov["Operado"] = pd.to_datetime(df_mov["Operado"], dayfirst=True, errors='coerce').dt.normalize()
    df_mov["Operación"] = df_mov["Operación"].replace({"CPRA": "Compra", "VTAS": "Venta"})
    return df_mov

def cargar_entorno():
    if os.path.exists("DOLAR MEP - Cotizaciones historicas.csv"):
        df_mep = pd.read_csv("DOLAR MEP - Cotizaciones historicas.csv")
        df_mep.columns = [str(c).strip().replace('ï»¿', '') for c in df_mep.columns]
        df_mep["fecha"] = pd.to_datetime(df_mep["fecha"], errors='coerce').dt.normalize()
        df_mep = df_mep[["fecha", "cierre"]].rename(columns={"cierre": "Cotiz_mep", "fecha": "Operado"})
        df_mep = df_mep.dropna(subset=['Operado']).sort_values('Operado') # MEP ordenado
    else:
        df_mep = pd.DataFrame({'Operado': [pd.Timestamp.now().normalize()], 'Cotiz_mep': [1300.0]})

    archivos_maestro = [f for f in glob.glob('listado_ticker_bonos*.csv') if not os.path.basename(f).startswith('~$')]
    if not archivos_maestro:
        df_maestro = pd.DataFrame(columns=['Ticker', 'Tipo'])
    else:
        ultimo_maestro = max(archivos_maestro, key=os.path.getctime)
        df_maestro = pd.read_csv(ultimo_maestro, sep=None, engine='python', encoding='latin1')
        df_maestro.columns = [str(c).strip().replace('ï»¿', '') for c in df_maestro.columns]
        mapeo = {c: "Tipo" for c in df_maestro.columns if "categ" in c.lower()}
        df_maestro = df_maestro.rename(columns=mapeo)
    
    return df_mep, df_maestro

def procesar_cartera(df_mov, df_mep, df_maestro, precios_manuales):
    MEP_HOY = df_mep['Cotiz_mep'].iloc[-1]
    df_solo_c_v = df_mov[df_mov["Operación"].isin(["Compra", "Venta"])].copy()
    
    df_solo_c_v = pd.merge(df_solo_c_v, df_maestro[['Ticker', 'Tipo']], on='Ticker', how='left')
    df_solo_c_v['Tipo'] = df_solo_c_v['Tipo'].fillna('Otros')
    
    # --- SOLUCIÓN AL ERROR: SORT OBLIGATORIO ANTES DE MERGE_ASOF ---
    df_solo_c_v = df_solo_c_v.sort_values('Operado') 
    df_mep = df_mep.sort_values('Operado')

    df_limpio = pd.merge_asof(
        df_solo_c_v, 
        df_mep[['Operado', 'Cotiz_mep']], 
        on='Operado', 
        direction='backward'
    )
    
    df_limpio['MEP_Final'] = df_limpio['Cotiz_mep'].fillna(MEP_HOY)
    df_limpio['Importe_ARS'] = (df_limpio['Precio'] * df_limpio['Cantidad']).abs() / 100
    df_limpio['Importe_USD'] = df_limpio['Importe_ARS'] / df_limpio['MEP_Final']

    resumen = []
    # Re-ordenamos por Ticker para que el bucle de acumulación sea coherente
    for (tipo, ticker), group in df_limpio.sort_values(['Ticker', 'Operado']).groupby(['Tipo', 'Ticker']):
        c_neta, c_nom, tot_usd_c, v_nom, tot_usd_v = 0.0, 0.0, 0.0, 0.0, 0.0
        
        for _, row in group.iterrows():
            if abs(c_neta) < 0.1: # Reseteo de ciclo si la posición es residual
                c_nom, tot_usd_c, v_nom, tot_usd_v, c_neta = 0.0, 0.0, 0.0, 0.0, 0.0
            
            cant = float(row['Cantidad'])
            if cant > 0: # Compra
                c_neta += cant; c_nom += cant; tot_usd_c += row['Importe_USD']
            else: # Venta
                c_neta += cant; v_nom += abs(cant); tot_usd_v += row['Importe_USD']

        c_neta_final = round(c_neta, 2)
        estado = "Abierto" if abs(c_neta_final) > 0.9 else "Cerrado"
        ppp_usd_compra = (tot_usd_c / c_nom * 100) if c_nom > 0 else 0
        
        if estado == "Abierto":
            p_exit_usd = precios_manuales.get(ticker, ppp_usd_compra)
        else:
            p_exit_usd = (tot_usd_v / v_nom * 100) if v_nom > 0 else 0

        resumen.append({
            'Ticker': ticker, 'Tipo': tipo, 'Cant_Final': c_neta_final,
            'PPP_USD': ppp_usd_compra, 'P_Exit_USD': p_exit_usd, 
            'Rinde_USD_%': ((p_exit_usd / ppp_usd_compra) - 1) * 100 if ppp_usd_compra > 0 else 0,
            'Estado': estado
        })
    return pd.DataFrame(resumen), MEP_HOY

# --- INTERFAZ (Sin cambios significativos) ---
try:
    df_mov = cargar_datos()
    df_mep, df_maestro = cargar_entorno()
    if df_mov is not None:
        st.sidebar.header("⚙️ Precios Salida (Abiertos)")
        tickers_unicos = sorted(df_mov['Ticker'].unique())
        df_p_init = pd.DataFrame({'Ticker': tickers_unicos, 'Precio_USD': 0.0})
        df_editado = st.sidebar.data_editor(df_p_init, column_config={"Precio_USD": st.column_config.NumberColumn(format="U$S %.2f")}, disabled=["Ticker"], hide_index=True)
        precios_manuales = df_editado[df_editado['Precio_USD'] > 0].set_index('Ticker')['Precio_USD'].to_dict()

        df_res, mep_val = procesar_cartera(df_mov, df_mep, df_maestro, precios_manuales)
        st.title("📈 Mi Portafolio de Inversiones")
        st.metric("Cotización MEP Hoy", f"${mep_val:,.2f}")
        estado_filtro = st.multiselect("Estado", ["Abierto", "Cerrado"], default=["Abierto"])
        df_f = df_res[df_res['Estado'].isin(estado_filtro)]

        for cat in df_f['Tipo'].unique():
            with st.expander(f"Estrategia: {str(cat).upper()}", expanded=True):
                st.dataframe(df_f[df_f['Tipo'] == cat].style.format({'Cant_Final': '{:,.0f}', 'PPP_USD': 'U$S {:,.2f}', 'P_Exit_USD': 'U$S {:,.2f}', 'Rinde_USD_%': '{:.2f}%'}).background_gradient(subset=['Rinde_USD_%'], cmap='RdYlGn', vmin=-10, vmax=10), use_container_width=True)
except Exception as e:
    st.error(f"Error: {e}")
