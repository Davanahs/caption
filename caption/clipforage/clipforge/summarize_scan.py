import json

with open("caption_scan_results.json", "r") as f:
    results = json.load(f)

files_by_dir = {}
for path in results.keys():
    directory = path.split('\\')[0] if '\\' in path else '.'
    if directory not in files_by_dir:
        files_by_dir[directory] = []
    files_by_dir[directory].append(path)

print("--- SCAN SUMMARY ---")
for directory, paths in sorted(files_by_dir.items()):
    print(f"\n[{directory}]")
    for p in sorted(paths):
        print(f"  {p}")
