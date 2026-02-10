import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Ingeniería de Tráfico: Onda Verde Pro 2026", layout="wide")

def main():
    st.title("🚦 Diseño Profesional de Onda Verde")
    st.markdown("""
    Diagrama técnico de **bandas paralelas rígidas**. 
    Optimizado para la versión de Streamlit 2026.
    """)

    # --- ESTADO DE SESIÓN ---
    if 'num_cruces' not in st.session_state:
        st.session_state.num_cruces = 4

    # --- SIDEBAR: PARÁMETROS TÉCNICOS ---
    st.sidebar.header("⚙️ Parámetros de Diseño")
    c_total = st.sidebar.number_input("Ciclo Total (C) [s]", value=90, min_value=30)
    v_kmh = st.sidebar.slider("Velocidad de Diseño (km/h)", 20, 80, 50)
    v_ms = v_kmh / 3.6
    num_ciclos = st.sidebar.slider("Ciclos en Gráfico", 1, 4, 2)

    # --- GESTIÓN DE CRUCES ---
    st.subheader("📍 Configuración de Intersecciones")
    c1, c2, _ = st.columns([1, 1, 4])
    if c1.button("➕ Añadir Cruce"):
        st.session_state.num_cruces += 1
        st.rerun()
    if c2.button("➖ Quitar Cruce") and st.session_state.num_cruces > 2:
        st.session_state.num_cruces -= 1
        st.rerun()

    n = st.session_state.num_cruces
    cols = st.columns(n)
    config = []
    
    for i in range(n):
        with cols[i]:
            name = chr(65 + i)
            st.markdown(f"**Cruce {name}**")
            off = st.slider(f"Offset", 0, int(c_total), key=f"off_{i}")
            ver = st.slider(f"Verde", 5, int(c_total), key=f"ver_{i}", value=45)
            dist = 0 if i == 0 else st.number_input(f"Dist. {chr(65+i-1)}-{name}", 50, 1500, 400, key=f"dist_{i}")
            config.append({"ID": name, "Offset": off, "Verde": ver, "Dist": dist})

    # --- CÁLCULO DE BANDA ---
    df = pd.DataFrame(config)
    df['Dist_Acum'] = df['Dist'].cumsum()
    verde_min = df['Verde'].min()

    st.sidebar.divider()
    t_ini = st.sidebar.slider("Inicio Banda (Cruce A)", 0, int(c_total), key="t_ini")
    ancho = st.sidebar.slider("Ancho de Banda [s]", 1, int(verde_min), int(verde_min))

    # --- FUNCIÓN DE OPTIMIZACIÓN ---
    def optimizar():
        base_t = st.session_state.t_ini
        for i, row in df.iterrows():
            t_viaje = row['Dist_Acum'] / v_ms
            st.session_state[f"off_{i}"] = int((base_t + t_viaje) % c_total)

    st.button("🎯 Alinear Offsets al Inicio de Banda", on_click=optimizar)

    # --- GRÁFICO PROFESIONAL ---
    fig = go.Figure()

    for _, row in df.iterrows():
        x = row['Dist_Acum']
        for k in range(num_ciclos):
            t_base = k * c_total
            # Rojo (Fondo)
            fig.add_trace(go.Scatter(x=[x,x], y=[t_base, t_base+c_total], mode='lines', 
                                    line=dict(color='#E74C3C', width=25), showlegend=False))
            # Verde
            s, d = row['Offset'], row['Verde']
            def draw_v(start, end):
                fig.add_trace(go.Scatter(x=[x,x], y=[t_base+start, t_base+end], mode='lines', 
                                        line=dict(color='#2ECC71', width=25), showlegend=False))
            if s + d <= c_total:
                draw_v(s, s+d)
            else:
                draw_v(s, c_total); draw_v(0, s+d-c_total)

    # Dibujar Banda de Progresión
    for k in range(num_ciclos):
        t0 = k * c_total + t_ini
        x_pts = df['Dist_Acum'].tolist()
        y_inf = [t0 + (d / v_ms) for d in x_pts]
        y_sup = [t + ancho for t in y_inf]
        
        fig.add_trace(go.Scatter(
            x=x_pts + x_pts[::-1],
            y=y_inf + y_sup[::-1],
            fill='toself',
            fillcolor='rgba(52, 152, 219, 0.3)',
            line=dict(color='rgba(41, 128, 185, 0.8)', width=2),
            name="Banda de Progresión" if k==0 else ""
        ))

    fig.update_layout(
        xaxis_title="Distancia [m]", yaxis_title="Tiempo [s]",
        xaxis=dict(tickvals=df['Dist_Acum'], ticktext=df['ID'], gridcolor='#f0f0f0'),
        yaxis=dict(range=[0, num_ciclos*c_total], gridcolor='#f0f0f0'),
        plot_bgcolor='white', height=750
    )

    # FIX 2026: Reemplazo de use_container_width por width='stretch'
    st.plotly_chart(fig, width='stretch')

    # --- MÉTRICAS ---
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Velocidad de Diseño", f"{v_kmh} km/h")
    m2.metric("Ancho de Banda", f"{ancho} s")
    m3.metric("Eficiencia", f"{(ancho/c_total)*100:.1f}%")

if __name__ == "__main__":
    main()