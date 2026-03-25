@st.cache_data
def cargar_datos():
    archivos_csv = glob.glob("Movimientos_*.csv")
    if not archivos_csv: return None, None, None
        
    lista_dataframes = []
    for ruta in archivos_csv:
        nombre_base = os.path.basename(ruta)
        # Limpieza del Ticker desde el nombre del archivo
        ticker = nombre_base.split('_')[1].split('.')[0].strip().upper()
        
        df_temp = pd.read_csv(ruta, sep=None, engine='python', encoding='latin-1', dtype=str)
        df_temp.columns = [str(col).strip().replace('ï»¿', '') for col in df_temp.columns]
        
        for col in ['Cantidad', 'Precio', 'Importe']:
            if col in df_temp.columns:
                df_temp[col] = df_temp[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce')
        
        df_temp.insert(0, 'Ticker', ticker)
        lista_dataframes.append(df_temp)

    df_mov = pd.concat(lista_dataframes, ignore_index=True)
    
    # --- LIMPIEZA ANTI-DUPLICADOS ---
    df_mov["Ticker"] = df_mov["Ticker"].str.strip().upper()
    df_mov["Operado"] = pd.to_datetime(df_mov["Operado"], dayfirst=True, errors='coerce').dt.normalize()
    df_mov["Operación"] = df_mov["Operación"].replace({"CPRA": "Compra", "VTAS": "Venta"})
    
    # Consolidamos filas que sean idénticas en fecha, ticker y operación (por si el CSV bajó doble)
    df_mov = df_mov.groupby(['Ticker', 'Operado', 'Operación', 'Precio'], as_index=False).agg({
        'Cantidad': 'sum',
        'Importe': 'sum'
    })
    
    return df_mov

def procesar_cartera(df_mov, df_mep, df_maestro, precios_manuales):
    MEP_HOY = df_mep['Cotiz_mep'].iloc[-1]
    
    # Filtramos solo C/V y eliminamos filas con cantidad 0
    df_solo_c_v = df_mov[df_mov["Operación"].isin(["Compra", "Venta"])].copy()
    df_solo_c_v = df_solo_c_v[df_solo_c_v["Cantidad"] > 0] 

    # Aseguramos que el Maestro también esté limpio
    df_maestro['Ticker'] = df_maestro['Ticker'].str.strip().upper()
    
    df_solo_c_v = pd.merge(df_solo_c_v, df_maestro[['Ticker', 'Tipo']], on='Ticker', how='left')
    df_solo_c_v['Tipo'] = df_solo_c_v['Tipo'].fillna('Otros')
    
    # Ordenamiento crítico
    df_solo_c_v = df_solo_c_v.sort_values('Operado')
    df_mep = df_mep.sort_values('Operado')

    # ... (el resto del merge_asof y el bucle for sigue igual)
