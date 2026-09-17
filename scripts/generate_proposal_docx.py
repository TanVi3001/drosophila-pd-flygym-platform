#!/usr/bin/env python
"""Generate an official academic Research Proposal (Đề Cương NCKH) in DOCX format.

Uses python-docx to generate a beautifully styled Microsoft Word document
complying with standard Vietnamese University NCKH guidelines (12 mandatory sections,
tables, typography, IEEE references, and critical self-evaluation).
"""

from __future__ import annotations

from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DOCX = REPO_ROOT / "docs" / "scientific" / "De_Cuong_NCKH_Drosophila_Parkinson.docx"


def set_cell_background(cell, fill_hex: str):
    """Set the background color of a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)


def set_cell_margins(cell, top=120, bottom=120, left=150, right=150):
    """Set internal cell padding (in dxa: 20 dxa = 1 pt)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def add_styled_heading(doc, text: str, level: int):
    """Add a heading with academic primary colors and font styles."""
    p = doc.add_heading(text, level=level)
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    for run in p.runs:
        run.font.name = "Times New Roman"
        if level == 1:
            run.font.size = Pt(15)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)  # Navy Blue
        elif level == 2:
            run.font.size = Pt(13)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0x2B, 0x54, 0x7E)
        else:
            run.font.size = Pt(12)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    return p


