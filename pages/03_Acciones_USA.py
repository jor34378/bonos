import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Performance Avanzada - USA", layout="wide")

@st.cache_data
def load_data():
    try:
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=None, engine='python')
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        mapeo = {
            'ticker': 'Ticker', 'inversion_usa': 'Inversion_USA',
            'estado_trade': 'Estado_Trade', 'fecha': 'fecha',
            'cantidad_usa': 'Cantidad_USA', 'precio_unitario': 'Precio_Unitario',
            'id_trade': 'ID_Trade'
        }
        df = df.rename(columns={k: v for k, v in mapeo.items() if k in df.columns})
        
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        else:
            cols_fec = [c for c in df.columns if 'fec' in c or 'dat' in c]
            if cols_fec:
                df = df.rename(columns={cols_fec[0]: 'fecha'})
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"❌ Error crítico al leer el CSV: {e}")
        return None

# --- INICIO DE LA APP ---
st.title("🚀 Dashboard de Trading (Benchmark 10k)")
df_trades = load_data()

if df_trades is not None:
    try:
        # --- 2. LÓGICA DE CIERRE FORZADO (DIS, F) ---
        check_cierre = df_trades.groupby('ID_Trade')['Cantidad_USA'].sum().abs()
        ids_cerrados = check_cierre[check_cierre < 0.1].index
        df_trades.loc[df_trades['ID_Trade'].isin(ids_cerrados), 'Estado_Trade'] = 'Cerrado'

        # --- 3. SEPARACIÓN ---
        df_abiertos_raw = df_trades[df_trades['Estado_Trade'].str.contains('Abierto', case=False, na=False)].copy()
        df_cerrados = df_trades[(df_trades['Estado_Trade'].str.contains('Cerrado', case=False, na=False)) & (df_trades['fecha'].notnull())].copy()

        # --- 4. MÉTRICAS SUPERIORES ---
        resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Rendimiento_%'] = np.where(resumen_stats['Inversion_Inicial'] > 0, (resumen_stats['Neto_Flujo'] / resumen_stats['Inversion_Inicial']) * 100, 0)
        
        ganadores = resumen_stats[resumen_stats['Neto_Flujo'] > 0]
        perdedores = resumen_stats[resumen_stats['Neto_Flujo'] <= 0]
        
        st.subheader("📌 Análisis de Gestión y Riesgo")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Win Rate", f"{(len(ganadores)/len(resumen_stats)*100):.1f}%" if len(resumen_stats)>0 else "0%")
        m2.metric("Avg Size (10k)", f"{(resumen_stats['Inversion_Inicial'].mean()/100):.2f}%")
        p_factor = ganadores['Neto_Flujo'].sum() / abs(perdedores['Neto_Flujo'].sum()) if not perdedores.empty else 0
        m3.metric("Profit Factor", f"{p_factor:.2f}x")
        m4.metric("Pond. Ganancia", f"{(ganadores['Rendimiento_%'].mean() if not ganadores.empty else 0):.2f}%")
        m5.metric("Pond. Pérdida", f"{(perdedores['Rendimiento_%'].mean() if not perdedores.empty else 0):.2f}%")

        # --- 5. TABLA POSICIONES ACTUALES (ESTILO CAPTURA) ---
        st.write("---")
        st.subheader("⚪ Posiciones Actuales")
        
        if not df_abiertos_raw.empty:
            # Consolidamos el ciclo abierto
            pos_actuales = df_abiertos_raw.groupby(['Ticker', 'ID_Trade']).agg(
                Posicion_Acum=('Cantidad_USA', 'sum'),
                Costo_USD=('Inversion_USA', lambda x: abs(x.sum()))
            ).reset_index()
            
            # Agregamos selector de precio para valuar
            st.write("👉 *Ingresá el precio de mercado para valuar la cartera:*")
            input_data = pd.DataFrame({'Ticker': pos_actuales['Ticker'], 'Precio_Mercado': 0.0})
            edit_precios = st.data_editor(input_data, hide_index=True, use_container_width=True)
            
            # Cálculos finales para la tabla
            tabla_final = pd.merge(pos_actuales, edit_precios, on='Ticker')
            tabla_final['Valuacion_USD'] = tabla_final['Posicion_Acum'] * tabla_final['Precio_Mercado']
            tabla_final['Ganancia_USD'] = tabla_final['Valuacion_USD'] - tabla_final['Costo_USD']
            tabla_final['Rend_%'] = (tabla_final['Ganancia_USD'] / tabla_final['Costo_USD']) * 100
            
            # Reordenar columnas como en tu foto
            cols_orden = ['Ticker', 'ID_Trade', 'Posicion_Acum', 'Valuacion_USD', 'Costo_USD', 'Ganancia_USD', 'Rend_%']
            tabla_final = tabla_final[cols_orden]

            # Estilo: Rojo para pérdidas, Verde para ganancias
            def highlight_pnl(val):
                color = '#910c11' if val < 0 else '#0c633a' # Tonos de tu captura
                return f'background-color: {color}; color: white'

            st.dataframe(
                tabla_final.style.format({
                    'Posicion_Acum': '{:,.4f}', 'Valuacion_USD': 'U$S {:,.2f}', 
                    'Costo_USD': 'U$S {:,.2f}', 'Ganancia_USD': 'U$S {:,.2f}', 'Rend_%': '{:.2f}%'
                }).applymap(highlight_pnl, subset=['Ganancia_USD', 'Rend_%']), 
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No hay trades abiertos.")

        # --- 6. GRÁFICOS ---
        st.write("---")
        c1, c2 = st.columns(2); c3, c4 = st.columns(2)
        with c1:
            f1, ax1 = plt.subplots(figsize=(8,4)); sns.histplot(resumen_stats['Neto_Flujo'], kde=True, ax=ax1)
            st.pyplot(f1)
        with c2:
            f2, ax2 = plt.subplots(figsize=(8,4))
            if not df_abiertos_raw.empty:
                pesos = tabla_final.set_index('Ticker')['Costo_USD']
                ax2.pie(pesos, labels=pesos.index, autopct='%1.1f%%'); ax2.set_title("Asset Allocation")
                st.pyplot(f2)
        # ... Resto de gráficos igual ...

    except Exception as e:
        st.error(f"⚠️ Error en el procesamiento: {e}")
