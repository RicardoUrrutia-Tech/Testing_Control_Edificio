import streamlit as st
from datetime import datetime, date
from io import BytesIO

from PIL import Image

# PDF (ReportLab)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

# Word (python-docx)
from docx import Document
from docx.shared import Inches


st.set_page_config(
    page_title="Control Edificio Pro (Streamlit)",
    page_icon="🛡️",
    layout="wide",
)

# ---------------------------
# Helpers (State)
# ---------------------------
def init_state():
    if "report_date" not in st.session_state:
        st.session_state["report_date"] = date.today()

    # IMPORTANTE: NO usar key "items" (colisiona con st.session_state.items())
    if "checklist_items" not in st.session_state:
        st.session_state["checklist_items"] = [
            {"id": 1, "cat": "Críticos", "name": "Sala de Bombas", "task": "Presión y alternancia", "status": "pending", "note": "", "photo": None},
            {"id": 2, "cat": "Críticos", "name": "Sala de Calderas", "task": "Temperatura y fugas", "status": "pending", "note": "", "photo": None},
            {"id": 3, "cat": "Críticos", "name": "Generador", "task": "Nivel petróleo y batería", "status": "pending", "note": "", "photo": None},
            {"id": 4, "cat": "Críticos", "name": "PEAS (Presurización)", "task": "Prueba de ventilador", "status": "pending", "note": "", "photo": None},
            {"id": 5, "cat": "Críticos", "name": "Ascensores (2)", "task": "Nivelación y limpieza rieles", "status": "pending", "note": "", "photo": None},
            {"id": 6, "cat": "Accesos", "name": "Portones (2)", "task": "Sensores y velocidad", "status": "pending", "note": "", "photo": None},
            {"id": 7, "cat": "Accesos", "name": "Control Biométrico", "task": "Lectores huella/tarjeta", "status": "pending", "note": "", "photo": None},
            {"id": 8, "cat": "Higiene", "name": "Sala de Basura", "task": "Desinfección y contenedores", "status": "pending", "note": "", "photo": None},
            {"id": 9, "cat": "Higiene", "name": "Ductos (20 pisos)", "task": "Cierre de escotillas", "status": "pending", "note": "", "photo": None},
            {"id": 10, "cat": "Comunes", "name": "Piscina", "task": "Parámetros Cl/pH", "status": "pending", "note": "", "photo": None},
            {"id": 11, "cat": "Comunes", "name": "Quincho / Eventos", "task": "Mobiliario e higiene", "status": "pending", "note": "", "photo": None},
            {"id": 12, "cat": "Comunes", "name": "Gym / Sauna", "task": "Máquinas y tableros", "status": "pending", "note": "", "photo": None},
            {"id": 13, "cat": "Infra", "name": "Pasillos (1-20)", "task": "Luces de emergencia", "status": "pending", "note": "", "photo": None},
            {"id": 14, "cat": "Infra", "name": "Subterráneo", "task": "Filtraciones y limpieza", "status": "pending", "note": "", "photo": None},
            {"id": 15, "cat": "Infra", "name": "Jardines", "task": "Riego programado", "status": "pending", "note": "", "photo": None},
        ]

    if "incidences" not in st.session_state:
        st.session_state["incidences"] = []  # {id, employee, detail, ts}

    if "needs" not in st.session_state:
        st.session_state["needs"] = ""


# ---------------------------
# Helpers (UI/Stats/Text)
# ---------------------------
def status_badge(status: str) -> str:
    if status == "ok":
        return "🟢 OK"
    if status == "fail":
        return "🔴 FALLA"
    return "⚪ PEND."


def status_color(status: str) -> str:
    if status == "ok":
        return "#16a34a"
    if status == "fail":
        return "#dc2626"
    return "#64748b"


def get_stats():
    items = st.session_state["checklist_items"]
    ok = sum(1 for i in items if i["status"] == "ok")
    fail = sum(1 for i in items if i["status"] == "fail")
    pending = sum(1 for i in items if i["status"] == "pending")
    total = len(items)
    return ok, fail, pending, total


