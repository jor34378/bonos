import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 1. CONFIGURACIÓN (Debe ser lo primero)
st.set_page_config(page_title="Analítica de Trades USA", layout="wide")

@st.cache_data
def load_data():
    try:
        # Cargamos el CSV detectando el separador automáticamente
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=None, engine='python')
        
        # LIMPIEZA TOTAL DE COLUMNAS: Sin espacios y todo a MINÚSCULAS para mapear
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Diccionario de mapeo: 'nombre_en_minúsculas_en_csv': 'nombre_que_usara_el_codigo'
        mapeo = {
            'ticker': 'Ticker',
            'inversion_usa': 'Inversion_USA',
            'estado_trade': 'Estado_Trade',
            'fecha': 'fecha',
            'cantidad_usa': 'Cantidad_USA',
            'precio_unitario': 'Precio_Unitario',
            'id_trade': 'ID_Trade'
        }
        
        # Renombramos solo las que existan
        df = df.rename(columns={k: v for k, v in mapeo.items() if k in df.columns})
        
        # Verificación de columna crítica 'fecha'
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        else:
            # Si no se llama 'fecha', buscamos una que contenga 'date' o 'time'
            fallback_date = [c for c in df.columns if 'fec' in c.lower() or 'dat' in c.lower()]
            if fallback_date:
                df = df.rename(columns={fallback_date[0]: 'fecha'})
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')

        return df
    except Exception as e:
        st.error(f"❌ Error al leer el archivo: {e}")
        return None

# --- LÓGICA DE LA APP ---
st.title("📊 Análisis de Estrategia - Acciones USA")
df_trades = load_data()

if df_trades is not None:
    try:
        # 2. PROCESAMIENTO
        # Solo trades cerrados
        df_cerrados = df_trades[df_trades['Estado_Trade'] == 'Cerrado'].copy()

        # Agrupación con nombrado explícito para evitar el error de 'fecha'
        resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
            Fecha_In=('fecha', 'min'),
            Fecha_Out=('fecha', 'max'),
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()

        # 3. CÁLCULOS DE PERFORMANCE
        resumen_stats['Resultado_USD'] = resumen_stats['Neto_Flujo']
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        
        # Evitar división por cero en Cant_Total
        resumen_stats['Precio_Salida'] = np.where(
            resumen_stats['Cant_Total'] > 0,
            (resumen_stats['Inversion_Inicial'] + resumen_stats['Resultado_USD']) / resumen_stats['Cant_Total'],
            0
        )
        
        resumen_stats['Rendimiento_%'] = np.where(
            resumen_stats['Inversion_Inicial'] > 0,
            (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100,
            0
        )

        # Métricas
        ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0]
        perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0]
        
        total_trades = len(resumen_stats)
        win_rate = (len(ganadores) / total_trades * 100) if total_trades > 0 else 0
        
        # --- 4. INTERFAZ ---
        c1, c2, c3 = st.columns(3)
        c1.metric("Win Rate", f"{win_rate:.1f}%")
        c2.metric("P&L Total", f"${resumen_stats['Resultado_USD'].sum():,.2f}")
        c3.metric("Trades Cerrados", total_trades)

        st.write("---")
        
        # Gráficos
        fig, ax = plt.subplots(1, 2, figsize=(12, 4))
        ax[0].pie([len(ganadores), len(perdedores)], labels=['Wins', 'Losses'], autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'])
        sns.histplot(resumen_stats['Resultado_USD'], kde=True, ax=ax[1])
        st.pyplot(fig)

        # --- 5. MONTE CARLO ---
        st.sidebar.header("Simulación")
        cap_inicial = st.sidebar.number_input("Capital Inicial", 6000)
        
        if total_trades > 0:
            st.subheader("Simulación Monte Carlo")
            resultados = []
            avg_win = ganadores['Resultado_USD'].mean() if not ganadores.empty else 60
            avg_loss = abs(perdedores['Resultado_USD'].mean()) if not perdedores.empty else 30
            
            for _ in range(500): # 500 rutas para velocidad
                eventos = np.random.choice([avg_win, -avg_loss], size=total_trades, p=[win_rate/100, 1-win_rate/100])
                ruta = cap_inicial + np.cumsum(eventos)
                resultados.append(ruta[-1])
                plt.plot(ruta, color='blue', alpha=0.05)
            
            st.write(f"Esperanza de Ganancia: **${np.mean(resultados)-cap_inicial:,.2f}**")
            st.pyplot(plt.gcf())
            plt.close()

    except KeyError as e:
        st.error(f"❌ Error: No se encontró la columna {e}")
        st.write("Columnas detectadas en tu archivo:", list(df_trades.columns))
    except Exception as e:
        st.error(f"❌ Error inesperado: {e}")
