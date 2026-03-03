import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math

st.set_page_config(page_title="Ingeniería de Tráfico: Onda Verde Pro 2026", layout="wide")


# -------------------------
# Utilidades circulares
# -------------------------
def modC(x, C):
    return float(x) % float(C)


def circular_distance(a, b, C):
    """Distancia mínima circular entre a,b en [0,C)."""
    C = float(C)
    d = abs((float(a) - float(b)) % C)
    return min(d, C - d)


def circular_interval(start, end, C):
    """
    Intervalo circular [start,end] en un círculo de periodo C, devuelto
    como lista de intervalos [s,e] dentro de [0,C), con s<=e.
    """
    C = float(C)
    start_m = float(start) % C
    end_m = float(end) % C
    # Si el tramo cubre >=C (caso extremo), todo el ciclo
    if (float(end) - float(start)) >= C:
        return [(0.0, C)]
    if start_m <= end_m:
        return [(start_m, end_m)]
    return [(start_m, C), (0.0, end_m)]


def union_intervals(intervals):
    if not intervals:
        return []
    intervals = [(float(s), float(e)) for s, e in intervals if e > s + 1e-9]
    if not intervals:
        return []
    intervals.sort()
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        ps, pe = merged[-1]
        if s <= pe + 1e-9:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def intersect_intervals(A, B):
    out = []
    for a1, a2 in A:
        for b1, b2 in B:
            s = max(a1, b1)
            e = min(a2, b2)
            if e > s + 1e-9:
                out.append((s, e))
    return union_intervals(out)


def integers_in_intervals(intervals, C):
    """
    Enteros en [0,C-1] que caen en cualquiera de los intervalos [s,e] (s<=e) en [0,C).
    """
    C = int(C)
    ints = set()
    for s, e in intervals:
        a = int(math.ceil(s - 1e-9))
        b = int(math.floor(e + 1e-9))
        for x in range(a, b + 1):
            ints.add(x % C)
    return sorted(ints)


# -------------------------
# Ventanas de verde y banda
# -------------------------
def green_windows(offset, verde, C):
    """Ventanas verdes en [0,C). Maneja wrap-around."""
    C = float(C)
    s = float(offset) % C
    d = float(verde)
    if d <= 0:
        return []
    if s + d <= C:
        return [(s, s + d)]
    return [(s, C), (0.0, (s + d) - C)]


def split_interval_modC(start, duration, C):
    """Intervalo [start, start+duration] mod C en 1 o 2 intervalos dentro [0,C)."""
    C = float(C)
    start = float(start) % C
    end_raw = start + float(duration)
    if end_raw <= C:
        return [(start, end_raw)]
    end = end_raw - C
    return [(start, C), (0.0, end)]


def interval_inside_green(b_start, b_end, windows):
    """
    Comprueba si [b_start,b_end] cabe dentro de alguna ventana verde.
    Devuelve ok, margen_izq, margen_der, detalle.
    """
    for gs, ge in windows:
        if b_start >= gs and b_end <= ge:
            return True, (b_start - gs), (ge - b_end), "OK"

    # Diagnóstico: mejor solape
    best = None
    best_overlap = -1.0
    for gs, ge in windows:
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