def build_report_text():
    rd = st.session_state["report_date"]
    ok, fail, pending, total = get_stats()

    lines = []
    lines.append("--- INFORME DE GESTIÓN / CONTROL DE INSTALACIONES ---")
    lines.append(f"FECHA: {rd.isoformat()}")
    lines.append("")
    lines.append(f"RESUMEN: OK={ok} | FALLAS={fail} | PENDIENTES={pending} | TOTAL={total}")
    lines.append("")
    lines.append("1) CHECKLIST TÉCNICO")
    lines.append("---------------------------------")

    categories = ["Críticos", "Accesos", "Higiene", "Comunes", "Infra"]
    for cat in categories:
        lines.append(f"\n[{cat}]")
        for it in [x for x in st.session_state["checklist_items"] if x["cat"] == cat]:
            note = (it.get("note") or "").strip()
            note_txt = note if note else "Sin novedades."
            lines.append(f"- {status_badge(it['status'])} {it['name']} ({it['task']}): {note_txt}")

    lines.append("\n2) REQUERIMIENTOS / COMPRAS")
    lines.append("---------------------------------")
    needs = (st.session_state["needs"] or "").strip() or "Sin requerimientos reportados."
    lines.append(needs)

    lines.append("\n3) INCIDENCIAS RR.HH.")
    lines.append("---------------------------------")
    incidences = st.session_state["incidences"]
    if not incidences:
        lines.append("Sin incidencias registradas.")
    else:
        for inc in sorted(incidences, key=lambda x: x["ts"], reverse=True):
            ts = inc["ts"].strftime("%Y-%m-%d %H:%M")
            lines.append(f"- {ts} | {inc['employee']}: {inc['detail']}")

    return "\n".join(lines)


# ---------------------------
# Helpers (PDF/DOCX)
# ---------------------------
def _wrap_pdf_line(text: str, max_chars: int):
    import textwrap
    return textwrap.wrap(text, width=max_chars) or [""]


def generate_pdf_bytes(report_text: str) -> bytes:
    """
    PDF con texto + fotos anexas.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    x = 2 * cm
    y = height - 2 * cm
    line_h = 12

    def new_page():
        nonlocal y
        c.showPage()
        y = height - 2 * cm

    # Título
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, "INFORME DE GESTIÓN / CONTROL DE INSTALACIONES")
    y -= 18
    c.setFont("Helvetica", 10)

    # Texto
    for raw_line in report_text.split("\n"):
        if raw_line.strip() == "":
            if y < 2 * cm:
                new_page()
            y -= line_h
            continue

        for ln in _wrap_pdf_line(raw_line, 110):
            if y < 2 * cm:
                new_page()
            c.drawString(x, y, ln)
            y -= line_h

    # Fotos
    items = st.session_state["checklist_items"]
    photos = [it for it in items if it.get("photo")]

    if photos:
        if y < 5 * cm:
            new_page()

        c.setFont("Helvetica-Bold", 12)
        c.drawString(x, y, "ANEXO: FOTOS")
        y -= 18
        c.setFont("Helvetica", 10)

        for it in photos:
            header = f"#{it['id']} - {it['cat']} - {it['name']} ({it['task']})"
            note = (it.get("note") or "").strip()
            note_txt = f"Obs: {note}" if note else "Obs: (sin observaciones)"

            for ln in _wrap_pdf_line(header, 110):
                if y < 2 * cm:
                    new_page()
                c.drawString(x, y, ln)
                y -= line_h

            for ln in _wrap_pdf_line(note_txt, 110):
                if y < 2 * cm:
                    new_page()
                c.drawString(x, y, ln)
                y -= line_h

            img_bytes = it["photo"]
            img = Image.open(BytesIO(img_bytes)).convert("RGB")

            max_w = 16 * cm
            max_h = 9 * cm
            iw, ih = img.size
            scale = min(max_w / iw, max_h / ih)
            dw, dh = iw * scale, ih * scale

            if y - dh < 2 * cm:
                new_page()

            img_buf = BytesIO()
            img.save(img_buf, format="JPEG", quality=85)
            img_buf.seek(0)

            c.drawInlineImage(img_buf, x, y - dh, width=dw, height=dh)
            y -= (dh + 18)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_docx_bytes(report_text: str) -> bytes:
    """
    DOCX con texto + fotos anexas.
    """
    doc = Document()
    doc.add_heading("Informe de Gestión / Control de Instalaciones", level=1)

    for line in report_text.split("\n"):
        doc.add_paragraph(line)

    items = st.session_state["checklist_items"]
    photos = [it for it in items if it.get("photo")]

    if photos:
        doc.add_page_break()
        doc.add_heading("Anexo: Fotos", level=2)

        for it in photos:
            doc.add_paragraph(f"#{it['id']} - {it['cat']} - {it['name']} ({it['task']})")
            note = (it.get("note") or "").strip()
            doc.add_paragraph(f"Obs: {note}" if note else "Obs: (sin observaciones)")

            img = Image.open(BytesIO(it["photo"])).convert("RGB")
            img_buf = BytesIO()
            img.save(img_buf, format="PNG")
            img_buf.seek(0)

            doc.add_picture(img_buf, width=Inches(5.8))
            doc.add_paragraph("")

    out = BytesIO()
    doc.save(out)
    out.seek(0)
    return out.getvalue()


# ---------------------------
# UI
# ---------------------------
init_state()
ok, fail, pending, total = get_stats()

st.markdown(
    f"""
    <div style="padding:18px 18px 10px 18px; border-radius:16px; background: linear-gradient(90deg, #4338ca, #4f46e5); color:white;">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap;">
        <div>
          <div style="font-size:24px; font-weight:800;">🛡️ Control Edificio Pro</div>
          <div style="opacity:0.85;">Mayordomía y Gestión de Operaciones (demo Streamlit)</div>
        </div>
        <div style="display:flex; gap:16px;">
          <div style="background: rgba(0,0,0,0.20); padding:10px 14px; border-radius:12px; text-align:center; min-width:120px;">
            <div style="font-size:11px; letter-spacing:0.08em; opacity:0.8;">SISTEMAS OK</div>
            <div style="font-size:24px; font-weight:800; color:#4ade80;">{ok}</div>
          </div>
          <div style="background: rgba(0,0,0,0.20); padding:10px 14px; border-radius:12px; text-align:center; min-width:120px;">
            <div style="font-size:11px; letter-spacing:0.08em; opacity:0.8;">FALLAS</div>
            <div style="font-size:24px; font-weight:800; color:#f87171;">{fail}</div>
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("")

