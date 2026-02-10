import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Control de Offset Interactivo", layout="wide")

def main():
    st.title("🚦 Panel de Control de Sincronismo Semafórico")
    
    # --- INICIALIZACIÓN ---
    if 'num_cruces' not in st.session_state:
        st.session_state.num_cruces = 4
    
    # --- SIDEBAR: PARÁMETROS FIJOS ---
    st.sidebar.header("⚙️ Configuración Global")
    num_cruces = st.sidebar.slider("Número de cruces", 2, 10, st.session_state.num_cruces)
    st.session_state.num_cruces = num_cruces
    
    c_total = st.sidebar.number_input("Ciclo Total (C) [s]", value=90, min_value=30)
    num_ciclos = st.sidebar.slider("Ciclos visibles", 1, 5, 2)
    v_kmh = st.sidebar.slider("Velocidad (km/h)", 20, 80, 50)
    v_ms = v_kmh / 3.6

    # --- PANEL DE CONTROL INTERACTIVO (Offsets y Verdes) ---
    st.subheader("🎮 Ajuste en Tiempo Real de Cruces")
    cols = st.columns(num_cruces)
    
    config_list = []
    
    for i in range(num_cruces):
        with cols[i]:
            st.markdown(f"**Cruce {chr(65+i)}**")
            # Estos sliders actúan como el "arrastre" manual que pedías
            off = st.slider(f"Offset", 0, int(c_total), i*15, key=f"off_{i}")
            ver = st.slider(f"Verde", 5, int(c_total), 40, key=f"ver_{i}")
            dist = 0 if i == 0 else st.number_input(f"Dist. prec.", 50, 1000, 300, key=f"dist_{i}")
            
            config_list.append({
                "Cruce": chr(65+i),
                "Dist": dist,
                "Offset": off,
                "Verde": ver
            })

    # --- CÁLCULO DE BANDA RESTRICTIVA ---
    df = pd.DataFrame(config_list)
    ancho_max_posible = int(df["Verde"].min())
    
    st.sidebar.divider()
    st.sidebar.header("📏 Ajuste de Banda")
    t_inicio_banda = st.sidebar.slider("Posición de la Banda [s]", 0, int(c_total), 0)
    ancho_banda = st.sidebar.slider("Ancho de Banda [s]", 1, int(c_total), ancho_max_posible)

    # --- LÓGICA DE GRÁFICO ---
    dist_acum = []
    curr_x = 0
    for d in df["Dist"]:
        curr_x += d
        dist_acum.append(curr_x)

    fig = go.Figure()

    for idx, row in df.iterrows():
        x = dist_acum[idx]
        for k in range(num_ciclos):
            t_base = k * c_total
            # Rojo
            fig.add_trace(go.Scatter(x=[x,x], y=[t_base, t_base+c_total], mode='lines', 
                                    line=dict(color='#FF4B4B', width=15), showlegend=False, hoverinfo='skip'))
            # Verde (con lógica de wraparound)
            start, dur = row["Offset"], row["Verde"]
            if start + dur <= c_total:
                fig.add_trace(go.Scatter(x=[x,x], y=[t_base+start, t_base+start+dur], mode='lines', 
                                        line=dict(color='#00FF00', width=15), showlegend=False))
            else:
                fig.add_trace(go.Scatter(x=[x,x], y=[t_base+start, t_base+c_total], mode='lines', 
                                        line=dict(color='#00FF00', width=15), showlegend=False))
                fig.add_trace(go.Scatter(x=[x,x], y=[t_base, t_base+(start+dur-c_total)], mode='lines', 
                                        line=dict(color='#00FF00', width=15), showlegend=False))

    # --- BANDA ---
    for k in range(num_ciclos):
        t0 = k * c_total + t_inicio_banda
        y_inf = [t0 + (d/v_ms) for d in dist_acum]
        y_sup = [t + ancho_banda for t in y_inf]
        fig.add_trace(go.Scatter(x=dist_acum + dist_acum[::-1], y=y_inf + y_sup[::-1],
                                fill='toself', fillcolor='rgba(100,100,100,0.3)', 
                                line=dict(color='black', width=1), name="Banda"))

    fig.update_layout(xaxis_title="Distancia [m]", yaxis_title="Tiempo [s]", 
                      xaxis=dict(tickvals=dist_acum, ticktext=df["Cruce"]),
                      yaxis=dict(range=[0, num_ciclos*c_total]), plot_bgcolor='white', height=600)

    st.plotly_chart(fig, width='stretch')
    
    if ancho_banda > ancho_max_posible:
        st.error(f"⚠️ ¡Atención! El ancho de banda ({ancho_banda}s) es mayor que el verde más restrictivo ({ancho_max_posible}s).")

if __name__ == "__main__":
    main()