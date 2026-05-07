import os
import re
from collections import defaultdict

event_dir = r"j:\Repositorios\fomt_studio\scratch\event_dump"
flags = defaultdict(set)

for file in os.listdir(event_dir):
    if file.startswith("event_") and file.endswith(".txt"):
        with open(os.path.join(event_dir, file), 'r', encoding='utf-8') as f:
            content = f.read()
            # Buscar Check_Flag(x)
            for match in re.finditer(r'Check_Flag\((.*?)\)', content):
                val = match.group(1).strip()
                try:
                    if val.startswith('0x'):
                        num = int(val, 16)
                    else:
                        num = int(val)
                    flags[num].add("checked")
                except:
                    pass
            # Buscar Set_Flag(x, y)
            for match in re.finditer(r'Set_Flag\((.*?),\s*(.*?)\)', content):
                val = match.group(1).strip()
                v2 = match.group(2).strip()
                try:
                    if val.startswith('0x'):
                        num = int(val, 16)
                    else:
                        num = int(val)
                    flags[num].add(v2)
                except:
                    pass

with open(r"j:\Repositorios\fomt_studio\scratch\flags_extracted.csv", 'w', encoding='utf-8') as f:
    f.write("flag_id,values\n")
    for k in sorted(flags.keys()):
        f.write(f"{hex(k)},{'|'.join(flags[k])}\n")
print(f"Extracted {len(flags)} flags")
