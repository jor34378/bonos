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
        # Limpieza idéntica a tu primer código (la que te funcionaba)
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
        # --- 2. LIMPIEZA DE DECIMALES (DIS, F, etc.) ---
        # Forzamos cierre si la cantidad neta del ID_Trade es casi cero
        check_cierre = df_trades.groupby('ID_Trade')['Cantidad_USA'].sum().abs()
        ids_cerrados_ficticios = check_cierre[check_cierre < 0.1].index
        df_trades.loc[df_trades['ID_Trade'].isin(ids_cerrados_ficticios), 'Estado_Trade'] = 'Cerrado'

        # --- 3. SEPARACIÓN Y PROCESAMIENTO ---
        df_abiertos_raw = df_trades[df_trades['Estado_Trade'].str.contains('Abierto', case=False, na=False)].copy()
        df_cerrados = df_trades[(df_trades['Estado_Trade'].str.contains('Cerrado', case=False, na=False)) & (df_trades['fecha'].notnull())].copy()

        # Consolidación de ABIERTOS (El Ciclo)
        resumen_abiertos = df_abiertos_raw.groupby(['Ticker', 'ID_Trade']).agg(
            Fecha_In=('fecha', 'min'),
            Cant_Neta=('Cantidad_USA', 'sum'),
            Inversion_Total=('Inversion_USA', 'sum')
        ).reset_index()
        
        # Cálculo de PPP Simple para el ciclo
        resumen_abiertos['PPP_Compra'] = (resumen_abiertos['Inversion_Total'].abs() * 100) / resumen_abiertos['Cant_Neta'].abs()
        resumen_abiertos = resumen_abiertos[resumen_abiertos['Cant_Neta'] > 0.1]

        # Estadísticas de CERRADOS
        resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
            Fecha_In=('fecha', 'min'),
            Fecha_Out=('fecha', 'max'),
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()

        resumen_stats['Resultado_USD'] = resumen_stats['Neto_Flujo']
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Rendimiento_%'] = np.where(resumen_stats['Inversion_Inicial'] > 0, 
                                                (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100, 0)
        resumen_stats['Size_vs_10k_%'] = (resumen_stats['Inversion_Inicial'] / 10000) * 100

        ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
        perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()

        # --- 4. MÉTRICAS PONDERADAS ---
        st.subheader("📌 Análisis de Gestión y Riesgo")
        m1, m2, m3, m4, m5 = st.columns(5)
        
        win_rate = (len(ganadores) / len(resumen_stats) * 100) if not resumen_stats.empty else 0
        m1.metric("Win Rate", f"{win_rate:.1f}%")
        
        def ponderado(df):
            if df.empty or df['Inversion_Inicial'].sum() == 0: return 0
            return (df['Rendimiento_%'] * df['Inversion_Inicial']).sum() / df['Inversion_Inicial'].sum()

        m2.metric("Prom. Pond. (+)", f"{ponderado(ganadores):.2f}%")
        m3.metric("Prom. Pond. (-)", f"{ponderado(perdedores):.2f}%")
        m4.metric("Avg Size (10k)", f"{resumen_stats['Size_vs_10k_%'].mean():.2f}%")
        
        p_factor = ganadores['Resultado_USD'].sum() / abs(perdedores['Resultado_USD'].sum()) if not perdedores.empty else 0
        m5.metric("Profit Factor", f"{p_factor:.2f}x")

        # --- 5. TABLA DE ABIERTOS (CICLOS) ---
        st.write("---")
        st.subheader("📂 Seguimiento de Trades Abiertos")
        if not resumen_abiertos.empty:
            # Editor de precios para calcular P&L latente
            precios_input = pd.DataFrame({
                'Ticker': resumen_abiertos['Ticker'],
                'Precio_Actual': resumen_abiertos['PPP_Compra']
            })
            
            col_t1, col_t2 = st.columns([1, 3])
            with col_t1:
                st.write("✏️ Ajustar Precios:")
                edit_p = st.data_editor(precios_input, hide_index=True)
            
            with col_t2:
                # Merge para cálculos finales
                res_fin = pd.merge(resumen_abiertos, edit_p, on='Ticker')
                res_fin['P&L_Latente'] = (res_fin['Precio_Actual'] - res_fin['PPP_Compra']) * (res_fin['Cant_Neta'] / 100)
                res_fin['ROI_Latente_%'] = ((res_fin['Precio_Actual'] / res_fin['PPP_Compra']) - 1) * 100
                
                st.dataframe(res_fin.style.format({
                    'Cant_Neta': '{:.2f}', 'PPP_Compra': '${:,.2f}', 
                    'Precio_Actual': '${:,.2f}', 'P&L_Latente': '${:,.2f}', 'ROI_Latente_%': '{:.2f}%'
                }).background_gradient(subset=['ROI_Latente_%'], cmap='RdYlGn'), use_container_width=True)
        else:
            st.info("No hay trades abiertos significativos.")

        # --- 6. CUADRANTE 2x2 ---
        st.write("---")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        fig_sz = (8, 4.5)

        with c1:
            f1, ax1 = plt.subplots(figsize=fig_sz); sns.histplot(resumen_stats['Resultado_USD'], kde=True, color='teal', ax=ax1)
            ax1.set_title("Distribución P&L (USD)"); st.pyplot(f1)
        with c2:
            f2, ax2 = plt.subplots(figsize=fig_sz)
            if not resumen_abiertos.empty:
                data_p = resumen_abiertos.groupby('Ticker')['Inversion_Total'].sum().abs()
                ax2.pie(data_p, labels=data_p.index, autopct='%1.1f%%', startangle=140, colors=sns.color_palette("viridis"))
                ax2.set_title("Asset Allocation (Abiertos)")
            st.pyplot(f2)
        with c3:
            f3, ax3 = plt.subplots(figsize=fig_sz); colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in resumen_stats['Rendimiento_%']]
            ax3.scatter(resumen_stats.index, resumen_stats['Rendimiento_%'], c=colors, alpha=0.6)
            ax3.axhline(0, color='black', lw=1, ls='--'); ax3.set_title("ROI % Individual"); st.pyplot(f3)
        with c4:
            f4, ax4 = plt.subplots(figsize=fig_sz); equity = 10000 + resumen_stats['Resultado_USD'].cumsum()
            ax4.plot(equity.values, color='royalblue', lw=2.5); ax4.fill_between(range(len(equity)), equity, 10000, alpha=0.15)
            ax4.set_title("Equity Curve (Base 10k)"); st.pyplot(f4)

        # --- 7. MONTE CARLO ---
        st.write("---")
        st.write("### 🎲 Proyección Monte Carlo")
        n_sim = st.sidebar.slider("Simulaciones", 100, 1000, 500)
        f_mc, ax_mc = plt.subplots(figsize=(16, 6))
        all_p = []
        for _ in range(n_sim):
            draws = np.random.choice(resumen_stats['Resultado_USD'], size=len(resumen_stats), replace=True)
            path = 10000 + np.cumsum(draws)
            all_p.append(path); ax_mc.plot(path, color='gray', alpha=0.03)
        ax_mc.plot(np.median(all_p, axis=0), color='gold', lw=4, label="P50"); ax_mc.legend(); st.pyplot(f_mc)

        # --- 8. TABS DETALLE ---
        st.write("---")
        t1, t2, t3 = st.tabs(["📂 Abiertos", "✅ Ganadores", "❌ Perdedores"])
        with t1: st.dataframe(resumen_abiertos, use_container_width=True)
        with t2: st.dataframe(ganadores.sort_values('Resultado_USD', ascending=False), use_container_width=True)
        with t3: st.dataframe(perdedores.sort_values('Resultado_USD', ascending=True), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Error en el procesamiento: {e}")
