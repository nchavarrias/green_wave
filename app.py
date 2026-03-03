import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math

st.set_page_config(page_title="Ingeniería de Tráfico: Onda Verde Pro 2026", layout="wide")


def main():
    st.title("🚦 Diseño Profesional de Onda Verde")
    st.markdown("""
    Diagrama técnico de **bandas paralelas rígidas** (tiempo–distancia).  
    Incluye:
    - **Validación automática** de banda (ciclo base)
    - **Auto-ajuste de `t_ini`**
    - **Optimización real**: búsqueda automática de **banda máxima** (ancho máximo) ajustando `t_ini` y/o offsets  
    Optimizado para Streamlit 2026.
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

    # --- DATAFRAME ---
    df = pd.DataFrame(config)
    df["Dist_Acum"] = df["Dist"].cumsum()
    verde_min = int(df["Verde"].min())

    # --- SLIDERS BANDA (con key para poder actualizarlos desde optimización) ---
    st.sidebar.divider()
    t_ini = st.sidebar.slider("Inicio Banda (Cruce A)", 0, int(c_total), key="t_ini")
    ancho = st.sidebar.slider("Ancho de Banda [s]", 1, int(verde_min), int(verde_min), key="ancho")

    # --- FUNCIÓN: ALINEAR OFFSETS AL INICIO DE BANDA (se mantiene) ---
    def optimizar_offsets_simple():
        base_t = st.session_state.t_ini
        for i, row in df.iterrows():
            t_viaje = row["Dist_Acum"] / v_ms
            st.session_state[f"off_{i}"] = int((base_t + t_viaje) % c_total)

    st.button("🎯 Alinear Offsets al Inicio de Banda", on_click=optimizar_offsets_simple)

    # -------------------------
    # UTILIDADES DE TIEMPO / INTERVALOS EN CÍRCULO
    # -------------------------
    def modC(x, C):
        return float(x) % float(C)

    def green_windows(offset, verde, C):
        """Ventanas verdes dentro de [0,C). Maneja wrap-around."""
        s = float(offset)
        d = float(verde)
        if d <= 0:
            return []
        if s + d <= C:
            return [(s, s + d)]
        return [(s, float(C)), (0.0, (s + d) - float(C))]

    def split_interval_modC(start, duration, C):
        """Intervalo [start, start+duration] mod C en 1 o 2 intervalos dentro de [0,C)."""
        start = modC(start, C)
        end_raw = start + float(duration)
        if end_raw <= float(C):
            return [(start, end_raw)]
        end = end_raw - float(C)
        return [(start, float(C)), (0.0, end)]

    def circular_interval(start, end, C):
        """
        Intervalo circular [start, end] mod C, devuelto como lista de intervalos en [0,C).
        Si el intervalo "invertido" representa wrap.
        """
        C = float(C)
        start = float(start)
        end = float(end)
        # Nota: No asumimos start/end ya mod C para poder manejar rangos negativos
        start_m = start % C
        end_m = end % C
        # Si el rango original (end-start) cubre >=C, entonces es todo el ciclo
        if (end - start) >= C:
            return [(0.0, C)]
        # Si no hay wrap
        if start_m <= end_m:
            return [(start_m, end_m)]
        # Wrap
        return [(start_m, C), (0.0, end_m)]

    def intersect_intervals(A, B):
        """Intersección de dos listas de intervalos [s,e] (s<=e) en [0,C)."""
        out = []
        for (a1, a2) in A:
            for (b1, b2) in B:
                s = max(a1, b1)
                e = min(a2, b2)
                if e > s + 1e-9:  # tolerancia
                    out.append((s, e))
        # compactar (merge)
        if not out:
            return []
        out.sort()
        merged = [out[0]]
        for (s, e) in out[1:]:
            ps, pe = merged[-1]
            if s <= pe + 1e-9:
                merged[-1] = (ps, max(pe, e))
            else:
                merged.append((s, e))
        return merged

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

    def circular_distance(a, b, C):
        """Distancia mínima circular entre dos instantes a,b en [0,C)."""
        C = float(C)
        d = abs((float(a) - float(b)) % C)
        return min(d, C - d)

    # -------------------------
    # VALIDACIÓN Y MÁRGENES (ciclo base)
    # -------------------------
    def interval_inside_green(b_start, b_end, windows):
        """
        Comprueba si [b_start,b_end] cabe dentro de alguna ventana verde.
        Devuelve ok, margen_izq, margen_der, detalle.
        """
        for (gs, ge) in windows:
            if b_start >= gs and b_end <= ge:
                return True, (b_start - gs), (ge - b_end), "OK"

        # Diagnóstico: mejor solape
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

    def validate_at_params(tini_value, ancho_value, build_table=False):
        """
        Valida la banda en ciclo base para un tini y ancho dados.
        Devuelve:
          ok_count, all_ok, min_slack_global, sum_slack, invalid_ids, table_df
        """
        invalid_ids = set()
        rows = [] if build_table else None

        ok_count = 0
        slacks = []
        sum_slack = 0.0
        C = float(c_total)

        for _, row in df.iterrows():
            cruce = row["ID"]
            x = float(row["Dist_Acum"])
            t_arr = (float(tini_value) + (x / v_ms)) % C
            band_intervals = split_interval_modC(t_arr, float(ancho_value), C)
            windows = green_windows(row["Offset"], row["Verde"], C)

            ok_all = True
            worst_detail = "OK"

            cruce_slacks = []
            min_mi = None
            min_md = None

            for (bs, be) in band_intervals:
                ok, mi, md, detail = interval_inside_green(bs, be, windows)

                min_mi = mi if (min_mi is None) else min(min_mi, mi)
                min_md = md if (min_md is None) else min(min_md, md)

                # "Holgura" por intervalo: mínimo margen
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
    # AUTO-AJUSTE DE t_ini (se mantiene, usa ancho actual)
    # -------------------------
    st.sidebar.divider()
    st.sidebar.subheader("🛠️ Auto-ajuste de t_ini")

    def auto_ajustar_tini():
        C = int(c_total)
        best = None
        for tini_candidate in range(C):
            ok_count, all_ok, min_slack, sum_slack, _, _ = validate_at_params(
                tini_candidate, st.session_state.ancho, build_table=False
            )
            candidate = (ok_count, all_ok, min_slack, sum_slack, tini_candidate)
            if best is None:
                best = candidate
                continue

            # 1) más OK, 2) all_ok, 3) mayor holgura mínima, 4) mayor suma holguras
            if candidate[0] > best[0]:
                best = candidate
            elif candidate[0] == best[0]:
                if candidate[1] and not best[1]:
                    best = candidate
                elif candidate[1] == best[1]:
                    if candidate[2] > best[2]:
                        best = candidate
                    elif candidate[2] == best[2] and candidate[3] > best[3]:
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

    st.sidebar.button("🛠️ Auto-ajustar t_ini (ancho actual)", on_click=auto_ajustar_tini)

    if "auto_tini_info" in st.session_state:
        info = st.session_state["auto_tini_info"]
        if info.get("all_ok", False):
            st.sidebar.success(f"t_ini ajustado a {info['t_ini']} s (banda válida).")
        else:
            st.sidebar.warning(f"t_ini ajustado a {info['t_ini']} s (mejor posible, no válida en todos).")
        st.sidebar.caption(f"Holgura mínima (global): {info.get('min_slack', 0.0):.2f} s")

    # -------------------------
    # OPTIMIZACIÓN REAL (BANDA MÁXIMA)
    # -------------------------
    st.sidebar.divider()
    st.sidebar.subheader("📈 Optimización real (banda máxima)")

    modo = st.sidebar.radio(
        "Modo de optimización",
        [
            "Offsets fijos (optimiza ancho + t_ini)",
            "Optimiza t_ini + offsets (ancho máximo global, minimiza cambios)"
        ],
        index=0
    )

    def feasible_tini_intervals_for_width(w):
        """
        Dado un ancho w (segundos), calcula el conjunto de t_ini en [0,C)
        que hace la banda factible en TODOS los cruces, con offsets fijos.
        Devuelve lista de intervalos en [0,C).
        """
        C = float(c_total)
        feasible = [(0.0, C)]
        for _, row in df.iterrows():
            verde = float(row["Verde"])
            if float(w) > verde + 1e-9:
                return []  # imposible en este cruce

            t_travel = float(row["Dist_Acum"]) / v_ms
            windows = green_windows(row["Offset"], row["Verde"], C)

            valid_tini = []
            for (gs, ge) in windows:
                # arrival_start ∈ [gs, ge - w]
                ge_w = ge - float(w)
                if ge_w <= gs + 1e-9:
                    continue
                # t_ini ∈ [gs - t_travel, (ge - w) - t_travel] mod C
                ints = circular_interval(gs - t_travel, ge_w - t_travel, C)
                valid_tini.extend(ints)

            valid_tini = union_intervals(valid_tini)
            feasible = intersect_intervals(feasible, valid_tini)
            if not feasible:
                return []

        return feasible

    def pick_best_tini_from_intervals(intervals, w):
        """
        Escoge el mejor t_ini entero dentro de intervals, maximizando:
        1) holgura mínima global
        2) suma de holguras
        """
        C = int(c_total)
        best = None  # (min_slack, sum_slack, tini)
        for (s, e) in intervals:
            # candidatos enteros dentro del intervalo
            a = int(math.ceil(s - 1e-9))
            b = int(math.floor(e + 1e-9))
            for tini in range(a, b + 1):
                tini = tini % C
                _, all_ok, min_slack, sum_slack, _, _ = validate_at_params(tini, w, build_table=False)
                if not all_ok:
                    continue
                cand = (min_slack, sum_slack, tini)
                if best is None or cand[0] > best[0] or (cand[0] == best[0] and cand[1] > best[1]):
                    best = cand
        # si no encontramos entero por discretización, devolvemos el centro del primer intervalo
        if best is None and intervals:
            s, e = intervals[0]
            tini = int(((s + e) / 2.0) % float(c_total))
            return tini
        return best[2] if best else 0

    def compute_max_band_fixed_offsets():
        """
        Maximiza ancho con offsets fijos:
        - búsqueda binaria de w
        - selección de mejor t_ini factible
        """
        lo, hi = 1, int(verde_min)
        best_intervals = None
        while lo < hi:
            mid = (lo + hi + 1) // 2
            intervals = feasible_tini_intervals_for_width(mid)
            if intervals:
                lo = mid
                best_intervals = intervals
            else:
                hi = mid - 1

        w_max = lo
        intervals = feasible_tini_intervals_for_width(w_max)
        if not intervals:
            # Por robustez (si lo=1 y aún así no hay), devolvemos algo razonable
            return 1, st.session_state.t_ini, False

        tini_best = pick_best_tini_from_intervals(intervals, w_max)
        return int(w_max), int(tini_best), True

    def target_offsets_for_tini_and_width(tini_value, w):
        """
        Calcula offsets objetivo para que la banda de ancho w quede centrada
        dentro del verde de cada cruce (siempre factible si w <= verde_i),
        para una progresión A→... con velocidad v_ms.
        """
        C = float(c_total)
        targets = []
        for _, row in df.iterrows():
            verde = float(row["Verde"])
            x = float(row["Dist_Acum"])
            t_arr = (float(tini_value) + (x / v_ms)) % C
            # centrado: offset = arrival_start - (verde - w)/2
            left_margin = max(0.0, (verde - float(w)) / 2.0)
            off = (t_arr - left_margin) % C
            targets.append(off)
        return targets

    def compute_max_band_with_offset_changes_minimized():
        """
        Ancho máximo global (min verde) + busca t_ini que minimiza cambio de offsets.
        Devuelve: w_max, tini_best, offsets_objetivo_int
        """
        w_max = int(verde_min)
        C = int(c_total)

        # offsets actuales (del state)
        current_offsets = [float(st.session_state.get(f"off_{i}", 0)) for i in range(len(df))]

        best = None  # (cost, min_slack, sum_slack, tini, offs_int)
        for tini in range(C):
            targets = target_offsets_for_tini_and_width(tini, w_max)
            # redondeo a entero (lo que usan los sliders)
            targets_int = [int(round(t)) % C for t in targets]
            # coste = suma distancias circulares a offsets actuales
            cost = sum(circular_distance(current_offsets[i], targets_int[i], C) for i in range(len(df)))

            # además puntuamos holguras resultantes (aunque será factible)
            # Para evaluar holguras, debemos "simular" offsets: aquí evaluamos con offsets objetivos
            # Sin mutar estado, hacemos evaluación rápida:
            # guardamos offsets originales, calculamos holguras con una función ad-hoc
            # (usamos validate_at_params con offsets del df: así que no vale. Hacemos holgura simple centrada)
            # Como el centrado da holgura teórica = (verde - w)/2, el mínimo global es min((verde-w)/2).
            min_slack = min((float(row["Verde"]) - w_max) / 2.0 for _, row in df.iterrows())
            sum_slack = sum((float(row["Verde"]) - w_max) / 2.0 for _, row in df.iterrows())

            cand = (cost, min_slack, sum_slack, tini, targets_int)
            if best is None:
                best = cand
            else:
                # 1) menor coste, 2) mayor holgura mínima, 3) mayor suma holgura
                if cand[0] < best[0] - 1e-9:
                    best = cand
                elif abs(cand[0] - best[0]) <= 1e-9:
                    if cand[1] > best[1] + 1e-9:
                        best = cand
                    elif abs(cand[1] - best[1]) <= 1e-9 and cand[2] > best[2] + 1e-9:
                        best = cand

        if best is None:
            return int(w_max), int(st.session_state.t_ini), [int(current_offsets[i]) % C for i in range(len(df))]
        return int(w_max), int(best[3]), best[4]

    def aplicar_optimizacion():
        if modo.startswith("Offsets fijos"):
            w_max, tini_best, feasible = compute_max_band_fixed_offsets()
            st.session_state["ancho"] = int(w_max)
            st.session_state["t_ini"] = int(tini_best)
            st.session_state["opt_info"] = {
                "modo": "Offsets fijos",
                "ancho": int(w_max),
                "t_ini": int(tini_best),
                "factible": bool(feasible)
            }
            st.rerun()

        else:
            w_max, tini_best, offs_int = compute_max_band_with_offset_changes_minimized()
            st.session_state["ancho"] = int(w_max)
            st.session_state["t_ini"] = int(tini_best)
            for i, off in enumerate(offs_int):
                st.session_state[f"off_{i}"] = int(off)
            st.session_state["opt_info"] = {
                "modo": "t_ini + offsets",
                "ancho": int(w_max),
                "t_ini": int(tini_best),
                "factible": True
            }
            st.rerun()

    st.sidebar.button("📈 Calcular y aplicar banda máxima", on_click=aplicar_optimizacion)

    if "opt_info" in st.session_state:
        info = st.session_state["opt_info"]
        if info.get("factible", False):
            st.sidebar.success(f"Optimización aplicada ({info['modo']}): ancho={info['ancho']} s, t_ini={info['t_ini']} s")
        else:
            st.sidebar.warning(f"Optimización parcial ({info['modo']}): mejor ancho={info['ancho']} s, t_ini={info['t_ini']} s (no garantizado)")
        st.sidebar.caption("Tip: puedes ajustar manualmente y volver a recalcular.")

    # -------------------------
    # VALIDACIÓN ACTUAL (tabla + marcados)
    # -------------------------
    validation_df = None
    invalid_ids = set()

    if validar:
        ok_count, all_ok, min_slack, sum_slack, invalid_ids, validation_df = validate_at_params(
            st.session_state.t_ini, st.session_state.ancho, build_table=True
        )

        st.sidebar.markdown(f"**Cruces OK:** {ok_count}/{len(df)}")
        if not all_ok:
            st.sidebar.error("Hay cruces fuera de verde para la banda actual.")
        else:
            st.sidebar.success("Banda válida en todos los cruces (ciclo base).")
        st.sidebar.caption(f"Holgura mínima global: {min_slack:.2f} s | Holgura total: {sum_slack:.2f} s")

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
        t0 = k * c_total + st.session_state.t_ini
        x_pts = df["Dist_Acum"].tolist()
        y_inf = [t0 + (d / v_ms) for d in x_pts]
        y_sup = [t + st.session_state.ancho for t in y_inf]

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
                t_arr = (float(st.session_state.t_ini) + (x / v_ms)) % C
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

    # Streamlit 2026: width='stretch' / 'content'
    st.plotly_chart(fig, width="stretch")

    # --- PANEL DE VALIDACIÓN (TABLA) ---
    if validar and validation_df is not None:
        st.subheader("✅ Validación automática de la banda (ciclo base)")
        st.caption("""
        Comprueba si la banda de progresión (A→...) en el **ciclo base** queda totalmente dentro de verde en cada cruce.  
        *Holgura (min)* es el margen más restrictivo por cruce.
        """)
        st.dataframe(validation_df, width="stretch", hide_index=True)

    # --- MÉTRICAS ---
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Velocidad de Diseño", f"{v_kmh} km/h")
    m2.metric("Ancho de Banda", f"{st.session_state.ancho} s")
    m3.metric("Eficiencia", f"{(st.session_state.ancho / c_total) * 100:.1f}%")

    if validar and validation_df is not None and len(invalid_ids) > 0:
        st.warning(
            "La banda no es válida en todos los cruces. "
            "Prueba a: (1) Optimización real (banda máxima), (2) Auto-ajustar t_ini, "
            "(3) Alinear offsets, o (4) reducir el ancho."
        )


if __name__ == "__main__":
    main()