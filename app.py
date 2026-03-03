import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Ingeniería de Tráfico: Onda Verde Pro 2026", layout="wide")


def main():
    st.title("🚦 Diseño Profesional de Onda Verde")
    st.markdown("""
    Diagrama técnico de **bandas paralelas rígidas**.  
    Incluye **validación automática** de la banda de progresión (A→...).  
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

    st.sidebar.divider()
    st.sidebar.subheader("✅ Validación")
    validar = st.sidebar.toggle("Activar validación automática", value=True)
    marcar_invalidos = st.sidebar.toggle("Marcar cruces no válidos en el gráfico", value=True)

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
            off = st.slider("Offset", 0, int(c_total), key=f"off_{i}")
            ver = st.slider("Verde", 5, int(c_total), key=f"ver_{i}", value=45)
            dist = 0 if i == 0 else st.number_input(
                f"Dist. {chr(65 + i - 1)}-{name}",
                50, 1500, 400, key=f"dist_{i}"
            )
            config.append({"ID": name, "Offset": off, "Verde": ver, "Dist": dist})

    # --- CÁLCULO DE BANDA ---
    df = pd.DataFrame(config)
    df['Dist_Acum'] = df['Dist'].cumsum()
    verde_min = int(df['Verde'].min())

    st.sidebar.divider()
    t_ini = st.sidebar.slider("Inicio Banda (Cruce A)", 0, int(c_total), key="t_ini")
    ancho = st.sidebar.slider("Ancho de Banda [s]", 1, int(verde_min), int(verde_min))

    # --- FUNCIÓN DE "OPTIMIZACIÓN" (alineación offsets) ---
    def optimizar():
        base_t = st.session_state.t_ini
        for i, row in df.iterrows():
            t_viaje = row['Dist_Acum'] / v_ms
            st.session_state[f"off_{i}"] = int((base_t + t_viaje) % c_total)

    st.button("🎯 Alinear Offsets al Inicio de Banda", on_click=optimizar)

    # -------------------------
    # VALIDACIÓN DE LA BANDA
    # -------------------------
    def green_windows(offset, verde, C):
        """
        Devuelve lista de intervalos [start, end] (en segundos dentro del ciclo [0,C))
        donde el verde está activo.
        Maneja wrap-around si offset+verde > C.
        """
        s = float(offset)
        d = float(verde)
        if d <= 0:
            return []
        if s + d <= C:
            return [(s, s + d)]
        else:
            # Verde parte al final y continúa al inicio
            return [(s, float(C)), (0.0, (s + d) - float(C))]

    def interval_inside_green(b_start, b_end, windows):
        """
        Comprueba si el intervalo [b_start, b_end] está completamente contenido
        dentro de alguno de los intervalos verdes (windows).
        Devuelve:
          ok (bool),
          margen_izq (s),
          margen_der (s),
          detalle (str)
        margen_izq: cuánto sobra desde el inicio del verde hasta b_start (>=0 si ok)
        margen_der: cuánto sobra desde b_end hasta fin del verde (>=0 si ok)
        """
        for (gs, ge) in windows:
            if b_start >= gs and b_end <= ge:
                return True, (b_start - gs), (ge - b_end), "OK"

        # Si no cabe en ninguno, intentamos diagnosticar con el "mejor" intervalo:
        # elegimos el que maximiza el solape con [b_start, b_end]
        best = None
        best_overlap = -1.0
        for (gs, ge) in windows:
            overlap = max(0.0, min(b_end, ge) - max(b_start, gs))
            if overlap > best_overlap:
                best_overlap = overlap
                best = (gs, ge)

        if best is None:
            return False, 0.0, 0.0, "Sin verde definido"

        gs, ge = best
        # Caso 1: banda empieza antes del verde
        if b_start < gs and b_end <= ge:
            return False, (b_start - gs), (ge - b_end), "Empieza antes del verde"
        # Caso 2: banda termina después del verde
        if b_start >= gs and b_end > ge:
            return False, (b_start - gs), (ge - b_end), "Termina después del verde"
        # Caso 3: banda más larga que la ventana o queda "partida" respecto a ventanas
        return False, (b_start - gs), (ge - b_end), "No cabe en ninguna ventana verde"

    validation_df = None
    invalid_ids = set()

    if validar:
        # Validamos en el ciclo base (k=0): tiempos relativos al ciclo [0, C)
        # Banda en cada cruce: [t_arrival, t_arrival + ancho] mod C
        rows = []
        for _, row in df.iterrows():
            cruce = row["ID"]
            x = float(row["Dist_Acum"])
            t_arr = (float(t_ini) + (x / v_ms)) % float(c_total)
            t_dep = (t_arr + float(ancho)) % float(c_total)

            # Si la banda cruza el final de ciclo, se divide en dos intervalos
            if t_arr + float(ancho) <= float(c_total):
                band_intervals = [(t_arr, t_arr + float(ancho))]
            else:
                band_intervals = [(t_arr, float(c_total)), (0.0, t_dep)]

            windows = green_windows(row["Offset"], row["Verde"], float(c_total))

            # La banda es válida si TODOS los sub-intervalos están dentro de ALGUNA ventana
            ok_all = True
            worst_detail = "OK"
            # márgenes: para informar, tomamos el mínimo margen izq/der entre sub-intervalos válidos
            # si falla, guardamos el peor caso (primer fallo)
            min_mi = None
            min_md = None

            for (bs, be) in band_intervals:
                ok, mi, md, detail = interval_inside_green(bs, be, windows)
                if ok:
                    min_mi = mi if (min_mi is None) else min(min_mi, mi)
                    min_md = md if (min_md is None) else min(min_md, md)
                else:
                    ok_all = False
                    worst_detail = detail
                    # en fallo, guardamos los "márgenes" tal cual (pueden ser negativos)
                    min_mi = mi if (min_mi is None) else min(min_mi, mi)
                    min_md = md if (min_md is None) else min(min_md, md)

            if not ok_all:
                invalid_ids.add(cruce)

            rows.append({
                "Cruce": cruce,
                "t_llegada [s] (mod C)": round(t_arr, 2),
                "Banda [s] (mod C)": f"[{round(band_intervals[0][0],2)}, {round(band_intervals[0][1],2)}]" + (
                    f" + [{round(band_intervals[1][0],2)}, {round(band_intervals[1][1],2)}]" if len(band_intervals) == 2 else ""
                ),
                "Verde (ventanas)": "; ".join([f"[{round(gs,2)}, {round(ge,2)}]" for gs, ge in windows]) if windows else "-",
                "OK": "✅" if ok_all else "❌",
                "Margen inicio [s]": round(min_mi if min_mi is not None else 0.0, 2),
                "Margen fin [s]": round(min_md if min_md is not None else 0.0, 2),
                "Detalle": worst_detail
            })

        validation_df = pd.DataFrame(rows)

        ok_count = (validation_df["OK"] == "✅").sum()
        st.sidebar.markdown(f"**Cruces OK:** {ok_count}/{len(validation_df)}")
        if ok_count != len(validation_df):
            st.sidebar.error("Hay cruces fuera de verde para la banda actual.")
        else:
            st.sidebar.success("Banda válida en todos los cruces (ciclo base).")

    # --- GRÁFICO PROFESIONAL ---
    fig = go.Figure()

    # Dibujo rojo/verde por cruce y por ciclo
    for _, row in df.iterrows():
        x = row['Dist_Acum']
        for k in range(num_ciclos):
            t_base = k * c_total

            # Rojo (fondo)
            fig.add_trace(go.Scatter(
                x=[x, x], y=[t_base, t_base + c_total],
                mode='lines',
                line=dict(color='#E74C3C', width=25),
                showlegend=False
            ))

            # Verde
            s, d = float(row['Offset']), float(row['Verde'])

            def draw_v(start, end):
                fig.add_trace(go.Scatter(
                    x=[x, x], y=[t_base + start, t_base + end],
                    mode='lines',
                    line=dict(color='#2ECC71', width=25),
                    showlegend=False
                ))

            if s + d <= c_total:
                draw_v(s, s + d)
            else:
                draw_v(s, c_total)
                draw_v(0.0, (s + d) - c_total)

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
            name="Banda de Progresión" if k == 0 else "",
            hoverinfo="skip"
        ))

    # Marcado visual de cruces inválidos (si procede)
    if validar and marcar_invalidos and validation_df is not None and len(invalid_ids) > 0:
        # Marcamos en el ciclo 0 el punto medio de la banda en cada cruce inválido
        xs = []
        ys = []
        texts = []
        for _, row in df.iterrows():
            cruce = row["ID"]
            if cruce in invalid_ids:
                x = float(row["Dist_Acum"])
                t_arr = (float(t_ini) + (x / v_ms)) % float(c_total)
                y = t_arr  # ciclo base
                xs.append(x)
                ys.append(y)
                texts.append(f"{cruce} ❌")

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            marker=dict(size=12, color="#8E44AD", symbol="x"),
            text=texts,
            textposition="top center",
            name="Cruces fuera de banda (ciclo base)"
        ))

    fig.update_layout(
        xaxis_title="Distancia [m]",
        yaxis_title="Tiempo [s]",
        xaxis=dict(
            tickvals=df['Dist_Acum'],
            ticktext=df['ID'],
            gridcolor='#f0f0f0'
        ),
        yaxis=dict(
            range=[0, num_ciclos * c_total],
            gridcolor='#f0f0f0'
        ),
        plot_bgcolor='white',
        height=750
    )

    # FIX 2026: Reemplazo de use_container_width por width='stretch'
    st.plotly_chart(fig, width='stretch')

    # --- PANEL DE VALIDACIÓN (TABLA) ---
    if validar and validation_df is not None:
        st.subheader("✅ Validación automática de la banda (ciclo base)")
        st.caption("""
        Comprueba si la banda de progresión (A→...) en el **ciclo base** queda totalmente dentro de verde en cada cruce.
        *Margen inicio* y *Margen fin* indican holgura (en segundos) respecto a la ventana verde que contiene (o la más cercana).
        """)
        st.dataframe(
            validation_df,
            use_container_width=True,
            hide_index=True
        )

    # --- MÉTRICAS ---
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Velocidad de Diseño", f"{v_kmh} km/h")
    m2.metric("Ancho de Banda", f"{ancho} s")
    m3.metric("Eficiencia", f"{(ancho / c_total) * 100:.1f}%")

    # Consejo rápido cuando no es válida
    if validar and validation_df is not None and len(invalid_ids) > 0:
        st.warning(
            "La banda no es válida en todos los cruces. "
            "Prueba a: (1) ajustar t_ini, (2) pulsar 'Alinear Offsets', "
            "o (3) reducir el ancho de banda."
        )


if __name__ == "__main__":
    main()