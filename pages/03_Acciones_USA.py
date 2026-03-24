# --- PROCESAMIENTO BLINDADO ---
        # Filtramos solo cerrados y nos aseguramos de que tengan fecha
        df_cerrados = df_trades[(df_trades['Estado_Trade'] == 'Cerrado') & (df_trades['fecha'].notnull())].copy()

        # Usamos AGREGACIÓN NOMBRADA para evitar el KeyError
        # Esto crea columnas nuevas (Fecha_In, Fecha_Out) directamente desde 'fecha'
        resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
            Fecha_In=('fecha', 'min'),
            Fecha_Out=('fecha', 'max'),
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()

        # Una vez reseteado el índice, verificamos que no haya nulos en las nuevas columnas
        resumen_stats = resumen_stats.dropna(subset=['Fecha_In'])

        # Cálculos de resultados
        resumen_stats['Resultado_USD'] = resumen_stats['Neto_Flujo']
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        
        # Rendimiento %
        resumen_stats['Rendimiento_%'] = np.where(
            resumen_stats['Inversion_Inicial'] > 0, 
            (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100, 
            0
        )
        
        # Tamaño relativo a 10k
        resumen_stats['Size_vs_10k_%'] = (resumen_stats['Inversion_Inicial'] / 10000) * 100
