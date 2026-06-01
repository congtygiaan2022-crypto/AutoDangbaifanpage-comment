# -*- coding: utf-8 -*-
"""
Chay_Khong_CMD.pyw
------------------
Double-click file này để mở chương trình KHÔNG hiện cửa sổ CMD.
File .pyw được Windows chạy bằng pythonw.exe (ẩn console).
"""
import os, sys

# Force Python to use UTF-8 for all I/O
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE_DIR)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from gui import App

app = App()
app.mainloop()