def add_body_paragraph(doc, text: str = "", bold_prefix: str = "", italic: bool = False):
    """Add standard academic body text."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.2
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    if bold_prefix:
        r_prefix = p.add_run(bold_prefix)
        r_prefix.font.name = "Times New Roman"
        r_prefix.font.size = Pt(12)
        r_prefix.font.bold = True
        r_prefix.font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    if text:
        r_text = p.add_run(text)
        r_text.font.name = "Times New Roman"
        r_text.font.size = Pt(12)
        r_text.font.italic = italic
        r_text.font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    return p


def add_bullet_point(doc, text: str, bold_prefix: str = ""):
    """Add a bullet point with proper indentation."""
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    if bold_prefix:
        r_prefix = p.add_run(bold_prefix)
        r_prefix.font.name = "Times New Roman"
        r_prefix.font.size = Pt(12)
        r_prefix.font.bold = True

    r_text = p.add_run(text)
    r_text.font.name = "Times New Roman"
    r_text.font.size = Pt(12)
    return p


def build_proposal_docx():
    doc = docx.Document()

    # Configure Margins: Standard A4 (Top=2cm, Bottom=2cm, Left=3cm, Right=2cm)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(1.1)
        section.right_margin = Inches(0.8)

    # Set normal style font
    style_normal = doc.styles["Normal"]
    font = style_normal.font
    font.name = "Times New Roman"
    font.size = Pt(12)
    font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    # ==========================================
    # COVER / HEADER
    # ==========================================
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_after = Pt(2)
    r1 = p_inst.add_run("BỘ GIÁO DỤC VÀ ĐÀO TẠO — TRƯỜNG ĐẠI HỌC KỸ THUẬT\n")
    r1.font.bold = True
    r1.font.size = Pt(13)
    r2 = p_inst.add_run("KHOA CÔNG NGHỆ THÔNG TIN\n")
    r2.font.bold = True
    r2.font.size = Pt(14)
    r2.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    r3 = p_inst.add_run("PHÒNG THÍ NGHIỆM SINH TIN HỌC & TÍNH TOÁN Y SINH")
    r3.font.size = Pt(11)
    r3.font.italic = True

    # Divider line
    p_div = doc.add_paragraph()
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div.paragraph_format.space_after = Pt(14)
    r_div = p_div.add_run("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    r_div.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # Main Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(8)
    p_title.paragraph_format.space_after = Pt(6)
    r_title_tag = p_title.add_run("ĐỀ CƯƠNG NGHIÊN CỨU KHOA HỌC SINH VIÊN\n")
    r_title_tag.font.bold = True
    r_title_tag.font.size = Pt(16)
    r_title_tag.font.color.rgb = RGBColor(0xBA, 0x1B, 0x1D)

    r_title = p_title.add_run(
        "MÔ PHỎNG TIẾN TRIỂN BỆNH PARKINSON TRÊN DROSOPHILA MELANOGASTER "
        "BẰNG HỆ THỐNG SINH HỌC TÍNH TOÁN: TÁI HIỆN VÀ XÁC NHẬN KIỂU HÌNH VẬN ĐỘNG "
        "THEO THANG ĐỊNH LƯỢNG Y VĂN"
    )
    r_title.font.bold = True
    r_title.font.size = Pt(14)
    r_title.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    # Metadata Table
    meta_table = doc.add_table(rows=5, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False

    meta_data = [
        ("Lĩnh vực nghiên cứu:", "Neuroscience tính toán / Cơ sinh học vận động / Sinh tin học"),
        ("Nhóm sinh viên thực hiện:", "Nhóm Nghiên cứu Sinh thái & Tính toán Thần kinh (SV Năm 3 - 4)"),
        ("Giảng viên hướng dẫn:", "TS. GVHD chuyên ngành Trí tuệ Nhân tạo & Y sinh"),
        ("Thời gian thực hiện:", "08 tháng (32 tuần) — Dự kiến nghiệm thu đợt 1"),
        ("Trạng thái đề cương:", "Phiên bản 2.0 (Đã hoàn thiện sau phản biện hội đồng)"),
    ]

    for i, (k, v) in enumerate(meta_data):
        row = meta_table.rows[i]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(2.2)
        c1.width = Inches(4.5)
        set_cell_background(c0, "F2F5F8")
        set_cell_margins(c0, 60, 60, 100, 100)
        set_cell_margins(c1, 60, 60, 100, 100)
        
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_k = p0.add_run(k)
        r_k.font.bold = True
        r_k.font.size = Pt(11)
        
        p1 = c1.paragraphs[0]
        r_v = p1.add_run(v)
        r_v.font.size = Pt(11)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # ==========================================
    # 1. TÊN ĐỀ TÀI
    # ==========================================
    add_styled_heading(doc, "1. TÊN ĐỀ TÀI", level=1)
    add_body_paragraph(
        doc,
        "Mô phỏng Tiến triển Bệnh Parkinson trên Drosophila melanogaster bằng Hệ thống Sinh học Tính toán: "
        "Tái hiện và Xác nhận Kiểu hình Vận động theo Thang Định lượng Y văn",
        bold_prefix="Tên chính thức (18 từ): "
    )
    add_body_paragraph(
        doc,
        "(1) Đối tượng: Sinh vật mô hình Drosophila melanogaster (ruồi giấm) trong bệnh lý Parkinson; "
        "(2) Phương pháp: Mô hình hóa cơ chế nơ-ron Leaky Integrate-and-Fire kết hợp điều khiển CPG "
        "và mô phỏng động lực học vật lý cơ sinh học 3D (NeuroMechFly/FlyGym); "
        "(3) Phạm vi: 7 mô hình đột biến gen và chuỗi tiến triển thoái hóa 30 ngày, xác nhận định lượng với y văn quốc tế.",
        bold_prefix="Phân tích cấu trúc danh pháp: ",
        italic=True
    )

    # ==========================================
    # 2. LÝ DO CHỌN ĐỀ TÀI / TÍNH CẤP THIẾT
    # ==========================================
    add_styled_heading(doc, "2. LÝ DO CHỌN ĐỀ TÀI / TÍNH CẤP THIẾT", level=1)
    
    add_styled_heading(doc, "2.1 Bối cảnh thực tế và số liệu dịch tễ học", level=2)
    add_body_paragraph(
        doc,
        "Bệnh Parkinson (Parkinson's Disease - PD) là rối loạn thoái hóa thần kinh có tốc độ gia tăng nhanh nhất toàn cầu, "
        "hiện ảnh hưởng đến hơn 10 triệu người (Parkinson's Foundation, 2024). Theo phân tích gánh nặng bệnh tật Global Burden of Disease (GBD) "
        "Study 2021 được công bố trên The Lancet Neurology (2024), các quốc gia đang phát triển tại châu Á chịu áp lực rất lớn do tốc độ già hóa "
        "dân số tăng nhanh. Tại Việt Nam, các ước tính dịch tễ học chỉ ra khoảng 85.000 người đang chung sống với bệnh Parkinson. Các nghiên cứu lâm sàng "
        "và di truyền học năm 2023 trên bệnh nhân Parkinson khởi phát sớm tại Việt Nam đã xác định các đột biến gây bệnh chủ chốt trên các gen LRRK2, PRKN, và GBA."
    )
    add_body_paragraph(
        doc,
        "Để nghiên cứu cơ chế bệnh sinh và sàng lọc liệu pháp, ruồi giấm (Drosophila melanogaster) được sử dụng rộng rãi nhờ sở hữu khoảng 75% gen "
        "gây bệnh ở người có gen tương đồng chức năng (homolog), mạng lưới nơ-ron Dopamine được lập bản đồ chi tiết và vòng đời trưởng thành ngắn (30 ngày). "
        "Tuy nhiên, các đợt thực nghiệm sinh học truyền thống trên ruồi thật gặp phải 3 rào cản nghiêm trọng: (1) Chi phí và thời gian kéo dài (2–6 tháng nuôi cấy); "
        "(2) Độ biến thiên lớn giữa các phòng lab do điều kiện nuôi dưỡng khác biệt; (3) Khó khăn trong việc đo lường đồng thời động cơ học 3D đa khớp và phân đoạn bước chân."
    )

    add_styled_heading(doc, "2.2 Khoảng trống nghiên cứu (Systematic Gap Identification)", level=2)
    add_body_paragraph(
        doc,
        "Khảo sát có hệ thống trên PubMed, IEEE Xplore, Scopus và Semantic Scholar với các từ khóa ['Parkinson Drosophila computational simulation locomotion'] "
        "trong giai đoạn 2010–08/2026 xác nhận chưa có bất kỳ công trình nào giải quyết đồng thời 3 khoảng trống sau:"
    )
    add_bullet_point(
        doc,
        "Chưa có hệ thống tính toán nào tích hợp liền mạch từ tổn thương nơ-ron Dopamine mức phân tử đến mô hình LIF, điều biến máy phát mẫu trung tâm (CPG) "
        "và dẫn truyền tới 42 khớp cơ thể học 3D hoàn chỉnh.",
        bold_prefix="Gap 1 (Thiếu cầu nối đa tầng): "
    )
    add_bullet_point(
        doc,
        "Các mô hình tính toán cơ sinh học côn trùng tiên tiến (như Lobato-Rios et al., Nature Methods 2022) mới chỉ mô phỏng ruồi lành mạnh (wild-type), "
        "hoàn toàn thiếu vắng module bệnh lý và chưa từng được kiểm chứng định lượng so với số liệu thực nghiệm gốc.",
        bold_prefix="Gap 2 (Thiếu xác nhận định lượng y văn): "
    )
    add_bullet_point(
        doc,
        "Chưa có nghiên cứu in-silico nào tái hiện được quỹ đạo tiến triển thoái hóa vận động liên tục qua 30 ngày (Longitudinal Aging Trajectory) "
        "cho nhiều dòng đột biến và can thiệp giải cứu di truyền.",
        bold_prefix="Gap 3 (Thiếu mô hình tiến triển 30 ngày): "
    )

    # ==========================================
    # 3. TỔNG QUAN TÌNH HÌNH NGHIÊN CỨU
    # ==========================================
    add_styled_heading(doc, "3. TỔNG QUAN TÌNH HÌNH NGHIÊN CỨU (RELATED WORK)", level=1)
    
    add_styled_heading(doc, "3.1 Nhóm A: Mô hình cơ sinh học tính toán vận động côn trùng", level=2)
    add_body_paragraph(
        doc,
        "Nổi bật nhất là nền tảng NeuroMechFly (Lobato-Rios et al., 2022, Nature Methods) và NeuroMechFly v2 (Ramdya et al., 2024, eLife). "
        "Mô hình tái tạo cơ thể học Drosophila với 69 đoạn thân, 42 khớp chủ động trên engine vật lý MuJoCo với tốc độ tính toán >100x thời gian thực. "
        "Tuy nhiên, hạn chế cốt lõi là chỉ mô phỏng cá thể lành mạnh, chưa có mô hình bệnh lý thần kinh."
    )

    add_styled_heading(doc, "3.2 Nhóm B: Thực nghiệm hành vi Parkinson trên Drosophila (Ground-Truth Benchmarks)", level=2)
    add_body_paragraph(
        doc,
        "Cung cấp số liệu đối chuẩn thực nghiệm định lượng từ các bài báo peer-reviewed quốc tế:"
    )
    add_bullet_point(doc, "Park et al. (2006, Nature): Đột biến PINK1 làm giảm vận tốc >30% ở ruồi 25 ngày tuổi.", bold_prefix="PINK1 Null: ")
    add_bullet_point(doc, "Clark et al. (2006, Nature): Ghi nhận hiện tượng bù trừ vận động sớm (+12%) trước khi suy thoái.", bold_prefix="PINK1 Early: ")
    add_bullet_point(doc, "Yang et al. (2006, PNAS): Biểu hiện quá mức Parkin (Parkin OE) giải cứu thành công kiểu hình PINK1.", bold_prefix="Genetic Rescue: ")
    add_bullet_point(doc, "Greene et al. (2003, PNAS) & Liu et al. (2008, PNAS): Đột biến Parkin và LRRK2 làm tăng độ lệch hướng (>43%).", bold_prefix="Parkin & LRRK2: ")
    add_bullet_point(doc, "Meulener et al. (2005, Curr Bio) & Coulom (2004, J Neurosci): Mô hình DJ-1 và ức chế Complex I bằng Rotenone.", bold_prefix="DJ-1 & Complex I: ")
    add_bullet_point(doc, "Kajtor et al. (2025, eLife, DOI: 10.7554/eLife.90905): Phân tích phản ứng vận động và giảm tốc độ của Parkin mutant trước kích thích đe dọa.", bold_prefix="Parkin Threat Response: ")

    add_styled_heading(doc, "3.3 Nhóm C: Mô hình nơ-ron Integrate-and-Fire & Mạng CPG", level=2)
    add_body_paragraph(
        doc,
        "Mô hình nơ-ron Leaky Integrate-and-Fire (Gerstner & Kistler, 2002) và lý thuyết máy phát mẫu trung tâm (Ijspeert, 2008) "
        "kết hợp các phát hiện mới về mạch CPG 3-nơ-ron tối giản trong Ventral Nerve Cord (bioRxiv, 2025) cung cấp nền tảng toán học vững chắc "
        "cho tầng điều khiển bước chân trong nghiên cứu này."
    )

    # Table 3.4
    add_styled_heading(doc, "3.4 Bảng so sánh tổng hợp các hướng tiếp cận", level=2)
    comp_table = doc.add_table(rows=6, cols=5)
    comp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Công trình", "Phương pháp", "Dữ liệu đối chuẩn", "Xác nhận định lượng", "Chuỗi 30 ngày"]
    for j, h in enumerate(headers):
        cell = comp_table.rows[0].cells[j]
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, 80, 80, 80, 80)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(10)

    rows_data = [
        ("Lobato-Rios (2022)", "FlyGym (MuJoCo)", "DeepFly3D (WT)", "Không (chỉ WT)", "Không"),
        ("Ramdya (2024)", "NeuroMechFly v2", "Connectome VNC", "Không (chỉ WT)", "Không"),
        ("Park et al. (2006)", "Sinh học thực nghiệm", "Ruồi thật PINK1", "Có (thực nghiệm)", "Một phần"),
        ("Kajtor et al. (2025)", "Video tracking thật", "Ruồi thật Parkin", "Có (thực nghiệm)", "Không"),
        ("Đề tài đề xuất", "FlyGym + LIF + CPG", "Benchmark 9 bài báo", "Có (N=6 seeds, p<0.05)", "Có (21 mốc)"),
    ]

    for i, r_data in enumerate(rows_data, start=1):
        row = comp_table.rows[i]
        bg = "F9FAFC" if i % 2 == 1 else "FFFFFF"
        if i == 5:
            bg = "EBF3FA"
        for j, val in enumerate(r_data):
            cell = row.cells[j]
            set_cell_background(cell, bg)
            set_cell_margins(cell, 60, 60, 60, 60)
            p = cell.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(10)
            if i == 5:
                r.font.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================================
    # 4. MỤC TIÊU NGHIÊN CỨU
    # ==========================================
    add_styled_heading(doc, "4. MỤC TIÊU NGHIÊN CỨU", level=1)
    add_body_paragraph(
        doc,
        "Xây dựng và kiểm chứng một hệ thống sinh học tính toán đa tầng có khả năng tái hiện, phân tích và mô phỏng chính xác "
        "kiểu hình thoái hóa vận động Parkinson trên Drosophila melanogaster từ cấp độ đột biến gen đến động lực học cơ thể 3D, "
        "đạt độ tương đồng định lượng cao (>= 80%) với các công trình thực nghiệm quốc tế.",
        bold_prefix="4.1 Mục tiêu tổng quát: "
    )

    add_styled_heading(doc, "4.2 Mục tiêu cụ thể (SMART Goals) & Ma trận Ánh xạ", level=2)
    add_bullet_point(
        doc,
        "Xây dựng cơ sở dữ liệu tham số sinh học cho 7 mô hình đột biến gen (pink1, parkin, lrrk2, dj1, complexI, pink1_age25, pink1_parkin_OE_age25), "
        "ánh xạ chính xác cơ chế phân tử thành vector tỷ lệ nhiễu loạn nơ-ron (motor_scale, coupling_scale). [Map Mục 7.1 -> KQ1]",
        bold_prefix="MT1 (Tham số hóa gen): "
    )
    add_bullet_point(
        doc,
        "Đạt mức tương đồng định lượng cao (HIGH_QUANTITATIVE_CONCORDANCE, |Delta_sim - Delta_lit| <= 15%) trên tối thiểu 6/7 mô hình, "
        "đạt ý nghĩa thống kê p < 0.05 qua kiểm định Wilcoxon với N=6 seeds. [Map Mục 7.3–7.5 -> KQ2]",
        bold_prefix="MT2 (Xác nhận định lượng): "
    )
    add_bullet_point(
        doc,
        "Tái lập thành công quỹ đạo thoái hóa vận động 30 ngày (Longitudinal Aging Trajectory) với 21 điểm mô phỏng (3 nhánh x 7 mốc tuổi), "
        "mô tả rõ nét các giai đoạn bù trừ sớm, khởi phát thoái hóa và sụp đổ muộn. [Map Mục 7.6 -> KQ3]",
        bold_prefix="MT3 (Tiến triển 30 ngày): "
    )
    add_bullet_point(
        doc,
        "Xác lập bộ chỉ số phân đoạn nâng cao (Gait Duty Cycle, Pause Bout Count, Turning Asymmetry) chứng minh năng lực phân biệt rõ rệt "
        "(p < 0.05) giữa cá thể bệnh nặng và cá thể được giải cứu gen. [Map Mục 7.2, 7.7 -> KQ4]",
        bold_prefix="MT4 (Chỉ số mở rộng): "
    )

    # ==========================================
    # 5. ĐỐI TƯỢNG & PHẠM VI NGHIÊN CỨU
    # ==========================================
    add_styled_heading(doc, "5. ĐỐI TƯỢNG & PHẠM VI NGHIÊN CỨU", level=1)
    add_bullet_point(
        doc,
        "Hệ thống mô phỏng sinh học tính toán kết hợp FlyGym (NeuroMechFly v2.1.0) + MuJoCo 3.9.0 với bộ điều khiển CPG và cơ chế nhiễu loạn nơ-ron LIF.",
        bold_prefix="Đối tượng chính: "
    )
    add_bullet_point(
        doc,
        "7 mô hình đột biến gen và can thiệp giải cứu Parkinson trên Drosophila melanogaster.",
        bold_prefix="Đối tượng bệnh học: "
    )
    add_bullet_point(
        doc,
        "Giai đoạn trưởng thành Day 1 đến Day 30; tập trung vào hành vi vận động đi bộ trên mặt phẳng (locomotion on flat terrain). "
        "Không bao gồm hành vi bay bằng cánh, hành vi giao phối hoặc cảm thụ hóa học.",
        bold_prefix="Phạm vi sinh học: "
    )
    add_bullet_point(
        doc,
        "Mô phỏng cơ sinh học vật lý (biomechanical physical simulation); không mở rộng sang full connectome simulation toàn não.",
        bold_prefix="Phạm vi tính toán: "
    )
    add_bullet_point(
        doc,
        "(1) motor_scale là xấp xỉ vĩ mô của sự suy giảm dẫn truyền thần kinh; (2) Các điểm mốc trung gian (Day 10, 15, 20) trong chuỗi 30 ngày "
        "là ước tính nội suy có cơ sở toán học mang tính dự báo, không phải số liệu đo độc lập từ thực nghiệm.",
        bold_prefix="Giới hạn đã thừa nhận (Acknowledged Limitations): "
    )

    # ==========================================
    # 6. CÂU HỎI NGHIÊN CỨU / GIẢ THUYẾT
    # ==========================================
    add_styled_heading(doc, "6. CÂU HỎI NGHIÊN CỨU / GIẢ THUYẾT", level=1)
    add_body_paragraph(
        doc,
        "Pipeline kết nối đột biến gen -> tham số LIF -> nhiễu loạn CPG -> vận động vật lý có tái tạo được chiều hướng và độ lớn suy giảm vận động "
        "quan sát trong thực nghiệm cho cả 7 mô hình hay không?",
        bold_prefix="RQ1: "
    )
    add_body_paragraph(
        doc,
        "Tối thiểu 6/7 mô hình đạt sai số định lượng |Delta_sim - Delta_lit| <= 15% và đạt mức ý nghĩa thống kê p < 0.05 (Wilcoxon signed-rank test, N=6 seeds).",
        bold_prefix="-> Giả thuyết H1: ",
        italic=True
    )
    add_body_paragraph(
        doc,
        "Bộ chỉ số mở rộng (Gait Duty Cycle, Pause Bouts, Left-Right Asymmetry) có phân biệt được kiểu hình bệnh nặng (PINK1 Day 25) "
        "với kiểu hình cứu vãn (PINK1+Parkin OE Day 25) ở mức thống kê có ý nghĩa hay không?",
        bold_prefix="RQ2: "
    )
    add_body_paragraph(
        doc,
        "Tồn tại sự khác biệt có ý nghĩa thống kê (Wilcoxon p < 0.05) trên ít nhất 1 chỉ số mở rộng giữa hai nhóm (Ablation Abl-3).",
        bold_prefix="-> Giả thuyết H2: ",
        italic=True
    )
    add_body_paragraph(
        doc,
        "Đường cong tiến triển 30 ngày in-silico của PINK1 và nhóm Rescue phân kỳ định lượng từ mốc tuổi nào so với nhóm lành mạnh?",
        bold_prefix="RQ3: "
    )
    add_body_paragraph(
        doc,
        "Thí nghiệm Ablation Abl-2 (thay tham số sinh học bằng giá trị ngẫu nhiên) có làm sụp đổ độ tương đồng y văn hay không?",
        bold_prefix="RQ4: "
    )
    add_body_paragraph(
        doc,
        "Cấu hình ngẫu nhiên chỉ đạt < 30% HIGH concordance so với 100% của cấu hình có cơ sở phân tử, chứng minh tính độc lập và phi ngẫu nhiên của mô hình.",
        bold_prefix="-> Giả thuyết H4: ",
        italic=True
    )

    # ==========================================
    # 7. PHƯƠNG PHÁP NGHIÊN CỨU
    # ==========================================
    add_styled_heading(doc, "7. PHƯƠNG PHÁP NGHIÊN CỨU", level=1)
    
    add_styled_heading(doc, "7.1 Kiến trúc Pipeline 4 Tầng & Tính Độc Lập Tham Số", level=2)
    add_body_paragraph(
        doc,
        "Hệ thống vận hành theo kiến trúc 4 tầng khép kín:"
    )
    add_bullet_point(doc, "Layer 1 (Gene-to-Neuron Bridge): Ánh xạ từ gen đột biến và mức tổn thương tế bào sang motor_scale và coupling_scale.")
    add_bullet_point(doc, "Layer 2 (LIF & CPG Controller): Điều biến phương trình vi phân pha CPG và biên độ điều khiển góc khớp.")
    add_bullet_point(doc, "Layer 3 (Embodied Physical Simulation): Thực thi mô phỏng vật lý 5.0s (50.000 bước tích phân Runge-Kutta dt=0.0001s).")
    add_bullet_point(doc, "Layer 4 (Quantitative Validation & Statistics): Trích xuất 9 chỉ số, kiểm định Wilcoxon N=6 seeds và so khớp y văn.")
    add_body_paragraph(
        doc,
        "Chứng minh tính độc lập (Phòng tránh Circular Reasoning): motor_scale được suy ra hoàn toàn từ dữ liệu nơ-ron/sinh học phân tử "
        "(tỷ lệ tế bào DA sống sót, tổn thương ty thể); trong khi dữ liệu xác nhận là vận tốc và góc lệch hướng đo từ chuyển động cơ học 3D. "
        "Hai nguồn dữ liệu hoàn toàn độc lập về phương pháp đo và bản chất vật lý.",
        bold_prefix="Lưu ý then chốt: ",
        italic=True
    )

    add_styled_heading(doc, "7.2 Bộ 9 Chỉ số Vận động Chuẩn hóa", level=2)
    add_bullet_point(doc, "mean_planar_speed_mm_s (Vận tốc trung bình mặt phẳng, mm/s)")
    add_bullet_point(doc, "planar_displacement_mm (Độ dời vị trí ngực, mm)")
    add_bullet_point(doc, "planar_path_length_mm (Tổng chiều dài quãng đường, mm)")
    add_bullet_point(doc, "trajectory_efficiency (Hiệu suất quỹ đạo = Độ dời / Chiều dài đường đi)")
    add_bullet_point(doc, "body_height_mean_mm (Độ cao thân trung bình, mm)")
    add_bullet_point(doc, "heading_yaw_change_rad (Biến thiên góc quay Yaw tích lũy, rad)")
    add_bullet_point(doc, "walking_duty_cycle (Tỷ lệ thời gian di chuyển, %)")
    add_bullet_point(doc, "pause_bout_count (Số đợt dừng vận động liên tục)")
    add_bullet_point(doc, "left_right_asymmetry (Độ bất đối xứng vận tốc góc quay trái - phải, rad/s)")

    add_styled_heading(doc, "7.3 Phân loại Concordance và Cơ sở Chọn Ngưỡng 15%", level=2)
    add_body_paragraph(
        doc,
        "Ngưỡng sai số định lượng |Delta_sim - Delta_lit| <= 15% (HIGH_CONCORDANCE) được thiết lập dựa trên: "
        "(1) Độ biến thiên sinh học nội tại giữa các cá thể ruồi trong thực nghiệm (inter-individual variability ~ 10–20%); "
        "(2) Độ không chắc chắn trong ước lượng tham số nơ-ron (+-5–10%). Do đó, ngưỡng 15% là tiêu chuẩn dung sai khoa học bảo thủ và hợp lý."
    )

    add_styled_heading(doc, "7.4 Thiết kế Thực nghiệm Đa Hạt Giống (N=6 Seeds)", level=2)
    add_body_paragraph(
        doc,
        "Để đạt mức ý nghĩa thống kê p < 0.05 trong kiểm định Wilcoxon signed-rank test hai phía, hệ thống chuẩn hóa danh sách N=6 seeds "
        "[42, 123, 456, 789, 1024, 2026] (vì với N=5, p_min = 0.0625 > 0.05; với N=6, p_min = 0.03125 < 0.05). "
        "Mỗi mô hình được tính toán giá trị Mean +- SD và p-value tương ứng."
    )

    add_styled_heading(doc, "7.5 Thiết kế Chuỗi Thời gian 30 Ngày & Ablation Study", level=2)
    add_body_paragraph(
        doc,
        "Xây dựng 21 điểm mốc thời gian (3 nhánh x 7 ngày: D01, D05, D10, D15, D20, D25, D30) theo hàm suy thoái hàm mũ. "
        "Triển khai 3 thí nghiệm Ablation: Abl-1 (loại trừ CPG coupling), Abl-2 (nhiễu loạn ngẫu nhiên), Abl-3 (độ nhạy bộ chỉ số mở rộng)."
    )

    # ==========================================
    # 8. KẾ HOẠCH THỰC HIỆN (TIMELINE 8 THÁNG)
    # ==========================================
    add_styled_heading(doc, "8. KẾ HOẠCH THỰC HIỆN (TIMELINE 8 THÁNG / 32 TUẦN)", level=1)
    
    time_table = doc.add_table(rows=8, cols=4)
    time_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_headers = ["Giai đoạn", "Thời gian", "Nội dung nhiệm vụ & Sản phẩm bàn giao", "Cột mốc Đánh giá"]
    for j, h in enumerate(t_headers):
        cell = time_table.rows[0].cells[j]
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, 80, 80, 80, 80)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(10)

    t_data = [
        ("GĐ 1: Lý thuyết", "Tuần 1–3", "Khảo sát systematic, trích xuất tham số 7 dòng gen -> 7 bridge JSONs.", "Checkpoint 1 (Duyệt lý thuyết)"),
        ("GĐ 2: Core Pipeline", "Tuần 4–7", "Hoàn thiện pipeline 4 tầng, module 9 metrics, N=6 seeds -> 14 unit tests pass.", "—"),
        ("GĐ 3: Mô phỏng 7 model", "Tuần 8–11", "Chạy 7x6=42 mô phỏng Colab GPU, render video 3D, chạy Abl-1 & Abl-2.", "Checkpoint 2 (Duyệt mô phỏng 7 model)"),
        ("GĐ 4: Xác nhận Y văn", "Tuần 12–14", "Tính Concordance, kiểm định Wilcoxon p<0.05 -> Báo cáo Validation.", "—"),
        ("GĐ 5: Chuỗi 30 ngày", "Tuần 15–17", "Chạy 21x6=126 mô phỏng chuỗi 30 ngày, xuất CSV decay curve, chạy Abl-3.", "Checkpoint 3 (Duyệt kết quả 30 ngày)"),
        ("GĐ 6a: Đóng gói", "Tuần 18–21", "Hoàn thiện tài liệu kỹ thuật, public GitHub repo chuẩn CI/CD.", "—"),
        ("GĐ 6b: Viết bài báo", "Tuần 22–28", "Soạn thảo bài báo IEEE (6–8 trang), chuẩn bị nộp hội nghị quốc tế (KSE).", "Checkpoint 4 (Duyệt bài báo hoàn chỉnh)"),
    ]

    for i, r_data in enumerate(t_data, start=1):
        row = time_table.rows[i]
        bg = "F9FAFC" if i % 2 == 1 else "FFFFFF"
        for j, val in enumerate(r_data):
            cell = row.cells[j]
            set_cell_background(cell, bg)
            set_cell_margins(cell, 60, 60, 60, 60)
            p = cell.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(10)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================================
    # 9. KẾT QUẢ DỰ KIẾN
    # ==========================================
    add_styled_heading(doc, "9. KẾT QUẢ DỰ KIẾN", level=1)
    add_bullet_point(doc, "Bộ cơ sở dữ liệu tham số 7 dòng đột biến PD có trích dẫn DOI y văn đầy đủ, 100% test pass. [KQ1]", bold_prefix="Sản phẩm 1: ")
    add_bullet_point(doc, "Báo cáo xác nhận định lượng đạt >= 6/7 mô hình HIGH_CONCORDANCE và Wilcoxon p < 0.05 với N=6 seeds. [KQ2]", bold_prefix="Sản phẩm 2: ")
    add_bullet_point(doc, "Bộ dữ liệu chuỗi thoái hóa 30 ngày (21 mốc x 6 seeds) và đồ thị đường cong suy thoái. [KQ3]", bold_prefix="Sản phẩm 3: ")
    add_bullet_point(doc, "Báo cáo Ablation Study chứng minh năng lực phân biệt vượt trội của bộ chỉ số mở rộng. [KQ4]", bold_prefix="Sản phẩm 4: ")
    add_bullet_point(doc, "Kho mã nguồn mở (GitHub Repository) hoàn chỉnh kèm pipeline kiểm thử tự động CI/CD và Google Colab bundle. [KQ5]", bold_prefix="Sản phẩm 5: ")
    add_bullet_point(doc, "01 Bài báo khoa học hoàn chỉnh chuẩn IEEE nộp Hội nghị Khoa học Quốc tế (KSE/ACIIDS). [KQ6]", bold_prefix="Sản phẩm 6: ")

    # ==========================================
    # 10. Ý NGHĨA KHOA HỌC VÀ THỰC TIỄN
    # ==========================================
    add_styled_heading(doc, "10. Ý NGHĨA KHOA HỌC VÀ THỰC TIỄN", level=1)
    add_body_paragraph(
        doc,
        "Thiết lập framework tính toán đa tầng đầu tiên kết nối cơ chế phân tử gen PD với động lực học vận động 3D có kiểm chứng định lượng; "
        "cung cấp bộ dữ liệu benchmark mở cho cộng đồng nghiên cứu; tạo ra các dự đoán kiểm chứng được (testable predictions) cho sinh học thực nghiệm.",
        bold_prefix="Ý nghĩa Khoa học: "
    )
    add_body_paragraph(
        doc,
        "Tiết kiệm chi phí và thời gian thực nghiệm (chạy mô phỏng 7 model trong 20 phút trên Colab thay vì 2–6 tháng nuôi ruồi thật); "
        "cung cấp công cụ tiền sàng lọc giả thuyết dược lý cho các lab tại Việt Nam; ứng dụng trong giảng dạy Sinh tin học và Computational Neuroscience.",
        bold_prefix="Ý nghĩa Thực tiễn: "
    )

    # ==========================================
    # 11. TÀI LIỆU THAM KHẢO
    # ==========================================
    add_styled_heading(doc, "11. TÀI LIỆU THAM KHẢO (CHUẨN IEEE)", level=1)
    refs = [
        "[1] J. Park, S. B. Lee, S. Lee, Y. Kim, S. Song, S. Kim, E. Bae, J. Kim, M. Shong, J. M. Chung, and J. Chung, "
        "\"Mitochondrial dysfunction in Drosophila PINK1 mutants is complemented by parkin,\" Nature, vol. 441, no. 7097, pp. 1157–1161, 2006. DOI: 10.1038/nature04788.",
        "[2] I. E. Clark, M. W. Dodson, C. Jiang, J. H. Cao, J. R. Huh, J. H. Seol, S. J. Yoo, M. D. Hay, and M. Guo, "
        "\"Drosophila pink1 is required for mitochondrial function and interacts genetically with parkin,\" Nature, vol. 441, no. 7097, pp. 1162–1166, 2006. DOI: 10.1038/nature04779.",
        "[3] Y. Yang, S. Gehrke, Y. Imai, Z. Huang, Y. Ouyang, J. W. Wang, L. Yang, M. F. Beal, H. Vogel, and B. Lu, "
        "\"Mitochondrial pathology and muscle and dopaminergic neuron degeneration caused by inactivation of Drosophila Pink1 is rescued by Parkin,\" Proc. Natl. Acad. Sci., vol. 103, no. 28, pp. 10793–10798, 2006. DOI: 10.1073/pnas.0602493103.",
        "[4] J. C. Greene, A. J. Whitworth, I. Kuo, L. A. Andrews, M. B. Feany, and L. J. Pallanck, "
        "\"Mitochondrial pathology and apoptotic muscle degeneration in Drosophila parkin mutants,\" Proc. Natl. Acad. Sci., vol. 100, no. 7, pp. 4078–4083, 2003. DOI: 10.1073/pnas.0737556100.",
        "[5] Z. Liu, X. Wang, Y. Yu, X. Li, T. Wang, H. Jiang, Q. Ren, Y. Jiao, A. Sawa, T. Moran, C. A. Ross, and W. W. Smith, "
        "\"A Drosophila model for LRRK2-linked parkinsonism,\" Proc. Natl. Acad. Sci., vol. 105, no. 7, pp. 2693–2698, 2008. DOI: 10.1073/pnas.0708452105.",
        "[6] M. Meulener, A. J. Whitworth, C. E. Armstrong-Gold, P. Rizzu, P. Heutink, P. D. Wes, L. J. Pallanck, and N. M. Bonini, "
        "\"Drosophila DJ-1 mutants are selectively sensitive to environmental toxins associated with Parkinson's disease,\" Current Biology, vol. 15, no. 17, pp. 1572–1577, 2005. DOI: 10.1016/j.cub.2005.07.064.",
        "[7] T. Riemensperger, T. Issa, U. Pech, H. Coulom, M. V. Nguyen, M. M. Cassar, M. Jacquet, M. Fiala, and S. Birman, "
        "\"A single dopamine pathway underlies progressive locomotor deficits in a Drosophila model of Parkinson disease,\" Cell Reports, vol. 5, no. 4, pp. 952–960, 2013. DOI: 10.1016/j.celrep.2013.10.032.",
        "[8] H. Coulom and S. Birman, \"Chronic exposure to rotenone models sporadic Parkinson's disease in Drosophila melanogaster,\" J. Neuroscience, vol. 24, no. 48, pp. 10993–10998, 2004. DOI: 10.1523/JNEUROSCI.2993-04.2004.",
        "[9] V. Lobato-Rios, S. T. Ramalingasetty, P. G. LoFaro, J. Arreguit, A. J. Ijspeert, and P. Ramdya, "
        "\"NeuroMechFly, a neuromechanical model of adult Drosophila melanogaster,\" Nature Methods, vol. 19, no. 5, pp. 620–627, 2022. DOI: 10.1038/s41592-022-01466-7.",
        "[10] P. Ramdya et al., \"NeuroMechFly v2: Embodied sensorimotor modeling of Drosophila motor control,\" eLife, 2024.",
        "[11] M. Kajtor, V. A. Billes, B. Király, P. Karkusova, T. Kovács, H. Stabb, K. Sviatkó, A. Vizi, E. Ujvári, D. Balázsfi, S. E. Seidenbecher, D. Kvitsiani, T. Vellai, and B. Hangya, "
        "\"Altered reactivity to threatening stimuli in Drosophila models of Parkinson's disease, revealed by a trial-based assay,\" eLife, vol. 14, p. e90905, Jul. 2025. DOI: 10.7554/eLife.90905.",
        "[12] N. S. Szczecinski, A. J. Hunt, and R. D. Quinn, \"A functional subnetwork approach to designing synthetic nervous systems that control legged robot locomotion,\" Front. Neurorobotics, vol. 11, p. 37, 2017. DOI: 10.3389/fnbot.2017.00037.",
        "[13] A. J. Ijspeert, \"Central pattern generators for locomotion control in animals and robots: A review,\" Neural Networks, vol. 21, no. 4, pp. 642–653, 2008. DOI: 10.1016/j.neunet.2008.03.014.",
        "[14] GBD 2021 Nervous System Disorders Collaborators, \"Global, regional, and national burden of disorders affecting the nervous system, 1990–2021: a systematic analysis for the Global Burden of Disease Study 2021,\" The Lancet Neurology, vol. 23, no. 4, pp. 344–381, 2024. DOI: 10.1016/S1474-4422(24)00038-3.",
    ]
    for r in refs:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(r)
        run.font.name = "Times New Roman"
        run.font.size = Pt(11)

    # ==========================================
    # 12. DỰ TRÙ KINH PHÍ
    # ==========================================
    add_styled_heading(doc, "12. DỰ TRÙ KINH PHÍ & NGUỒN LỰC", level=1)
    
    bud_table = doc.add_table(rows=6, cols=3)
    bud_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    b_headers = ["Hạng mục chi phí", "Nội dung chi tiết", "Dự toán (VNĐ)"]
    for j, h in enumerate(b_headers):
        cell = bud_table.rows[0].cells[j]
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, 80, 80, 80, 80)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(10)

    b_data = [
        ("Hạ tầng tính toán Cloud", "Google Colab Pro+ GPU phục vụ chạy N=6 seeds và render video 3D", "1.200.000"),
        ("Tài liệu & CSDL", "Truy cập cơ sở dữ liệu bài báo chuyên ngành", "1.500.000"),
        ("Lệ phí công bố", "Lệ phí nộp và báo cáo tại Hội nghị Khoa học Quốc tế", "2.500.000"),
        ("In ấn & Văn phòng phẩm", "In đề cương màu, poster và báo cáo nghiệm thu", "800.000"),
        ("Dự phòng phát sinh (10%)", "Chi phí kỹ thuật và lưu trữ phát sinh", "600.000"),
    ]

    for i, r_data in enumerate(b_data, start=1):
        row = bud_table.rows[i]
        bg = "F9FAFC" if i % 2 == 1 else "FFFFFF"
        for j, val in enumerate(r_data):
            cell = row.cells[j]
            set_cell_background(cell, bg)
            set_cell_margins(cell, 60, 60, 60, 60)
            p = cell.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(10)

    p_tot = doc.add_paragraph()
    p_tot.paragraph_format.space_before = Pt(6)
    r_tot = p_tot.add_run("TỔNG KINH PHÍ DỰ KIẾN: 6.600.000 VNĐ (Sáu triệu sáu trăm nghìn đồng)")
    r_tot.font.bold = True
    r_tot.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    # ==========================================
    # PHỤ LỤC: 3 ĐIỂM YẾU NHẤT & HƯỚNG BỔ SUNG
    # ==========================================
    add_styled_heading(doc, "PHỤ LỤC: 3 ĐIỂM YẾU NHẤT CỦA ĐỀ CƯƠNG (TỰ ĐÁNH GIÁ ĐỂ HOÀN THIỆN)", level=1)
    add_bullet_point(
        doc,
        "Vấn đề: Các điểm neo trung gian (Day 10, 15, 20) được nội suy từ Day 1 và Day 25 theo hàm mũ thoái hóa, chưa có thực nghiệm đo liên tục 7 mốc.\n"
        "-> Hướng xử lý: Trình bày đây là mô hình dự đoán (predictive & testable) tạo tiền đề cho thực nghiệm tương lai kiểm chứng, không nhận vơ là số liệu đo được.",
        bold_prefix="1. Tính xác thực của các điểm trung gian 30 ngày: "
    )
    add_bullet_point(
        doc,
        "Vấn đề: Mặc dù đã dùng N=6 seeds để đạt p < 0.05 trên Wilcoxon, số lượng mẫu trong mô phỏng vật lý có thể mở rộng lên N=20 seeds để tăng sức mạnh thống kê.\n"
        "-> Hướng xử lý: Tận dụng GPU Colab Pro+ để mở rộng lên N=20 seeds trong giai đoạn chạy thực nghiệm chính thức.",
        bold_prefix="2. Kích thước mẫu hạt giống mô phỏng (Sample Size N=6): "
    )
    add_bullet_point(
        doc,
        "Vấn đề: Cầu nối Layer 1 mới là xấp xỉ mức nơ-ron truyền xuống (Descending Neurons), chưa mô hình hóa nồng độ dopamine tại từng khe synap cụ thể.\n"
        "-> Hướng xử lý: Xác định rõ đây là Acknowledged Limitation và đặt mục tiêu tích hợp FlyWire synaptic connectome cho giai đoạn sau đề tài.",
        bold_prefix="3. Chưa mô phỏng mức nồng độ chất dẫn truyền thần kinh synap: "
    )

    OUTPUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUTPUT_DOCX))
    print(f"[SUCCESS] Generated DOCX at: {OUTPUT_DOCX}")


if __name__ == "__main__":
    build_proposal_docx()
