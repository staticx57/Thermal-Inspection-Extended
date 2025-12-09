
import sys
import traceback

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")

try:
    import pyqtgraph
    print(f"PyQtGraph imported successfully: {pyqtgraph.__file__}")
except ImportError:
    print("Failed to import pyqtgraph")
    traceback.print_exc()
except Exception:
    print("An unexpected error occurred during import")
    traceback.print_exc()
