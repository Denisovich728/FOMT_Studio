import csv
import os

csv_path = r'j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv'
temp_path = r'j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt_temp.csv'

with open(csv_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

header = lines[0]
new_lines = [header]

for line in lines[1:]:
    if not line.strip():
        new_lines.append(line)
        continue
    
    parts = line.strip().split(',')
    if len(parts) < 4:
        new_lines.append(line)
        continue
    
    type_col = parts[0]
    hex_id_col = parts[1] # e.g. 0x0FE
    name_col = parts[3]   # e.g. Proc101
    
    # Check if it's a placeholder
    is_placeholder = False
    if name_col.startswith('Proc') or name_col.startswith('Func'):
        # Usually placeholders are like Proc007, Func13A, etc.
        # If it's something like "Proc0FC", we want to ensure it matches hex_id_col
        is_placeholder = True
    
    if is_placeholder:
        # Get hex id without 0x
        clean_hex = hex_id_col.replace('0x', '').upper()
        # Pad to at least 3 chars if needed, or keep as is
        new_name = ("Proc" if type_col == "proc" else "Func") + clean_hex
        parts[3] = new_name
        new_lines.append(",".join(parts) + "\n")
    else:
        new_lines.append(line)

with open(csv_path, 'w', encoding='utf-8', newline='') as f:
    f.writelines(new_lines)

print("Normalization complete.")