# -------------------------
# Validación por sentido
# -------------------------
def validate_direction(df, C, v_ms, t0, ancho, travel_times, label_prefix="", build_table=False):
    """
    Valida banda en ciclo base para un sentido:
      arrival = (t0 + travel[i]) mod C
      banda: [arrival, arrival+ancho] mod C
    """
    invalid_ids = set()
    rows = [] if build_table else None

    ok_count = 0
    slacks = []
    sum_slack = 0.0

    for idx, row in df.iterrows():
        cruce = row["ID"]
        t_arr = (float(t0) + float(travel_times[idx])) % float(C)
        band_intervals = split_interval_modC(t_arr, float(ancho), C)
        windows = green_windows(row["Offset"], row["Verde"], C)

        ok_all = True
        worst_detail = "OK"
        min_mi = None
        min_md = None
        cruce_slacks = []

        for bs, be in band_intervals:
            ok, mi, md, detail = interval_inside_green(bs, be, windows)
            min_mi = mi if (min_mi is None) else min(min_mi, mi)
            min_md = md if (min_md is None) else min(min_md, md)
            cruce_slacks.append(min(mi, md))
            if not ok:
                ok_all = False
                worst_detail = detail

        if ok_all:
            ok_count += 1
        else:
            invalid_ids.add(cruce)

        cruce_slack = min(cruce_slacks) if cruce_slacks else 0.0
        slacks.append(cruce_slack)
        sum_slack += cruce_slack

        if build_table:
            rows.append({
                "Cruce": cruce,
                f"{label_prefix}t_llegada [s] (mod C)": round(t_arr, 2),
                f"{label_prefix}Banda [s] (mod C)": " + ".join([f"[{round(a,2)}, {round(b,2)}]" for a, b in band_intervals]),
                "Verde (ventanas)": "; ".join([f"[{round(gs,2)}, {round(ge,2)}]" for gs, ge in windows]) if windows else "-",
                f"{label_prefix}OK": "✅" if ok_all else "❌",
                f"{label_prefix}Margen inicio [s]": round(min_mi if min_mi is not None else 0.0, 2),
                f"{label_prefix}Margen fin [s]": round(min_md if min_md is not None else 0.0, 2),
                f"{label_prefix}Holgura (min) [s]": round(cruce_slack, 2),
                f"{label_prefix}Detalle": worst_detail
            })

    all_ok = (ok_count == len(df))
    min_slack_global = min(slacks) if slacks else 0.0
    table_df = pd.DataFrame(rows) if build_table else None
    return ok_count, all_ok, float(min_slack_global), float(sum_slack), invalid_ids, table_df


# -------------------------
# Optimización bidireccional
# -------------------------
def feasible_offset_intervals_for_arrival(arrival, verde, w, C):
    """
    Para una banda de ancho w y verde=verde_i:
    offset debe cumplir: offset <= arrival y arrival+w <= offset+verde (todo mod C)
    => offset ∈ [arrival - (verde - w), arrival] mod C
    """
    if w > verde + 1e-9:
        return []
    left = float(arrival) - (float(verde) - float(w))
    right = float(arrival)
    return union_intervals(circular_interval(left, right, C))


def best_offset_choice(current_off, feasible_intervals, C, max_change=None):
    """
    Elige offset entero dentro de intervalos factibles minimizando cambio circular.
    Si max_change está definido, exige distancia <= max_change.
    """
    C_int = int(C)
    candidates = integers_in_intervals(feasible_intervals, C_int)
    if not candidates:
        return False, None, None

    best = None  # (cost, off)
    for off in candidates:
        cost = circular_distance(current_off, off, C_int)
        if max_change is not None and cost > float(max_change) + 1e-9:
            continue
        if best is None or cost < best[0]:
            best = (cost, off)

    if best is None:
        return False, None, None
    return True, int(best[1]), float(best[0])


