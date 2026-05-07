import csv
import os

csv_path = r'j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_mfomt.csv'

with open(csv_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

header = lines[0]
new_lines = [header]
changes = []

for i, line in enumerate(lines[1:], 1):
    if not line.strip():
        new_lines.append(line)
        continue
    
    parts = line.strip().split(',')
    if len(parts) < 4:
        new_lines.append(line)
        continue
    
    type_col = parts[0]
    hex_id_col = parts[1]
    name_col = parts[3]
    
    is_placeholder = False
    if name_col.startswith('Proc') or name_col.startswith('Func'):
        is_placeholder = True
    
    if is_placeholder:
        clean_hex = hex_id_col.replace('0x', '').upper()
        # Handle cases where hex_id might be decimal or missing 0x
        try:
            if not hex_id_col.startswith('0x'):
                clean_hex = hex(int(hex_id_col)).replace('0x', '').upper()
        except:
            pass
            
        new_name = ("Proc" if type_col == "proc" else "Func") + clean_hex
        if name_col != new_name:
            changes.append(f"Line {i+1}: {name_col} -> {new_name}")
            parts[3] = new_name
            new_lines.append(",".join(parts) + "\n")
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

if changes:
    print("\n".join(changes))
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        f.writelines(new_lines)
else:
    print("No changes needed.")
