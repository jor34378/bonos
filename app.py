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
    # FORZAMOS DATETIME Y NORMALIZAMOS (Quitamos horas/minutos)
    df_mov["Operado"] = pd.to_datetime(df_mov["Operado"], dayfirst=True, errors='coerce').dt.normalize()
    df_mov["Operación"] = df_mov["Operación"].replace({"CPRA": "Compra", "VTAS": "Venta"})

    # 2. Carga de MEP
    df_mep = pd.read_csv("DOLAR MEP - Cotizaciones historicas.csv")
    # FORZAMOS DATETIME Y NORMALIZAMOS
    df_mep["fecha"] = pd.to_datetime(df_mep["fecha"], errors='coerce').dt.normalize()
    df_mep = df_mep[["fecha", "cierre"]].rename(columns={"cierre": "Cotiz_mep", "fecha": "Operado"})
    
    # Eliminamos filas sin fecha por si el CSV tiene basura al final
    df_mep = df_mep.dropna(subset=['Operado']).sort_values('Operado')
    
    # 3. Carga de Maestro
    archivos_maestro = glob.glob('listado_ticker_bonos*.csv')
    ultimo_maestro = max(archivos_maestro, key=os.path.getctime)
    df_maestro = pd.read_csv(ultimo_maestro, sep=None, engine='python', encoding='latin1')
    df_maestro.columns = [c.strip() for c in df_maestro.columns]
    df_maestro = df_maestro.rename(columns={"Categoría": "Tipo"})

    return df_mov, df_mep, df_maestro
