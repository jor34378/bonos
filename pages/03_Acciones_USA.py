import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="Performance Avanzada - USA", layout="wide")

@st.cache_data
def load_data():
    try:
        df = pd.read_csv('reporte_trades_para_USA.csv', sep=None, engine='python')
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Mapeo forzado para evitar errores de nombres
        mapeo = {
            'ticker': 'Ticker', 'inversion_usa': 'Inversion_USA',
            'estado_trade': 'Estado_Trade', 'fecha': 'fecha',
            'cantidad_usa': 'Cantidad_USA', 'precio_unitario': 'Precio_Unitario',
            'id_trade': 'ID_Trade'
        }
        df = df.rename(columns={k: v for k, v in mapeo.items() if k in df.columns})
        
        # Validación de columna fecha
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        else:
            # Si el CSV tiene otro nombre, intentamos detectarlo
            posibles_fechas = [c for c in df.columns if 'fec' in c.lower() or 'dat' in c.lower()]
            if posibles_fechas:
                df = df.rename(columns={posibles_fechas[0]: 'fecha'})
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        
        return df
    except Exception as e:
        st.error(f"❌ Error al leer el archivo: {e}")
        return None

st.title("🚀 Dashboard de Trading de Alta Precisión")
df_trades = load_data()

if df_trades is not None:
    try:
        # --- 1. PROCESAMIENTO ROBUSTO ---
        # Filtramos solo cerrados y nos aseguramos de que tengan fecha válida
        df_cerrados = df_trades[(df_trades['Estado_Trade'] == 'Cerrado') & (df_trades['fecha'].notnull())].copy()

        # Agregación Nombrada: Aquí evitamos el KeyError definiendo nombres nuevos
        resumen_stats = df_cerrados.groupby(['Ticker', 'ID_Trade']).agg(
            Fecha_In=('fecha', 'min'),
            Fecha_Out=('fecha', 'max'),
            Neto_Flujo=('Inversion_USA', 'sum'),
            Cant_Total=('Cantidad_USA', lambda x: x[x > 0].sum()),
            Precio_Entrada=('Precio_Unitario', 'first')
        ).reset_index()

        # Cálculos de Métricas
        resumen_stats['Resultado_USD'] = resumen_stats['Neto_Flujo']
        resumen_stats['Inversion_Inicial'] = resumen_stats['Cant_Total'] * resumen_stats['Precio_Entrada']
        resumen_stats['Rendimiento_%'] = np.where(resumen_stats['Inversion_Inicial'] > 0, 
                                                (resumen_stats['Resultado_USD'] / resumen_stats['Inversion_Inicial']) * 100, 0)
        resumen_stats['Size_vs_10k_%'] = (resumen_stats['Inversion_Inicial'] / 10000) * 100

        ganadores = resumen_stats[resumen_stats['Resultado_USD'] > 0].copy()
        perdedores = resumen_stats[resumen_stats['Resultado_USD'] <= 0].copy()

        # --- 2. MÉTRICAS DEL ENCABEZADO ---
        def ponderado(df):
            if df.empty or df['Inversion_Inicial'].sum() == 0: return 0
            return (df['Rendimiento_%'] * df['Inversion_Inicial']).sum() / df['Inversion_Inicial'].sum()

        st.subheader("📌 Métricas de Gestión de Riesgo (Benchmark 10k USD)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Prom. Ponderado Ganancia", f"{ponderado(ganadores):.2f}%")
        m2.metric("Prom. Ponderado Pérdida", f"{ponderado(perdedores):.2f}%")
        m3.metric("Avg Trade Size (s/10k)", f"{resumen_stats['Size_vs_10k_%'].mean():.2f}%")
        m4.metric("Profit Factor", f"{(ganadores['Resultado_USD'].sum() / abs(perdedores['Resultado_USD'].sum())):.2f}x" if not perdedores.empty else "N/A")

        # --- 3. GRÁFICOS (4 LÍMITES) ---
        st.write("---")
        c_g1, c_g2 = st.columns(2)
        with c_g1:
            # G1: Histograma
            fig1, ax1 = plt.subplots(figsize=(8, 4))
            sns.histplot(resumen_stats['Resultado_USD'], kde=True, color='teal', ax=ax1)
            ax1.set_title("Distribución de P&L")
            st.pyplot(fig1)
            # G2: Scatter de Consistencia
            fig2, ax2 = plt.subplots(figsize=(8, 4))
            ax2.scatter(resumen_stats.index, resumen_stats['Rendimiento_%'], 
                        c=np.where(resumen_stats['Rendimiento_%'] > 0, 'g', 'r'), alpha=0.5)
            ax2.axhline(0, color='black', lw=1)
            ax2.set_title("Consistencia: ROI % por Operación")
            st.pyplot(fig2)

        with c_g2:
            # G3: Pie Win Rate
            fig3, ax3 = plt.subplots(figsize=(5, 4))
            ax3.pie([len(ganadores), len(perdedores)], labels=['Wins', 'Losses'], autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'])
            ax3.set_title("Efectividad")
            st.pyplot(fig3)
            # G4: Equity Curve
            fig4, ax4 = plt.subplots(figsize=(8, 4))
            ax4.plot((10000 + resumen_stats['Resultado_USD'].cumsum()).values, color='royalblue', lw=2)
            ax4.set_title("Curva de Capital (Base 10k)")
            st.pyplot(fig4)

        # --- 4. MONTE CARLO CON MEDIANA ---
        st.write("---")
        st.write("### 🎲 Simulación Monte Carlo & Mediana (P50)")
        n_sim = st.sidebar.slider("Simulaciones", 100, 1000, 500)
        
        fig_mc, ax_mc = plt.subplots(figsize=(16, 7))
        rutas = []
        for _ in range(n_sim):
            # Bootstrapping: Remuestreo de tus propios resultados reales
            cambios = np.random.choice(resumen_stats['Resultado_USD'], size=len(resumen_stats), replace=True)
            ruta = 10000 + np.cumsum(cambios)
            rutas.append(ruta)
            ax_mc.plot(ruta, color='gray', alpha=0.03)
        
        ax_mc.plot(np.median(rutas, axis=0), color='gold', lw=4, label="Mediana (Camino más probable)")
        ax_mc.axhline(10000, color='red', ls='--')
        ax_mc.legend()
        st.pyplot(fig_mc)

        # --- 5. TABLAS DE TRADES ---
        st.write("---")
        st.subheader("📜 Detalle de Operaciones")
        
        # Formateo visual
        resumen_stats['Fecha_In'] = resumen_stats['Fecha_In'].dt.date
        resumen_stats['Fecha_Out'] = resumen_stats['Fecha_Out'].dt.date
        
        fmt = {'Inversion_Inicial': '${:,.2f}', 'Resultado_USD': '${:,.2f}', 
               'Rendimiento_%': '{:.2f}%', 'Size_vs_10k_%': '{:.2f}%',
               'Cant_Total': '{:.4f}'}
        
        t1, t2 = st.tabs(["Ganadores ✅", "Perdedores ❌"])
        with t1: st.dataframe(ganadores.style.format(fmt), use_container_width=True)
        with t2: st.dataframe(perdedores.style.format(fmt), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Error detallado: {e}")
        st.write("Columnas actuales en el DF:", list(df_trades.columns))
