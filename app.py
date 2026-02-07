import streamlit as st
from datetime import datetime, date
from io import BytesIO

from PIL import Image

# PDF (ReportLab - visual)
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

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
# PDF (Visual 3-column table + red soft background on FAIL + summary cards)
# ---------------------------
def _status_tag_html(status: str) -> str:
    if status == "ok":
        return '<font color="#16a34a"><b>OK</b></font>'
    if status == "fail":
        return '<font color="#dc2626"><b>FALLA</b></font>'
    return '<font color="#64748b"><b>PEND.</b></font>'


def _make_rl_image(photo_bytes: bytes, max_w: float, max_h: float, small_style):
    if not photo_bytes:
        return Paragraph("<i>Sin foto</i>", small_style)

    try:
        img = Image.open(BytesIO(photo_bytes)).convert("RGB")
    except Exception:
        return Paragraph("<i>Foto inválida</i>", small_style)

    iw, ih = img.size
    scale = min(max_w / iw, max_h / ih)
    w, h = iw * scale, ih * scale

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)

    # Import local para evitar warnings en algunos entornos
    from reportlab.platypus import Image as RLImage
    return RLImage(buf, width=w, height=h)


def generate_pdf_bytes_visual() -> bytes:
    styles = getSampleStyleSheet()

    normal = ParagraphStyle(
        "normal",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )
    small = ParagraphStyle(
        "small",
        parent=normal,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )
    title_style = ParagraphStyle(
        "title_style",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=8,
    )
    cat_style = ParagraphStyle(
        "cat_style",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.HexColor("#4338ca"),
        spaceBefore=10,
        spaceAfter=6,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )

    elements = []
    rd = st.session_state["report_date"]
    ok, fail, pending, total = get_stats()

    # Title
    elements.append(Paragraph("Control Edificio Pro – Informe Visual", title_style))
    elements.append(Paragraph(f"<b>Fecha:</b> {rd.isoformat()}", normal))
    elements.append(Spacer(1, 8))

    # Summary "cards" (as a 2-column small table)
    summary_data = [
        [
            Paragraph("<b>Sistemas OK</b>", small),
            Paragraph("<b>Fallas</b>", small),
            Paragraph("<b>Pendientes</b>", small),
            Paragraph("<b>Total</b>", small),
        ],
        [
            Paragraph(f"<font color='#16a34a'><b>{ok}</b></font>", normal),
            Paragraph(f"<font color='#dc2626'><b>{fail}</b></font>", normal),
            Paragraph(f"<font color='#64748b'><b>{pending}</b></font>", normal),
            Paragraph(f"<b>{total}</b>", normal),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[4.2 * cm, 4.2 * cm, 4.2 * cm, 4.2 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#ffffff")),
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # Table layout
    col1_w = 6.2 * cm   # Instalación
    col2_w = 6.2 * cm   # Estado+Obs
    col3_w = 5.6 * cm   # Foto
    photo_max_w = col3_w - 0.3 * cm
    photo_max_h = 3.6 * cm

    categories = ["Críticos", "Accesos", "Higiene", "Comunes", "Infra"]
    items = st.session_state["checklist_items"]

    for cat in categories:
        cat_items = [x for x in items if x["cat"] == cat]
        if not cat_items:
            continue

        elements.append(Paragraph(cat, cat_style))

        # Header row
        data = [
            [
                Paragraph("<b>Instalación</b>", normal),
                Paragraph("<b>Estado / Observación</b>", normal),
                Paragraph("<b>Registro visual</b>", normal),
            ]
        ]

        fail_row_indices = []  # for styling fail rows background

        for it in cat_items:
            inst = Paragraph(
                f"<b>{it['name']}</b><br/><font color='#64748b'>{it['task']}</font>",
                normal,
            )
            note = (it.get("note") or "").strip()
            note_txt = note if note else "Sin novedades."

            mid = Paragraph(
                f"{_status_tag_html(it['status'])}<br/>{note_txt}",
                normal,
            )

            img_cell = _make_rl_image(it.get("photo"), photo_max_w, photo_max_h, small)

            row = [inst, mid, img_cell]
            data.append(row)

            # Row index in table (0 is header)
            if it["status"] == "fail":
                fail_row_indices.append(len(data) - 1)

        table = Table(data, colWidths=[col1_w, col2_w, col3_w])

        style_cmds = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ]

        # Soft red background for FAIL rows
        soft_red = colors.HexColor("#fee2e2")  # light red
        for r in fail_row_indices:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), soft_red))

        table.setStyle(TableStyle(style_cmds))

        elements.append(table)
        elements.append(Spacer(1, 10))

    # Footer sections (no structural changes besides PDF formatting)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Requerimientos / Compras", cat_style))
    needs = (st.session_state["needs"] or "").strip() or "Sin requerimientos reportados."
    elements.append(Paragraph(needs, normal))

    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Incidencias RR.HH.", cat_style))
    incidences = st.session_state["incidences"]
    if not incidences:
        elements.append(Paragraph("Sin incidencias registradas.", normal))
    else:
        for inc in sorted(incidences, key=lambda x: x["ts"], reverse=True):
            ts = inc["ts"].strftime("%Y-%m-%d %H:%M")
            elements.append(Paragraph(f"- <b>{ts}</b> | <b>{inc['employee']}</b>: {inc['detail']}", normal))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------------------
# Word (same as before: text + photo annex)
# ---------------------------
def generate_docx_bytes(report_text: str) -> bytes:
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

# Header (same as before)
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
    st.caption("El PDF se exporta con estructura visual (3 columnas por área). El Word se exporta en texto + anexo de fotos (por ahora).")

    st.session_state["needs"] = st.text_area(
        "Requerimientos y compras (texto libre)",
        value=st.session_state["needs"],
        height=140,
        placeholder="Ej: Solicitar mantención ascensores / compra de luminarias / repuestos bomba…",
    )

    report_text = build_report_text()

    st.markdown("#### Vista previa (texto)")
    st.code(report_text, language="text")

    fmt = st.radio("Formato de descarga", options=["PDF (Visual)", "Word (DOCX)"], horizontal=True)

    file_base = f"informe_edificio_{st.session_state['report_date'].isoformat()}"

    col1, col2 = st.columns([1, 2])
    with col1:
        if fmt.startswith("PDF"):
            pdf_bytes = generate_pdf_bytes_visual()
            st.download_button(
                "⬇️ Descargar PDF (Visual, con fotos)",
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
        st.info("Tip: si subes muchas fotos grandes, el PDF/DOCX puede quedar pesado. Si quieres, puedo agregar redimensionado/compresión automática.")

st.markdown(
    "<div style='opacity:0.6; font-size:12px; margin-top:18px;'>Plataforma de Control Interno v1.0 (demo) • Streamlit</div>",
    unsafe_allow_html=True
)