def optimize_bidirectional(df, C, v_ms, verde_min, travel_fwd, travel_rev, max_delta=None):
    """
    Optimiza ancho común w (máximo) para dos sentidos simultáneamente.
    Variables:
      - w (común)
      - t_ini_dir, t_ini_inv
      - offsets (siempre se elige el más cercano al actual; si max_delta, restringe cambios)
    Estrategia:
      - probar w desde verde_min hacia abajo
      - para cada w, explorar t_ini_dir y t_ini_inv en [0..C-1]
      - por cada par, para cada cruce intersectar intervalos factibles (dir ∩ inv),
        escoger offset entero más cercano al actual (y <=max_delta si aplica)
      - elegir solución con menor coste total de cambios
    """
    C_int = int(C)
    current_offsets = [float(st.session_state.get(f"off_{i}", 0)) for i in range(len(df))]

    for w in range(int(verde_min), 0, -1):
        best_for_w = None  # (total_cost, tdir, tinv, offsets_int)

        for tdir in range(C_int):
            for tinv in range(C_int):
                offsets_int = []
                total_cost = 0.0
                feasible = True

                for i, row in df.iterrows():
                    verde = float(row["Verde"])

                    arr_dir = (float(tdir) + float(travel_fwd[i])) % float(C_int)
                    arr_inv = (float(tinv) + float(travel_rev[i])) % float(C_int)

                    feas_dir = feasible_offset_intervals_for_arrival(arr_dir, verde, w, C_int)
                    feas_inv = feasible_offset_intervals_for_arrival(arr_inv, verde, w, C_int)
                    feas_both = intersect_intervals(feas_dir, feas_inv)

                    if not feas_both:
                        feasible = False
                        break

                    ok, off_best, cost = best_offset_choice(
                        current_off=current_offsets[i],
                        feasible_intervals=feas_both,
                        C=C_int,
                        max_change=max_delta
                    )
                    if not ok:
                        feasible = False
                        break

                    offsets_int.append(off_best)
                    total_cost += cost

                if not feasible:
                    continue

                cand = (total_cost, tdir, tinv, offsets_int)
                if best_for_w is None or cand[0] < best_for_w[0]:
                    best_for_w = cand

        if best_for_w is not None:
            total_cost, tdir, tinv, offsets_int = best_for_w
            return {
                "w": int(w),
                "t_ini_dir": int(tdir),
                "t_ini_inv": int(tinv),
                "offsets": offsets_int,
                "cost": float(total_cost),
                "max_delta": max_delta
            }

    return None


