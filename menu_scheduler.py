import sys
import os

print("=== BASIC TEST ===", file=sys.stderr)
print(f"Current directory: {os.getcwd()}", file=sys.stderr)
print("Files in directory:", file=sys.stderr)
print(os.listdir('.'), file=sys.stderr)

try:
    print("Trying to open config.yaml...", file=sys.stderr)
    with open('config.yaml', 'r') as f:
        print("Config contents:", file=sys.stderr)
        print(f.read(), file=sys.stderr)
except Exception as e:
    print(f"Error reading config: {str(e)}", file=sys.stderr)