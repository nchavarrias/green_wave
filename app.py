import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Ingeniería de Tráfico: Onda Verde Pro 2026", layout="wide")


def main():
    st.title("🚦 Diseño Profesional de Onda Verde")
    st.markdown("""
    Diagrama técnico de **bandas paralelas rígidas**.  
    Incluye **validación automática** y **auto-ajuste de `t_ini`** (A→...).  
    Optimizado para la versión de Streamlit 2026.
    """)

    # --- ESTADO DE SESIÓN ---
    if "num_cruces" not in st.session_state:
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
    df["Dist_Acum"] = df["Dist"].cumsum()
    verde_min = int(df["Verde"].min())

    st.sidebar.divider()
    t_ini = st.sidebar.slider("Inicio Banda (Cruce A)", 0, int(c_total), key="t_ini")
    ancho = st.sidebar.slider("Ancho de Banda [s]", 1, int(verde_min), int(verde_min))

    # --- FUNCIÓN DE "OPTIMIZACIÓN" (alineación offsets) ---
    def optimizar_offsets():
        base_t = st.session_state.t_ini
        for i, row in df.iterrows():
            t_viaje = row["Dist_Acum"] / v_ms
            st.session_state[f"off_{i}"] = int((base_t + t_viaje) % c_total)

    st.button("🎯 Alinear Offsets al Inicio de Banda", on_click=optimizar_offsets)

    # -------------------------
    # UTILIDADES DE VALIDACIÓN
    # -------------------------
    def green_windows(offset, verde, C):
        """
        Devuelve lista de intervalos (start, end) en [0,C)
        donde el verde está activo. Maneja wrap-around.
        """
        s = float(offset)
        d = float(verde)
        if d <= 0:
            return []
        if s + d <= C:
            return [(s, s + d)]
        return [(s, float(C)), (0.0, (s + d) - float(C))]

    def split_interval_modC(start, duration, C):
        """
        Intervalo [start, start+duration] mod C.
        Devuelve 1 o 2 intervalos dentro de [0,C).
        """
        start = float(start) % float(C)
        end_raw = start + float(duration)
        if end_raw <= float(C):
            return [(start, end_raw)]
        end = end_raw - float(C)
        return [(start, float(C)), (0.0, end)]

    def interval_inside_green(b_start, b_end, windows):
        """
        Comprueba si [b_start,b_end] cabe dentro de alguna ventana verde.
        Si cabe: (ok=True, margen_izq>=0, margen_der>=0, "OK")
        Si no:  (ok=False, márgenes (pueden ser negativos), detalle)
        """
        for (gs, ge) in windows:
            if b_start >= gs and b_end <= ge:
                return True, (b_start - gs), (ge - b_end), "OK"

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
        if b_start < gs and b_end <= ge:
            return False, (b_start - gs), (ge - b_end), "Empieza antes del verde"
        if b_start >= gs and b_end > ge:
            return False, (b_start - gs), (ge - b_end), "Termina después del verde"
        return False, (b_start - gs), (ge - b_end), "No cabe en ninguna ventana verde"

    def validate_at_tini(tini_value, build_table=False):
        """
        Valida la banda en ciclo base para un tini_value.
        Devuelve:
          ok_count, all_ok, min_slack_global, sum_slack, invalid_ids, (optional) table_df
        """
        invalid_ids = set()
        rows = [] if build_table else None

        ok_count = 0
        slacks = []     # slack por cruce (el mínimo de sus márgenes)
        sum_slack = 0.0

        C = float(c_total)

        for _, row in df.iterrows():
            cruce = row["ID"]
            x = float(row["Dist_Acum"])
            t_arr = (float(tini_value) + (x / v_ms)) % C
            band_intervals = split_interval_modC(t_arr, float(ancho), C)

            windows = green_windows(row["Offset"], row["Verde"], C)

            ok_all = True
            worst_detail = "OK"

            # holguras por cruce: nos quedamos con el mínimo margen (más restrictivo)
            cruce_slacks = []

            # para tabla: guardamos márgenes "representativos"
            min_mi = None
            min_md = None

            for (bs, be) in band_intervals:
                ok, mi, md, detail = interval_inside_green(bs, be, windows)

                # Para diagnóstico/tabla
                min_mi = mi if (min_mi is None) else min(min_mi, mi)
                min_md = md if (min_md is None) else min(min_md, md)

                if ok:
                    cruce_slacks.append(min(mi, md))
                else:
                    ok_all = False
                    worst_detail = detail
                    # En fallo también metemos "slack" para puntuar (puede ser negativo)
                    cruce_slacks.append(min(mi, md))

            if ok_all:
                ok_count += 1
            else:
                invalid_ids.add(cruce)

            # slack del cruce: mínimo de los intervalos (si hay 2 por wrap)
            cruce_slack = min(cruce_slacks) if cruce_slacks else 0.0
            slacks.append(cruce_slack)
            sum_slack += cruce_slack

            if build_table:
                rows.append({
                    "Cruce": cruce,
                    "t_llegada [s] (mod C)": round(t_arr, 2),
                    "Banda [s] (mod C)": " + ".join([f"[{round(a,2)}, {round(b,2)}]" for a, b in band_intervals]),
                    "Verde (ventanas)": "; ".join([f"[{round(gs,2)}, {round(ge,2)}]" for gs, ge in windows]) if windows else "-",
                    "OK": "✅" if ok_all else "❌",
                    "Margen inicio [s]": round(min_mi if min_mi is not None else 0.0, 2),
                    "Margen fin [s]": round(min_md if min_md is not None else 0.0, 2),
                    "Holgura (min) [s]": round(cruce_slack, 2),
                    "Detalle": worst_detail
                })

        all_ok = (ok_count == len(df))
        min_slack_global = min(slacks) if slacks else 0.0

        table_df = pd.DataFrame(rows) if build_table else None
        return ok_count, all_ok, float(min_slack_global), float(sum_slack), invalid_ids, table_df

    # -------------------------
    # AUTO-AJUSTE DE t_ini
    # -------------------------
    st.sidebar.divider()
    st.sidebar.subheader("🛠️ Auto-ajuste de t_ini")

    def auto_ajustar_tini():
        C = int(c_total)
        best = None
        # best = (ok_count, all_ok, min_slack_global, sum_slack, tini)
        for tini_candidate in range(C):
            ok_count, all_ok, min_slack, sum_slack, _, _ = validate_at_tini(tini_candidate, build_table=False)
            candidate = (ok_count, all_ok, min_slack, sum_slack, tini_candidate)

            if best is None:
                best = candidate
                continue

            # Orden de decisión:
            # 1) más cruces OK
            # 2) preferir all_ok si empatan ok_count (redundante, pero explícito)
            # 3) mayor holgura mínima global
            # 4) mayor suma de holguras
            if candidate[0] > best[0]:
                best = candidate
            elif candidate[0] == best[0]:
                if candidate[1] and not best[1]:
                    best = candidate
                elif candidate[1] == best[1]:
                    if candidate[2] > best[2]:
                        best = candidate
                    elif candidate[2] == best[2]:
                        if candidate[3] > best[3]:
                            best = candidate

        if best is not None:
            _, all_ok, min_slack, _, tini_best = best
            st.session_state["t_ini"] = int(tini_best)
            st.session_state["auto_tini_info"] = {
                "t_ini": int(tini_best),
                "all_ok": bool(all_ok),
                "min_slack": float(min_slack)
            }
            st.rerun()

    st.sidebar.button("🛠️ Auto-ajustar t_ini (máxima validez)", on_click=auto_ajustar_tini)

    # Mostrar info del último auto-ajuste (si existe)
    if "auto_tini_info" in st.session_state:
        info = st.session_state["auto_tini_info"]
        if info.get("all_ok", False):
            st.sidebar.success(f"t_ini ajustado a {info['t_ini']} s (banda válida).")
        else:
            st.sidebar.warning(f"t_ini ajustado a {info['t_ini']} s (mejor posible, no válida en todos).")
        st.sidebar.caption(f"Holgura mínima (global): {info.get('min_slack', 0.0):.2f} s")

    # -------------------------
    # VALIDACIÓN ACTUAL (tabla + marcados)
    # -------------------------
    validation_df = None
    invalid_ids = set()

    if validar:
        ok_count, all_ok, _, _, invalid_ids, validation_df = validate_at_tini(t_ini, build_table=True)

        st.sidebar.markdown(f"**Cruces OK:** {ok_count}/{len(df)}")
        if not all_ok:
            st.sidebar.error("Hay cruces fuera de verde para la banda actual.")
        else:
            st.sidebar.success("Banda válida en todos los cruces (ciclo base).")

    # --- GRÁFICO PROFESIONAL ---
    fig = go.Figure()

    # Dibujo rojo/verde por cruce y por ciclo
    for _, row in df.iterrows():
        x = row["Dist_Acum"]
        for k in range(num_ciclos):
            t_base = k * c_total

            # Rojo (fondo)
            fig.add_trace(go.Scatter(
                x=[x, x], y=[t_base, t_base + c_total],
                mode="lines",
                line=dict(color="#E74C3C", width=25),
                showlegend=False
            ))

            # Verde (con wrap)
            s, d = float(row["Offset"]), float(row["Verde"])

            def draw_v(start, end):
                fig.add_trace(go.Scatter(
                    x=[x, x], y=[t_base + start, t_base + end],
                    mode="lines",
                    line=dict(color="#2ECC71", width=25),
                    showlegend=False
                ))

            if s + d <= c_total:
                draw_v(s, s + d)
            else:
                draw_v(s, float(c_total))
                draw_v(0.0, (s + d) - float(c_total))

    # Dibujar Banda de Progresión
    for k in range(num_ciclos):
        t0 = k * c_total + t_ini
        x_pts = df["Dist_Acum"].tolist()
        y_inf = [t0 + (d / v_ms) for d in x_pts]
        y_sup = [t + ancho for t in y_inf]

        fig.add_trace(go.Scatter(
            x=x_pts + x_pts[::-1],
            y=y_inf + y_sup[::-1],
            fill="toself",
            fillcolor="rgba(52, 152, 219, 0.3)",
            line=dict(color="rgba(41, 128, 185, 0.8)", width=2),
            name="Banda de Progresión" if k == 0 else "",
            hoverinfo="skip"
        ))

    # Marcado visual de cruces inválidos (ciclo base)
    if validar and marcar_invalidos and validation_df is not None and len(invalid_ids) > 0:
        xs, ys, texts = [], [], []
        C = float(c_total)
        for _, row in df.iterrows():
            cruce = row["ID"]
            if cruce in invalid_ids:
                x = float(row["Dist_Acum"])
                t_arr = (float(t_ini) + (x / v_ms)) % C
                xs.append(x)
                ys.append(t_arr)
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
        xaxis=dict(tickvals=df["Dist_Acum"], ticktext=df["ID"], gridcolor="#f0f0f0"),
        yaxis=dict(range=[0, num_ciclos * c_total], gridcolor="#f0f0f0"),
        plot_bgcolor="white",
        height=750
    )

    # ✅ Corrección: nada de use_container_width
    st.plotly_chart(fig, width="stretch")

    # --- PANEL DE VALIDACIÓN (TABLA) ---
    if validar and validation_df is not None:
        st.subheader("✅ Validación automática de la banda (ciclo base)")
        st.caption("""
        Comprueba si la banda de progresión (A→...) en el **ciclo base** queda totalmente dentro de verde en cada cruce.  
        *Holgura (min)* es el margen más restrictivo (el que manda) por cruce.
        """)
        # ✅ Corrección: use_container_width=True -> width="stretch"
        st.dataframe(validation_df, width="stretch", hide_index=True)

    # --- MÉTRICAS ---
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Velocidad de Diseño", f"{v_kmh} km/h")
    m2.metric("Ancho de Banda", f"{ancho} s")
    m3.metric("Eficiencia", f"{(ancho / c_total) * 100:.1f}%")

    if validar and validation_df is not None and len(invalid_ids) > 0:
        st.warning(
            "La banda no es válida en todos los cruces. "
            "Prueba a: (1) Auto-ajustar t_ini, (2) ajustar manualmente t_ini, "
            "(3) pulsar 'Alinear Offsets', o (4) reducir el ancho de banda."
        )


if __name__ == "__main__":
    main()