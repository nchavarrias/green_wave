import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Diagrama de Banda de Progresión Optimizada", layout="wide")

def main():
    st.title("🚦 Diagrama con Ancho de Banda Restrictivo")
    
    # --- INICIALIZACIÓN DE DATOS (Necesario antes de los sliders) ---
    num_cruces_init = 4
    c_total_init = 90
    
    if 'df_data' not in st.session_state:
        st.session_state.df_data = pd.DataFrame({
            "Cruce": [chr(65 + i) for i in range(num_cruces_init)],
            "Dist_al_anterior [m]": [0 if i == 0 else 400 for i in range(num_cruces_init)],
            "Offset (Inicio Verde) [s]": [(i * 20) % c_total_init for i in range(num_cruces_init)],
            "Duracion Verde [s]": [45, 30, 45, 40] # El de 30 será el restrictivo
        })

    # --- SIDEBAR ---
    st.sidebar.header("1. Parámetros Globales")
    num_cruces = st.sidebar.slider("Número de cruces", 2, 8, len(st.session_state.df_data))
    num_ciclos = st.sidebar.slider("Ciclos a mostrar", 1, 5, 2)
    c_total = st.sidebar.number_input("Ciclo Total (C) [s]", value=c_total_init)
    
    st.sidebar.divider()
    st.sidebar.header("2. Control de la Banda")
    v_kmh = st.sidebar.slider("Velocidad (km/h)", 20, 80, 50)
    v_ms = v_kmh / 3.6
    
    # Cálculo del verde más restrictivo (mínimo)
    verde_minimo = int(st.session_state.df_data["Duracion Verde [s]"].min())
    
    t_inicio_banda = st.sidebar.slider("Inicio de banda en Cruce A [s]", 0, int(c_total), 0)
    
    # El valor por defecto es el verde_minimo
    ancho_banda = st.sidebar.slider(
        "Ancho de la banda [s]", 
        min_value=1, 
        max_value=int(c_total), 
        value=verde_minimo,
        help="Por defecto se ajusta al cruce con el verde más corto."
    )

    # --- DATOS DE CRUCES ---
    st.subheader("Configuración de Intersecciones")
    
    # Si el slider de num_cruces cambia, regeneramos el dataframe
    if len(st.session_state.df_data) != num_cruces:
        st.session_state.df_data = pd.DataFrame({
            "Cruce": [chr(65 + i) for i in range(num_cruces)],
            "Dist_al_anterior [m]": [0 if i == 0 else 400 for i in range(num_cruces)],
            "Offset (Inicio Verde) [s]": [(i * 20) % c_total for i in range(num_cruces)],
            "Duracion Verde [s]": [40 for _ in range(num_cruces)]
        })

    edited_df = st.data_editor(st.session_state.df_data, width='stretch', key="editor")
    st.session_state.df_data = edited_df # Guardar cambios

    # Cálculos de distancias acumuladas
    dist_acumulada = []
    curr_x = 0
    for d in edited_df["Dist_al_anterior [m]"]:
        curr_x += d
        dist_acumulada.append(curr_x)

    fig = go.Figure()

    # --- DIBUJAR VERDES Y ROJOS ---
    for idx, row in edited_df.iterrows():
        x = dist_acumulada[idx]
        offset = row["Offset (Inicio Verde) [s]"]
        verde = row["Duracion Verde [s]"]
        nombre = row["Cruce"]
        
        for k in range(num_ciclos):
            t_base = k * c_total
            # Rojo
            fig.add_trace(go.Scatter(
                x=[x, x], y=[t_base, t_base + c_total],
                mode='lines', line=dict(color='#FF4B4B', width=12),
                hoverinfo='skip', showlegend=False
            ))
            # Verde
            def draw_v(start, end, show_leg):
                fig.add_trace(go.Scatter(
                    x=[x, x], y=[t_base + start, t_base + end],
                    mode='lines', line=dict(color='#00FF00', width=12),
                    name=f"Cruce {nombre}" if k==0 else "",
                    legendgroup=nombre, showlegend=show_leg,
                    hovertemplate=f"Cruce {nombre}<br>Tiempo: %{{y}}s"
                ))
            if offset + verde <= c_total:
                draw_v(offset, offset + verde, k == 0)
            else:
                draw_v(offset, c_total, k == 0)
                draw_v(0, (offset + verde) - c_total, False)

    # --- DIBUJAR LA BANDA ---
    for k in range(num_ciclos):
        t0_ciclo = k * c_total + t_inicio_banda
        x_banda = dist_acumulada + dist_acumulada[::-1]
        y_inf = [t0_ciclo + (d / v_ms) for d in dist_acumulada]
        y_sup = [t + ancho_banda for t in y_inf]
        y_banda = y_inf + y_sup[::-1]

        fig.add_trace(go.Scatter(
            x=x_banda, y=y_banda,
            fill='toself',
            fillcolor='rgba(128, 128, 128, 0.3)',
            line=dict(color='rgba(0,0,0,0.5)', width=1),
            name="Banda de Progresión",
            showlegend=k == 0,
            hoverinfo='skip'
        ))

    # --- ESTÉTICA ---
    fig.update_layout(
        xaxis_title="Distancia [m]", yaxis_title="Tiempo [s]",
        xaxis=dict(tickvals=dist_acumulada, ticktext=edited_df["Cruce"], gridcolor='#f0f0f0'),
        yaxis=dict(range=[0, num_ciclos * c_total], gridcolor='#f0f0f0'),
        plot_bgcolor='white', height=750
    )

    st.plotly_chart(fig, width='stretch')

    # Mensaje informativo sobre el restrictivo
    cruce_critico = edited_df.loc[edited_df["Duracion Verde [s]"].idxmin(), "Cruce"]
    st.warning(f"💡 El ancho de banda sugerido es de **{verde_minimo}s**, limitado por el **Cruce {cruce_critico}**.")

if __name__ == "__main__":
    main()