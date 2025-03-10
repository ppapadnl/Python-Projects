from cx_Freeze import setup, Executable
setup(
    name="WirelessScannerPypp",
    version=0.1,
    description="WirelessScanner2Π",
    executables=[Executable("main.py", base="Win32GUI")],
)
