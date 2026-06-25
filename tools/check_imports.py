modules = ['torch', 'transformers', 'fitz', 'PIL', 'cv2', 'pytesseract']
import importlib
import sys

for m in modules:
    try:
        mod = importlib.import_module(m)
        ver = getattr(mod, '__version__', None)
        print(f"{m}: INSTALLED, version={ver}")
    except Exception as e:
        print(f"{m}: MISSING or import error: {e}")

# Also print pip-installed packages summary for requirements.txt mapping
try:
    import pkg_resources
    installed = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
    print('\n--- Summary: selected packages from pip list ---')
    for key in ['torch','transformers','pymupdf','pillow','opencv-python','pytesseract']:
        print(f"{key}: {installed.get(key)}")
except Exception:
    pass