# =========================
# APP
# =========================
def main():
    # --- ESTADO DE SESIÓN ---
    if "num_cruces" not in st.session_state:
        st.session_state.num_cruces = 4

    # Defaults de claves nuevas (para no romper)
    if "t_ini_inv" not in st.session_state:
        st.session_state.t_ini_inv = 0
    if "ancho_inv" not in st.session_state:
        st.session_state.ancho_inv = 10
    if "ancho" not in st.session_state:
        st.session_state.ancho = 10

    st.title("🚦 Diseño Profesional de Onda Verde (Bidireccional)")
    st.markdown("""
    Diagrama de coordinación (tiempo–distancia) con **banda directa e inversa**.  
    Puedes validar cada sentido y optimizar una **banda común máxima** ajustando `t_ini` y offsets.
    """)

    # --- SIDEBAR: PARAMS ---
    st.sidebar.header("⚙️ Parámetros de Diseño")
    C = st.sidebar.number_input("Ciclo Total (C) [s]", value=90, min_value=30)
    v_kmh = st.sidebar.slider("Velocidad de Diseño (km/h)", 20, 80, 50)
    v_ms = v_kmh / 3.6
    num_ciclos = st.sidebar.slider("Ciclos en Gráfico", 1, 4, 2)

    st.sidebar.divider()
    st.sidebar.subheader("🧭 Sentidos")
    bidir = st.sidebar.toggle("Mostrar banda inversa (bidireccional)", value=True)
    usar_ancho_comun = st.sidebar.toggle("Usar ancho común en ambos sentidos", value=True) if bidir else False

    st.sidebar.divider()
    st.sidebar.subheader("✅ Validación")
    validar = st.sidebar.toggle("Activar validación automática", value=True)
    marcar_invalidos = st.sidebar.toggle("Marcar cruces no válidos en el gráfico", value=True)

    # --- CRUCES ---
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
            off = st.slider("Offset", 0, int(C), key=f"off_{i}")
            ver = st.slider("Verde", 5, int(C), key=f"ver_{i}", value=45)
            dist = 0 if i == 0 else st.number_input(
                f"Dist. {chr(65 + i - 1)}-{name}",
                50, 1500, 400, key=f"dist_{i}"
            )
            config.append({"ID": name, "Offset": off, "Verde": ver, "Dist": dist})

    df = pd.DataFrame(config)
    df["Dist_Acum"] = df["Dist"].cumsum()
    verde_min = int(df["Verde"].min())
    dist_total = float(df["Dist_Acum"].iloc[-1])

    # --- TIEMPOS DE VIAJE POR SENTIDO ---
    travel_fwd = [float(d) / v_ms for d in df["Dist_Acum"].tolist()]
    travel_rev = [(dist_total - float(d)) / v_ms for d in df["Dist_Acum"].tolist()]

    # --- SLIDERS DE BANDA ---
    st.sidebar.divider()
    st.sidebar.subheader("📏 Banda directa (A → …)")
    st.sidebar.slider("Inicio Banda directa (Cruce A)", 0, int(C), key="t_ini")

    if bidir:
        st.sidebar.subheader("📏 Banda inversa (… → A)")
        st.sidebar.slider("Inicio Banda inversa (Último cruce)", 0, int(C), key="t_ini_inv")

    if usar_ancho_comun:
        st.sidebar.slider("Ancho común [s]", 1, int(verde_min), min(int(verde_min), int(st.session_state.ancho)), key="ancho_comun")
        # Sincronizamos ambos anchos
        st.session_state.ancho = int(st.session_state.ancho_comun)
        st.session_state.ancho_inv = int(st.session_state.ancho_comun)
    else:
        st.sidebar.slider("Ancho directa [s]", 1, int(verde_min), min(int(verde_min), int(st.session_state.ancho)), key="ancho")
        if bidir:
            st.sidebar.slider("Ancho inversa [s]", 1, int(verde_min), min(int(verde_min), int(st.session_state.ancho_inv)), key="ancho_inv")

    # --- BOTÓN: ALINEAR OFFSETS A BANDA DIRECTA (mantener funcionalidad previa) ---
    def alinear_offsets_al_inicio_directa():
        base_t = st.session_state.t_ini
        for i, row in df.iterrows():
            t_viaje = float(row["Dist_Acum"]) / v_ms
            st.session_state[f"off_{i}"] = int((base_t + t_viaje) % float(C))
        st.rerun()

    st.button("🎯 Alinear Offsets al Inicio de Banda (Directa)", on_click=alinear_offsets_al_inicio_directa)

    # --- OPTIMIZACIÓN BIDIRECCIONAL ---
    if bidir:
        st.sidebar.divider()
        st.sidebar.subheader("📈 Optimización bidireccional (banda común máxima)")
        restringir = st.sidebar.toggle("Restringir cambios de offset", value=True)
        max_delta = st.sidebar.slider("Cambio máximo por cruce [s]", 0, int(C // 2), 15) if restringir else None

        def aplicar_opt_bidireccional():
            sol = optimize_bidirectional(df, C, v_ms, verde_min, travel_fwd, travel_rev, max_delta=max_delta)
            if sol is None:
                st.session_state["opt_bidir_info"] = {
                    "ok": False,
                    "msg": "No se encontró solución (ni con ancho=1) bajo las restricciones actuales."
                }
                st.rerun()

            # Aplicar
            w = int(sol["w"])
            st.session_state["t_ini"] = int(sol["t_ini_dir"])
            st.session_state["t_ini_inv"] = int(sol["t_ini_inv"])
            st.session_state["ancho"] = w
            st.session_state["ancho_inv"] = w
            if "ancho_comun" in st.session_state:
                st.session_state["ancho_comun"] = w

            for i, off in enumerate(sol["offsets"]):
                st.session_state[f"off_{i}"] = int(off)

            st.session_state["opt_bidir_info"] = {
                "ok": True,
                "ancho": w,
                "t_ini_dir": int(sol["t_ini_dir"]),
                "t_ini_inv": int(sol["t_ini_inv"]),
                "cost": float(sol["cost"]),
                "max_delta": sol["max_delta"]
            }
            st.rerun()

        st.sidebar.button("📈 Aplicar banda común máxima (2 sentidos)", on_click=aplicar_opt_bidireccional)

        if "opt_bidir_info" in st.session_state:
            info = st.session_state["opt_bidir_info"]
            if info.get("ok", False):
                extra = f" | Δmax={info['max_delta']} s" if info.get("max_delta") is not None else ""
                st.sidebar.success(
                    f"Banda común={info['ancho']} s | t_dir={info['t_ini_dir']} | t_inv={info['t_ini_inv']} "
                    f"| coste cambio={info['cost']:.1f}{extra}"
                )
            else:
                st.sidebar.error(info.get("msg", "Optimización bidireccional no factible."))

    # --- VALIDACIÓN ---
    invalid_dir = set()
    invalid_inv = set()
    val_df_dir = None
    val_df_inv = None

    if validar:
        ok_d, all_ok_d, min_slack_d, sum_slack_d, invalid_dir, val_df_dir = validate_direction(
            df=df, C=C, v_ms=v_ms,
            t0=st.session_state.t_ini, ancho=st.session_state.ancho,
            travel_times=travel_fwd,
            label_prefix="DIR_",
            build_table=True
        )

        if bidir:
            ok_i, all_ok_i, min_slack_i, sum_slack_i, invalid_inv, val_df_inv = validate_direction(
                df=df, C=C, v_ms=v_ms,
                t0=st.session_state.t_ini_inv, ancho=st.session_state.ancho_inv,
                travel_times=travel_rev,
                label_prefix="INV_",
                build_table=True
            )
        else:
            ok_i, all_ok_i, min_slack_i, sum_slack_i = None, None, None, None

        st.sidebar.divider()
        st.sidebar.subheader("📋 Estado (ciclo base)")
        st.sidebar.markdown(f"**Directa OK:** {ok_d}/{len(df)}")
        st.sidebar.caption(f"Holgura mínima: {min_slack_d:.2f} s | Total: {sum_slack_d:.2f} s")
        if all_ok_d:
            st.sidebar.success("Directa válida en todos los cruces.")
        else:
            st.sidebar.error("Directa: hay cruces fuera de verde.")

        if bidir:
            st.sidebar.markdown(f"**Inversa OK:** {ok_i}/{len(df)}")
            st.sidebar.caption(f"Holgura mínima: {min_slack_i:.2f} s | Total: {sum_slack_i:.2f} s")
            if all_ok_i:
                st.sidebar.success("Inversa válida en todos los cruces.")
            else:
                st.sidebar.error("Inversa: hay cruces fuera de verde.")

    # --- GRÁFICO ---
    fig = go.Figure()

    # Señalización (rojo/verde)
    for _, row in df.iterrows():
        x = row["Dist_Acum"]
        for k in range(num_ciclos):
            t_base = k * C
            fig.add_trace(go.Scatter(
                x=[x, x], y=[t_base, t_base + C],
                mode="lines",
                line=dict(color="#E74C3C", width=25),
                showlegend=False
            ))

            s = float(row["Offset"])
            d = float(row["Verde"])

            def draw_v(sta, end):
                fig.add_trace(go.Scatter(
                    x=[x, x], y=[t_base + sta, t_base + end],
                    mode="lines",
                    line=dict(color="#2ECC71", width=25),
                    showlegend=False
                ))

            if s + d <= C:
                draw_v(s, s + d)
            else:
                draw_v(s, float(C))
                draw_v(0.0, (s + d) - float(C))

    # Banda directa (azul)
    for k in range(num_ciclos):
        t0 = k * C + st.session_state.t_ini
        x_pts = df["Dist_Acum"].tolist()
        y_inf = [t0 + travel_fwd[i] for i in range(len(x_pts))]
        y_sup = [t + st.session_state.ancho for t in y_inf]
        fig.add_trace(go.Scatter(
            x=x_pts + x_pts[::-1],
            y=y_inf + y_sup[::-1],
            fill="toself",
            fillcolor="rgba(52, 152, 219, 0.25)",
            line=dict(color="rgba(41, 128, 185, 0.9)", width=2),
            name="Banda directa" if k == 0 else "",
            hoverinfo="skip"
        ))

    # Banda inversa (naranja)
    if bidir:
        for k in range(num_ciclos):
            t0 = k * C + st.session_state.t_ini_inv
            x_pts = df["Dist_Acum"].tolist()
            y_inf = [t0 + travel_rev[i] for i in range(len(x_pts))]
            y_sup = [t + st.session_state.ancho_inv for t in y_inf]
            fig.add_trace(go.Scatter(
                x=x_pts + x_pts[::-1],
                y=y_inf + y_sup[::-1],
                fill="toself",
                fillcolor="rgba(243, 156, 18, 0.20)",
                line=dict(color="rgba(211, 84, 0, 0.95)", width=2),
                name="Banda inversa" if k == 0 else "",
                hoverinfo="skip"
            ))

    # Marcas de inválidos (ciclo base)
    if validar and marcar_invalidos:
        # Directa: X morada
        if invalid_dir:
            xs, ys, texts = [], [], []
            for i, row in df.iterrows():
                cruce = row["ID"]
                if cruce in invalid_dir:
                    xs.append(float(row["Dist_Acum"]))
                    ys.append((float(st.session_state.t_ini) + travel_fwd[i]) % float(C))
                    texts.append(f"{cruce} D ❌")
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode="markers+text",
                marker=dict(size=12, color="#8E44AD", symbol="x"),
                text=texts, textposition="top center",
                name="Inválidos directa (base)"
            ))

        # Inversa: triángulo rojo
        if bidir and invalid_inv:
            xs, ys, texts = [], [], []
            for i, row in df.iterrows():
                cruce = row["ID"]
                if cruce in invalid_inv:
                    xs.append(float(row["Dist_Acum"]))
                    ys.append((float(st.session_state.t_ini_inv) + travel_rev[i]) % float(C))
                    texts.append(f"{cruce} I ❌")
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode="markers+text",
                marker=dict(size=12, color="#C0392B", symbol="triangle-up"),
                text=texts, textposition="bottom center",
                name="Inválidos inversa (base)"
            ))

    fig.update_layout(
        xaxis_title="Distancia [m]",
        yaxis_title="Tiempo [s]",
        xaxis=dict(tickvals=df["Dist_Acum"], ticktext=df["ID"], gridcolor="#f0f0f0"),
        yaxis=dict(range=[0, num_ciclos * C], gridcolor="#f0f0f0"),
        plot_bgcolor="white",
        height=750
    )

    # Streamlit 2026: width='stretch'
    st.plotly_chart(fig, width="stretch")

    # --- TABLAS VALIDACIÓN ---
    if validar and val_df_dir is not None:
        st.subheader("✅ Validación banda directa (ciclo base)")
        st.dataframe(val_df_dir, width="stretch", hide_index=True)

    if validar and bidir and val_df_inv is not None:
        st.subheader("✅ Validación banda inversa (ciclo base)")
        st.dataframe(val_df_inv, width="stretch", hide_index=True)

    # --- MÉTRICAS ---
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Velocidad de Diseño", f"{v_kmh} km/h")
    m2.metric("Ancho Directa", f"{int(st.session_state.ancho)} s")
    m3.metric("Ancho Inversa", f"{int(st.session_state.ancho_inv) if bidir else 0} s")
    m4.metric("Eficiencia (Directa)", f"{(float(st.session_state.ancho) / float(C)) * 100:.1f}%")


if __name__ == "__main__":
    main()