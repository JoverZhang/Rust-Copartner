import sys
import re

if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <old_prefix> <new_prefix>", file=sys.stderr)
    sys.exit(1)

old_prefix = sys.argv[1].rstrip("/") + "/"
new_prefix = sys.argv[2].rstrip("/") + "/"

for line in sys.stdin:
    if line.startswith("--- "):
        # --- old_prefix/... → --- a/...
        path = re.sub(rf'^---\s+{re.escape(old_prefix)}', '--- a/', line)
        path = path.split('\t')[0] + '\n'
        sys.stdout.write(path)
    elif line.startswith("+++ "):
        # +++ new_prefix/... → +++ b/...
        path = re.sub(rf'^\+\+\+\s+{re.escape(new_prefix)}', '+++ b/', line)
        path = path.split('\t')[0] + '\n'
        sys.stdout.write(path)
    else:
        sys.stdout.write(line)
