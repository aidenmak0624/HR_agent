#!/usr/bin/env python3
"""Quick diagnostic script"""

import sys
import os

print("🔍 Checking Flask Setup...\n")

# Check 1: Find main app file
print("1. Looking for Flask app file...")
possible_files = ["app.py", "main.py", "server.py", "run.py"]
app_file = None
for f in possible_files:
    if os.path.exists(f):
        app_file = f
        print(f"   ✅ Found: {f}")
        break

if not app_file:
    print("   ❌ No Flask app file found!")
    sys.exit(1)

# Check 2: Verify routes file
print("\n2. Checking agent routes...")
routes_file = "src/api/routes/agent_routes.py"
if os.path.exists(routes_file):
    print(f"   ✅ Found: {routes_file}")
else:
    print(f"   ❌ Missing: {routes_file}")
    sys.exit(1)

# Check 3: Check blueprint registration
print("\n3. Checking blueprint registration...")
with open(app_file, "r") as f:
    content = f.read()
    if "agent_routes" in content and "register_blueprint" in content:
        print("   ✅ Blueprint appears to be registered")
    else:
        print("   ❌ Blueprint not registered in app.py")
        print("\n   Add this to your app.py:")
        print("   " + "-" * 50)
        print("   from src.api.routes import agent_routes")
        print("   app.register_blueprint(agent_routes.bp)")
        print("   " + "-" * 50)

# Check 4: Test imports
print("\n4. Testing imports...")
try:
    from src.api.routes import agent_routes

    print("   ✅ Can import agent_routes")
except Exception as e:
    print(f"   ❌ Import failed: {e}")
    sys.exit(1)

print("\n✅ Setup looks good! Try starting the server:")
print(f"   python {app_file}")
