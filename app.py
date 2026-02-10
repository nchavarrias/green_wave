import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Sincronizador Pro: Fix Final", layout="wide")

def main():
    st.title("🚦 Sincronizador de Onda Verde (v2.2)")
    st.markdown("Cálculo de ancho de banda garantizado en tiempo real.")

    # --- GESTIÓN DE ESTADO ---
    if 'num_cruces' not in st.session_state:
        st.session_state.num_cruces = 4

    # --- SIDEBAR: PARÁMETROS GLOBALES ---
    st.sidebar.header("⚙️ Configuración Global")
    c_total = st.sidebar.number_input("Ciclo Total (C) [s]", value=90, min_value=30)
    num_ciclos = st.sidebar.slider("Ciclos visibles", 1, 5, 2)
    v_kmh = st.sidebar.slider("Velocidad Deseada (km/h)", 20, 80, 50)
    v_ms = v_kmh / 3.6

    # --- PANEL DE CONTROL DE CRUCES ---
    st.subheader("📍 Configuración de la Ruta")
    
    col_btns1, col_btns2, _ = st.columns([1, 1, 4])
    with col_btns1:
        if st.button("➕ Añadir Cruce"):
            st.session_state.num_cruces += 1
            st.rerun()
    with col_btns2:
        if st.button("➖ Quitar Cruce") and st.session_state.num_cruces > 2:
            st.session_state.num_cruces -= 1
            st.rerun()

    num_cruces = st.session_state.num_cruces

    # --- CAPTURA DE DATOS ---
    config_list = []
    cols = st.columns(num_cruces)
    verdes_actuales = []

    for i in range(num_cruces):
        with cols[i]:
            nombre = chr(65 + i)
            st.markdown(f"### Cruce {nombre}")
            
            # Recogemos los valores
            off = st.slider(f"Offset {nombre}", 0, int(c_total), key=f"off_{i}")
            ver = st.slider(f"Verde {nombre}", 5, int(c_total), key=f"ver_{i}", value=45)
            verdes_actuales.append(ver)
            
            dist = 0 if i == 0 else st.number_input(f"Dist. {chr(65+i-1)}➡️{nombre}", 50, 2000, 300, key=f"dist_{i}")
            config_list.append({"Cruce": nombre, "Dist": dist, "Offset": off, "Verde": ver})

    # CALCULO CRÍTICO: El verde mínimo disponible en este instante
    verde_min_disponible = min(verdes_actuales)

    # --- OPTIMIZACIÓN ---
    def optimizar_al_inicio():
        t_ref = st.session_state.t_ini_manual
        d_acum = 0
        for i in range(num_cruces):
            d_prev = st.session_state.get(f"dist_{i}", 300) if i > 0 else 0
            d_acum += d_prev
            st.session_state[f"off_{i}"] = int((t_ref + (d_acum / v_ms)) % c_total)

    st.button("🚀 Optimizar: Alinear Inicio de Verde", on_click=optimizar_al_inicio)

    # --- CONTROLES DE BANDA ---
    st.sidebar.divider()
    st.sidebar.header("📏 Parámetros de la Banda")
    t_inicio_banda = st.sidebar.slider("Inicio de la Banda [s]", 0, int(c_total), key="t_ini_manual")
    
    # Aquí está el cambio: El slider controla un "deseo", pero la banda usa la "realidad"
    ancho_deseado = st.sidebar.slider(
        "Ancho de la Banda [s]", 
        min_value=1, 
        max_value=int(c_total), 
        value=min(40, verde_min_disponible)
    )

    # FORZAMOS que el ancho no supere nunca el mínimo de los verdes
    ancho_efectivo = min(ancho_deseado, verde_min_disponible)

    # --- GRÁFICO ---
    df = pd.DataFrame(config_list)
    dist_acum_lista = []
    total_d = 0
    for d in df["Dist"]:
        total_d += d
        dist_acum_lista.append(total_d)
    df["Dist_Acum"] = dist_acum_lista

    fig = go.Figure()

    for idx, row in df.iterrows():
        x = row["Dist_Acum"]
        for k in range(num_ciclos):
            t_base = k * c_total
            # Rojo
            fig.add_trace(go.Scatter(x=[x,x], y=[t_base, t_base+c_total], mode='lines', 
                                    line=dict(color='#FF4B4B', width=20), showlegend=False, hoverinfo='skip'))
            # Verde
            s, d = row["Offset"], row["Verde"]
            def plot_v(start, end):
                fig.add_trace(go.Scatter(x=[x,x], y=[t_base+start, t_base+end], mode='lines', 
                                        line=dict(color='#00FF00', width=20), showlegend=False))
            if s + d <= c_total:
                plot_v(s, s+d)
            else:
                plot_v(s, c_total)
                plot_v(0, s+d-c_total)

    # Dibujar la Banda con el ancho_efectivo
    for k in range(num_ciclos):
        t0 = k * c_total + t_inicio_banda
        y_inf = [t0 + (d/v_ms) for d in dist_acum_lista]
        y_sup = [t + ancho_efectivo for t in y_inf]
        fig.add_trace(go.Scatter(x=dist_acum_lista + dist_acum_lista[::-1], y=y_inf + y_sup[::-1],
                                fill='toself', fillcolor='rgba(128,128,128,0.4)', 
                                line=dict(color='rgba(0,0,0,0.6)', width=2), name="Banda"))

    fig.update_layout(
        xaxis_title="Distancia [m]", yaxis_title="Tiempo [s]",
        xaxis=dict(tickvals=dist_acum_lista, ticktext=df["Cruce"]),
        yaxis=dict(range=[0, num_ciclos*c_total]),
        plot_bgcolor='white', height=700
    )

    st.plotly_chart(fig, width='stretch')
    
    # Feedback al usuario
    if ancho_deseado > verde_min_disponible:
        st.error(f"⚠️ El ancho está limitado a **{verde_min_disponible}s** por el cruce más restrictivo.")
    else:
        st.success(f"✅ Ancho de banda efectivo: **{ancho_efectivo}s**.")

if __name__ == "__main__":
    main()