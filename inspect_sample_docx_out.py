import zipfile
import os
from xml.etree import ElementTree as ET

output_lines = []
files = [
    "sample/FM-EN-180- LOADER.docx",
    "sample/FM-EN-181- TRUCKS.docx",
]
for fn in files:
    path = os.path.normpath(fn)
    output_lines.append(f"FILE: {path}")
    if not os.path.exists(path):
        output_lines.append("  MISSING")
        continue
    with zipfile.ZipFile(path, "r") as z:
        if "word/document.xml" not in z.namelist():
            output_lines.append("  document.xml missing")
            continue
        xml = z.read("word/document.xml")
        root = ET.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        texts = [t.text for t in root.findall('.//w:t', ns) if t.text]
        txt = " ".join(texts)
        output_lines.append(txt[:5000])
        output_lines.append("---")

with open("sample_inspection_output.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))