tab_checklist, tab_rrhh, tab_report = st.tabs(
    ["✅ Levantamiento Técnico", "👥 RR.HH. (Incidencias)", "🧾 Generar Informe"]
)

# ---------------------------
# Checklist
# ---------------------------
with tab_checklist:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Checklist Técnico (por áreas)")
        st.caption("Marca OK / FALLA / PENDIENTE, agrega observaciones y (opcional) una foto por ítem.")
    with c2:
        st.session_state["report_date"] = st.date_input(
            "Fecha del informe",
            value=st.session_state["report_date"]
        )

    categories = ["Críticos", "Accesos", "Higiene", "Comunes", "Infra"]

    for cat in categories:
        st.markdown(f"### {cat}")
        for it in [x for x in st.session_state["checklist_items"] if x["cat"] == cat]:
            box = st.container(border=True)
            with box:
                left, mid, right = st.columns([2.2, 2.2, 1.6], gap="medium")

                with left:
                    st.markdown(f"**{it['name']}**")
                    st.caption(it["task"])

                with mid:
                    status = st.radio(
                        "Estado",
                        options=["pending", "ok", "fail"],
                        format_func=lambda v: {"pending": "Pendiente", "ok": "OK", "fail": "Falla"}[v],
                        index=["pending", "ok", "fail"].index(it["status"]),
                        horizontal=True,
                        key=f"status_{it['id']}",
                        label_visibility="collapsed",
                    )
                    it["status"] = status

                    it["note"] = st.text_input(
                        "Observación",
                        value=it["note"],
                        placeholder="Escribe una observación breve…",
                        key=f"note_{it['id']}",
                        label_visibility="collapsed",
                    )

                with right:
                    st.markdown(
                        f"""
                        <div style="padding:10px 12px; border-radius:12px; border:1px solid #e2e8f0;">
                          <div style="font-weight:800; color:{status_color(it['status'])}; font-size:16px;">
                            {status_badge(it['status'])}
                          </div>
                          <div style="opacity:0.7; font-size:12px;">Ítem #{it['id']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    uploaded = st.file_uploader(
                        "Foto (opcional)",
                        type=["png", "jpg", "jpeg"],
                        key=f"photo_{it['id']}",
                        label_visibility="collapsed",
                    )
                    if uploaded is not None:
                        it["photo"] = uploaded.getvalue()
                        st.image(it["photo"], caption="Foto adjunta", use_container_width=True)

        st.divider()

    colA, colB, colC = st.columns([1, 1, 2])
    with colA:
        if st.button("🔄 Marcar todo como Pendiente"):
            for it in st.session_state["checklist_items"]:
                it["status"] = "pending"
            st.rerun()

    with colB:
        if st.button("✅ Marcar todo como OK"):
            for it in st.session_state["checklist_items"]:
                it["status"] = "ok"
            st.rerun()

    with colC:
        st.info("Tip: sin base de datos, el contenido se mantiene mientras no cierres/recargues la pestaña. Para persistencia real, se integra Firebase/Sheets.")

# ---------------------------
# RR.HH - Incidences
# ---------------------------
with tab_rrhh:
    st.subheader("Gestión RR.HH. – Incidencias manuales")
    st.caption("Registra incidencias por empleado (puedes agregar múltiples incidencias para el mismo nombre).")

    with st.form("add_incidence", clear_on_submit=True):
        employee = st.text_input("Nombre del empleado", placeholder="Ej: Juan Pérez")
        detail = st.text_area("Detalle de la incidencia", placeholder="Ej: Atraso 20 min. / Falta de EPP / Observación…", height=120)
        submitted = st.form_submit_button("➕ Ingresar nueva incidencia")

        if submitted:
            if not employee.strip() or not detail.strip():
                st.error("Por favor completa nombre del empleado y detalle.")
            else:
                incidences = st.session_state["incidences"]
                new_id = (max([i["id"] for i in incidences]) + 1) if incidences else 1
                st.session_state["incidences"].append(
                    {"id": new_id, "employee": employee.strip(), "detail": detail.strip(), "ts": datetime.now()}
                )
                st.success("Incidencia registrada.")

    st.write("")
    st.markdown("#### Incidencias registradas")

    if not st.session_state["incidences"]:
        st.warning("Aún no hay incidencias.")
    else:
        for inc in sorted(st.session_state["incidences"], key=lambda x: x["ts"], reverse=True):
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 6, 1.2])
                with c1:
                    st.markdown(f"**{inc['employee']}**")
                    st.caption(inc["ts"].strftime("%Y-%m-%d %H:%M"))
                with c2:
                    st.write(inc["detail"])
                with c3:
                    if st.button("🗑️", key=f"del_inc_{inc['id']}", help="Eliminar incidencia"):
                        st.session_state["incidences"] = [x for x in st.session_state["incidences"] if x["id"] != inc["id"]]
                        st.rerun()

# ---------------------------
# Report
# ---------------------------
with tab_report:
    st.subheader("Generador de Informe (descarga PDF o Word con fotos)")
    st.caption("Se arma automáticamente con el checklist + requerimientos/compras + incidencias RR.HH. Incluye fotos en un anexo.")

    st.session_state["needs"] = st.text_area(
        "Requerimientos y compras (texto libre)",
        value=st.session_state["needs"],
        height=140,
        placeholder="Ej: Solicitar mantención ascensores / compra de luminarias / repuestos bomba…",
    )

    report_text = build_report_text()

    st.markdown("#### Vista previa (texto)")
    st.code(report_text, language="text")

    fmt = st.radio("Formato de descarga", options=["PDF", "Word (DOCX)"], horizontal=True)

    file_base = f"informe_edificio_{st.session_state['report_date'].isoformat()}"

    col1, col2 = st.columns([1, 2])
    with col1:
        if fmt == "PDF":
            pdf_bytes = generate_pdf_bytes(report_text)
            st.download_button(
                "⬇️ Descargar PDF (con fotos)",
                data=pdf_bytes,
                file_name=f"{file_base}.pdf",
                mime="application/pdf",
            )
        else:
            docx_bytes = generate_docx_bytes(report_text)
            st.download_button(
                "⬇️ Descargar Word (DOCX) (con fotos)",
                data=docx_bytes,
                file_name=f"{file_base}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

    with col2:
        st.info("Tip: si subes muchas fotos grandes, el archivo puede quedar pesado. Si quieres, puedo agregar redimensionado/compresión automática.")

st.markdown(
    "<div style='opacity:0.6; font-size:12px; margin-top:18px;'>Plataforma de Control Interno v1.0 (demo) • Streamlit</div>",
    unsafe_allow_html=True
)

