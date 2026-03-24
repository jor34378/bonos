@st.cache_data
def load_data():
    try:
        # 1. Intentamos leer el CSV (agregamos sep=None para que detecte si es , o ;)
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=None, engine='python')
        
        # 2. LIMPIEZA DE COLUMNAS: Quitamos espacios en blanco de los nombres de las columnas
        # y las pasamos a Capitalize para asegurar match (Ticker, Fecha, etc.)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 3. Verificamos si existe la columna (case-insensitive)
        # Buscamos 'Ticker' ignorando si es 'ticker' o 'TICKER'
        col_dict = {c.lower(): c for c in df.columns}
        if 'ticker' in col_dict:
            nombre_real = col_dict['ticker']
            df['Ticker'] = df[nombre_real].astype(str).str.strip()
            # Si el nombre era distinto, lo normalizamos a 'Ticker'
            if nombre_real != 'Ticker':
                df = df.rename(columns={nombre_real: 'Ticker'})
        else:
            st.error(f"❌ No se encontró la columna 'Ticker'. Columnas detectadas: {list(df.columns)}")
            return None

        # Filtramos filas basura
        df = df[df['Ticker'].get_loc != 'nan']
        return df

    except Exception as e:
        st.error(f"❌ Error al cargar el archivo: {e}")
        return None
