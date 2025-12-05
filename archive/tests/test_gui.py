import sys
from PyQt6.QtWidgets import QApplication
from inspection_gui_qt import InspectionAppWindow

app = QApplication(sys.argv)
print('Creating window...')
try:
    window = InspectionAppWindow(None)
    print(f'Success! Tabs: {window.right_panel_tabs.count()}')
    print(f'Analysis subtabs: {window.analysis_tabs.count()}')
    print(f'Camera subtabs: {window.cameras_tabs.count()}')
    window.show()
    print('Window shown')
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
