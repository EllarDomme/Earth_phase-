"""md2docx.py —— 把技术手册 md 转成 docx（标题/表格/代码块/引用/列表）"""
import os
import re
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

SRC = sys.argv[1] if len(sys.argv) > 1 else r"E:\DeskTop\地球\技术手册_地相图.md"
DST = sys.argv[2] if len(sys.argv) > 2 else r"E:\DeskTop\技术手册_地相图.docx"

doc = Document()

# 中文字体
style = doc.styles["Normal"]
style.font.name = "Microsoft YaHei"
style.font.size = Pt(10.5)
style.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")


def clean_xml(t):
    """去掉 XML 不接受的控制字符（\x00-\x08 等）"""
    return "".join(ch for ch in t if ch >= " " or ch == "\t")


def add_runs(p, text):
    """处理 **粗体**、`代码`"""
    for part in re.split(r"(\*\*.+?\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = p.add_run(clean_xml(part[2:-2]))
            r.bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = p.add_run(clean_xml(part[1:-1]))
            r.font.name = "Consolas"
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(0xB0, 0x30, 0x30)
        else:
            p.add_run(clean_xml(part))


lines = open(SRC, encoding="utf-8").read().splitlines()
i = 0
in_code = False
code_buf = []

while i < len(lines):
    ln = lines[i]
    s = ln.rstrip()

    # 代码块
    if s.startswith("```"):
        if in_code:
            for cl in code_buf:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(12)
                p.paragraph_format.space_after = Pt(0)
                r = p.add_run(clean_xml(cl) if cl.strip() else " ")
                r.font.name = "Consolas"
                r.font.size = Pt(8.5)
            code_buf = []
            in_code = False
        else:
            in_code = True
        i += 1
        continue
    if in_code:
        code_buf.append(ln)
        i += 1
        continue

    # 表格
    if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
        rows = []
        header = [c.strip() for c in s.strip("|").split("|")]
        rows.append(header)
        i += 2
        while i < len(lines) and lines[i].strip().startswith("|"):
            rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
            i += 1
        ncol = max(len(r) for r in rows)
        t = doc.add_table(rows=len(rows), cols=ncol)
        t.style = "Light Grid Accent 1"
        for ri, row in enumerate(rows):
            for ci in range(ncol):
                cell = t.cell(ri, ci)
                cell.text = ""
                p = cell.paragraphs[0]
                txt = row[ci] if ci < len(row) else ""
                add_runs(p, txt.replace("<br>", "\n"))
                for r in p.runs:
                    r.font.size = Pt(9)
                    if ri == 0:
                        r.bold = True
        doc.add_paragraph()
        continue

    # 标题
    m = re.match(r"^(#{1,4})\s+(.*)$", s)
    if m:
        lvl = len(m.group(1))
        h = doc.add_heading(level=min(lvl, 4))
        add_runs(h, m.group(2))
        for r in h.runs:
            r.font.name = "Microsoft YaHei"
            r.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        i += 1
        continue

    # 分隔线
    if re.match(r"^-{3,}$", s.strip()):
        i += 1
        continue

    # 引用
    if s.startswith(">"):
        txt = s.lstrip("> ").strip()
        if txt:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            add_runs(p, txt)
            for r in p.runs:
                r.italic = True
                r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        i += 1
        continue

    # 列表
    m = re.match(r"^\s*[-*]\s+(.*)$", s)
    if m:
        p = doc.add_paragraph(style="List Bullet")
        add_runs(p, m.group(1))
        i += 1
        continue
    m = re.match(r"^\s*(\d+)[.、]\s+(.*)$", s)
    if m:
        p = doc.add_paragraph(style="List Number")
        add_runs(p, m.group(2))
        i += 1
        continue

    # 普通段落
    if s.strip():
        p = doc.add_paragraph()
        add_runs(p, s)
    i += 1

doc.save(DST)
print("已生成 %s（%.0f KB）" % (DST, os.path.getsize(DST) / 1024))
