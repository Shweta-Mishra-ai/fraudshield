import os
import sys

# Ensure the root directory and dashboard directory are in the Python search path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Read and execute the modular dashboard app
dashboard_path = os.path.join(root_dir, "dashboard", "app.py")
with open(dashboard_path, "r", encoding="utf-8") as f:
    exec(f.read(), globals())
