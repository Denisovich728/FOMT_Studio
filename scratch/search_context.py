import os
import re

event_dir = r"j:\Repositorios\fomt_studio\scratch\event_dump"
pattern = r'0x28' # Cambiar segn necesidad

for file in os.listdir(event_dir):
    if file.endswith(".txt"):
        with open(os.path.join(event_dir, file), 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    print(f"--- Context in {file} (line {i+1}) ---")
                    start = max(0, i-5)
                    end = min(len(lines), i+6)
                    for j in range(start, end):
                        print(f"{j+1}: {lines[j].strip()}")
