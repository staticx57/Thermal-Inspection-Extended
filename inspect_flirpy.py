
try:
    from flirpy.camera.boson import Boson
    print("Flirpy Boson methods:")
    for method in dir(Boson):
        if not method.startswith("__"):
            print(method)
except ImportError:
    print("flirpy not installed")
except Exception as e:
    print(f"Error: {e}")
