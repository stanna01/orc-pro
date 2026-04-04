import zipfile
import os
from xml.etree import ElementTree as ET

files = [
    "sample/FM-EN-180- LOADER.docx",
    "sample/FM-EN-181- TRUCKS.docx",
]

for fn in files:
    path = os.path.normpath(fn)
    print(f"FILE: {path}")
    if not os.path.exists(path):
        print("  MISSING")
        continue
    with zipfile.ZipFile(path, "r") as z:
        if "word/document.xml" not in z.namelist():
            print("  document.xml missing")
            continue
        xml = z.read("word/document.xml")
        root = ET.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        texts = [t.text for t in root.findall('.//w:t', ns) if t.text]
        txt = " ".join(texts)
        print(txt[:2500])
        print("---")
