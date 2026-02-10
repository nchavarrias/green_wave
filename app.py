import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Sincronizador: Inicio de Verde", layout="wide")

def main():
    st.title("🚦 Sincronizador: Alineación al Inicio de Verde")
    st.markdown("El botón de optimización ajustará los offsets para que el verde comience exactamente cuando llega la banda.")
    
    # --- ESTADO DE LA SESIÓN ---
    if 'num_cruces' not in st.session_state:
        st.session_state.num_cruces = 4
    
    # --- SIDEBAR ---
    st.sidebar.header("⚙️ Configuración de la Vía")
    num_cruces = st.sidebar.slider("Número de cruces", 2, 10, st.session_state.num_cruces)
    st.session_state.num_cruces = num_cruces
    
    c_total = st.sidebar.number_input("Ciclo Total (C) [s]", value=90, min_value=30)
    num_ciclos = st.sidebar.slider("Ciclos visibles", 1, 5, 2)
    v_kmh = st.sidebar.slider("Velocidad Deseada (km/h)", 20, 80, 50)
    v_ms = v_kmh / 3.6

    # --- LÓGICA DE OPTIMIZACIÓN (INICIO DE VERDE) ---
    temp_distances = [0]
    for i in range(1, num_cruces):
        d_val = st.session_state.get(f"dist_{i}", 300)
        temp_distances.append(temp_distances[-1] + d_val)

    def optimizar_al_inicio():
        """Alinea el inicio del verde con el inicio de la banda de progresión."""
        # El tiempo de llegada del inicio de la banda a cada cruce d es:
        # T_inicio_llegada = t_inicio_banda + (distancia / v_ms)
        t_referencia_inicial = st.session_state.t_ini
        
        for i in range(num_cruces):
            distancia = temp_distances[i]
            tiempo_llegada_banda = t_referencia_inicial + (distancia / v_ms)
            
            # El offset es simplemente el tiempo de llegada (módulo el ciclo)
            offset_ideal = tiempo_llegada_banda % c_total
            
            # Actualizamos el estado del slider
            st.session_state[f"off_{i}"] = int(offset_ideal)

    # --- PANEL DE CONTROL ---
    st.subheader("🎮 Ajuste de Intersecciones")
    
    # Botón de Optimización actualizado
    st.button("🚀 Optimizar: Alinear Inicio de Verde", on_click=optimizar_al_inicio)
    
    cols = st.columns(num_cruces)
    config_list = []
    
    for i in range(num_cruces):
        with cols[i]:
            st.markdown(f"**Cruce {chr(65+i)}**")
            off = st.slider(f"Offset", 0, int(c_total), key=f"off_{i}")
            ver = st.slider(f"Verde", 5, int(c_total), 40, key=f"ver_{i}")
            dist = 0 if i == 0 else st.number_input(f"Dist. desde {chr(65+i-1)}", 50, 1000, 300, key=f"dist_{i}")
            
            config_list.append({"Cruce": chr(65+i), "Dist": dist, "Offset": off, "Verde": ver})

    df = pd.DataFrame(config_list)
    verde_min = int(df["Verde"].min())

    # --- CONTROLES DE BANDA ---
    st.sidebar.divider()
    st.sidebar.header("📏 Parámetros de la Banda")
    t_inicio_banda = st.sidebar.slider("Inicio de la Banda [s]", 0, int(c_total), key="t_ini")
    ancho_banda = st.sidebar.slider("Ancho de la Banda [s]", 1, int(c_total), verde_min, key="ancho")

    # --- GRÁFICO ---
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
            # Fondo Rojo (Líneas gruesas para simular la barra del semáforo)
            fig.add_trace(go.Scatter(x=[x,x], y=[t_base, t_base+c_total], mode='lines', 
                                    line=dict(color='#FF4B4B', width=20), showlegend=False, hoverinfo='skip'))
            
            # Ventana Verde
            s, d = row["Offset"], row["Verde"]
            def plot_v(start, end):
                fig.add_trace(go.Scatter(x=[x,x], y=[t_base+start, t_base+end], mode='lines', 
                                        line=dict(color='#00FF00', width=20), showlegend=False))
            
            if s + d <= c_total:
                plot_v(s, s+d)
            else:
                plot_v(s, c_total)
                plot_v(0, s+d-c_total)

    # Dibujar la Banda de Progresión (Área sombreada)
    for k in range(num_ciclos):
        t0 = k * c_total + t_inicio_banda
        y_inf = [t0 + (dist/v_ms) for dist in dist_acum]
        y_sup = [t + ancho_banda for t in y_inf]
        
        fig.add_trace(go.Scatter(
            x=dist_acum + dist_acum[::-1], 
            y=y_inf + y_sup[::-1],
            fill='toself', 
            fillcolor='rgba(128,128,128,0.4)', 
            line=dict(color='rgba(0,0,0,0.7)', width=2), 
            name="Banda de Progresión",
            showlegend=k==0
        ))

    # Estética del gráfico
    fig.update_layout(
        xaxis_title="Distancia (Cruces) [m]", 
        yaxis_title="Tiempo [s]", 
        xaxis=dict(tickvals=dist_acum, ticktext=df["Cruce"], range=[-100, max(dist_acum)+100]),
        yaxis=dict(range=[0, num_ciclos*c_total], gridcolor='#e5e5e5'), 
        plot_bgcolor='white', 
        height=700
    )

    st.plotly_chart(fig, width='stretch')

    # Validación visual
    st.info(f"📐 **Ancho de banda actual:** {ancho_banda} segundos. El inicio de cada bloque verde está sincronizado con la base de la banda gris.")

if __name__ == "__main__":
    main()