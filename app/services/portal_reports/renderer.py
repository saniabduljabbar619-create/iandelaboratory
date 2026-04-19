from pathlib import Path
from datetime import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader


def _safe_set_alpha(c, a):
    try:
        c.setFillAlpha(a)
    except Exception:
        pass


def _draw_header(c, lab_profile, w, h):

    logo = lab_profile.get("logo_path")

    top_y = h - 20 * mm

    # In your _draw_header function
    if logo:
        try:
            from PIL import Image
            # logo is already str(logo_path) from your config.py
            pil_img = Image.open(logo)
            
            # Explicitly ensure it is RGB/RGBA to avoid 'L' or 'P' mode errors
            if pil_img.mode not in ('RGB', 'RGBA'):
                pil_img = pil_img.convert('RGB')
                
            img = ImageReader(pil_img)
            size = 18 * mm
    
            # Check your Y coordinates; if h - 38*mm is too low, 
            # it might be drawing off-page or behind a table.
            c.drawImage(img, 15 * mm, h - 35 * mm, size, size, mask='auto')
            c.drawImage(img, w - 15 * mm - size, h - 35 * mm, size, size, mask='auto')
        except Exception as e:
            print(f"DEBUG PDF LOGO ERROR: {e}") # Add this to see the error in Railway logs

    lab_name = lab_profile.get("lab_name", "Laboratory")
    address = lab_profile.get("address", "")
    phone = lab_profile.get("phone", "")
    email = lab_profile.get("email", "")

    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(w / 2, top_y, lab_name)

    c.setFont("Helvetica", 9)

    y_txt = top_y - 5 * mm

    if address:
        c.drawCentredString(w / 2, y_txt, address)
        y_txt -= 4 * mm

    contact = "  ".join([x for x in [phone, email] if x])

    if contact:
        c.drawCentredString(w / 2, y_txt, contact)

    c.setStrokeColor(colors.grey)
    c.setLineWidth(1)

    c.line(15 * mm, h - 42 * mm, w - 15 * mm, h - 42 * mm)


def _ensure_space(c, y, needed, page_height, lab_profile, w):
    if y - needed < 25 * mm:
        c.showPage()
        _draw_header(c, lab_profile, w, page_height)
        return page_height - 50 * mm
    return y


def render_pdf(output_path, lab_profile, patient_row, bundle_results, source="lab"):

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(out), pagesize=A4)

    w, h = A4

    # ================= WATERMARK =================

    logo = lab_profile.get("logo_path")
    watermark = bool(lab_profile.get("watermark_enabled", True))

    if watermark and logo:
        try:
            from PIL import Image

            pil_img = Image.open(logo).convert("RGB")
            img = ImageReader(pil_img)

            _safe_set_alpha(c, 0.08)

            size = 140 * mm

            c.drawImage(
                img,
                (w - size) / 2,
                (h - size) / 2,
                size,
                size,
                mask="auto",
            )

            _safe_set_alpha(c, 1)

        except Exception:
            pass

    # ================= HEADER =================

    _draw_header(c, lab_profile, w, h)

    # ================= PATIENT BLOCK =================

    pid = patient_row.get("Patient ID", "-")
    name = patient_row.get("Name", "-")
    sex = patient_row.get("Sex", "-")
    age = patient_row.get("Age", "-")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, h - 48 * mm, "Patient Report")

    c.setFont("Helvetica", 9)

    c.drawString(15 * mm, h - 53 * mm, f"Name: {name}")
    c.drawString(15 * mm, h - 57 * mm, f"Patient ID: {pid}")

    c.drawString(80 * mm, h - 53 * mm, f"Sex: {sex}")
    c.drawString(80 * mm, h - 57 * mm, f"Age: {age}")

    c.drawString(w - 60 * mm, h - 53 * mm, f"Printed: {now}")

    y = h - 65 * mm

    # ================= RESULTS =================

    for rid, payload in bundle_results.items():

        test_name = payload.get("request", {}).get("test_name", "Test")

        y = _ensure_space(c, y, 20 * mm, h, lab_profile, w)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(15 * mm, y, test_name)

        y -= 6 * mm

        typ = payload.get("type")

        # ================= STRUCTURED RESULT =================

        if typ == "structured":

            rows = payload.get("rows", [])

            data = [["Parameter", "Result", "Unit", "Ref Range", "Flag"]]

            for r in rows:
                data.append(
                    [
                        r.get("parameter", ""),
                        r.get("result", ""),
                        r.get("unit", ""),
                        r.get("ref_range", ""),
                        r.get("flag", ""),
                    ]
                )

            tbl = Table(
                data,
                colWidths=[60 * mm, 25 * mm, 22 * mm, 35 * mm, 18 * mm],
            )

            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("WORDWRAP", (0, 0), (-1, -1), True),
                        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ]
                )
            )

            tw, th = tbl.wrapOn(c, w - 30 * mm, y)

            y = _ensure_space(c, y, th + 10 * mm, h, lab_profile, w)

            tbl.drawOn(c, 15 * mm, y - th)

            y -= th + 8 * mm

        # ================= GRID TABLE RESULT =================

        elif typ == "table":

            grid = payload.get("grid", {})
            cells = grid.get("cells", [])

            if not cells:
                continue

            ncols = max(len(r) for r in cells)

            padded = [r + [""] * (ncols - len(r)) for r in cells]

            col_width = (w - 30 * mm) / ncols

            tbl = Table(padded, colWidths=[col_width] * ncols)

            tbl.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ]
                )
            )

            tw, th = tbl.wrapOn(c, w - 30 * mm, y)

            y = _ensure_space(c, y, th + 10 * mm, h, lab_profile, w)

            tbl.drawOn(c, 15 * mm, y - th)

            y -= th + 8 * mm

        # separator between tests
        c.setStrokeColor(colors.lightgrey)
        c.line(15 * mm, y, w - 15 * mm, y)

        y -= 6 * mm


    # ================= FOOTER =================
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.5)
    c.line(15 * mm, 28 * mm, w - 15 * mm, 28 * mm)

    # Primary Footer (General Note)
    c.setFont("Helvetica", 8)
    footer = lab_profile.get(
        "report_notes",
        "Authorized Laboratory Report — Generated by Solunex Technologies Software.",
    )
    c.drawCentredString(w / 2, 22 * mm, footer)

    # --- SUBTLE SOURCE TRACKING NOTE ---
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.gray)
    
    if source == "lab":
        source_note = "Official Reprint: Routed and fetched from the Laboratory Internal Portal."
    else:
        source_note = "Online Document: Electronically generated and downloaded via the Patient Portal."

    # Positioned slightly lower than the main footer
    c.drawCentredString(w / 2, 18 * mm, source_note)
    # -----------------------------------

    c.save()
    return str(out)
