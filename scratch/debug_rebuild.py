import csv
import re

mfomt_by_hex = {}
with open('j:\\Repositorios\\fomt_studio\\Nucleos_de_Procesamiento\\data\\lib_mfomt.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        if len(row) < 4: continue
        hex_id = row[1].upper().strip()
        name = row[3].strip()
        args = row[4].strip() if len(row) > 4 else ""
        mfomt_by_hex[hex_id] = (name, args)

print(f"0x030 in mfomt_by_hex: {'0x030' in mfomt_by_hex}")
if '0x030' in mfomt_by_hex:
    print(f"Value: {mfomt_by_hex['0x030']}")
    
fomt_to_mfomt_data = {}
with open('j:\\Repositorios\\fomt_studio\\Cruce referencia fomt a Mfomt.csv', 'r', encoding='utf-8') as f:
    for line in f:
        parts = line.split(',')
        if len(parts) < 2: continue
        
        fomt_str = parts[0].strip()
        match = re.search(r'(0x[0-9A-Fa-f]+)', fomt_str)
        if not match: continue
        fomt_hex = match.group(1).upper()
        
        mfomt_str = parts[1].strip()
        
        mfomt_data = None
        m2 = re.search(r'(?:Proc|Func|Unk)([0-9A-Fa-f]{3})', mfomt_str, re.IGNORECASE)
        if m2:
            m_hex = "0x" + m2.group(1).upper()
            if m_hex in mfomt_by_hex:
                mfomt_data = mfomt_by_hex[m_hex]
                
        if mfomt_data:
            fomt_to_mfomt_data[fomt_hex] = mfomt_data

print(f"0x02F in fomt_to_mfomt_data: {'0x02F' in fomt_to_mfomt_data}")
if '0x02F' in fomt_to_mfomt_data:
    print(f"Value: {fomt_to_mfomt_data['0x02F']}")
