import csv
import re
import os

def rebuild():
    # 1. Load lib_mfomt.csv
    mfomt_by_hex = {}
    mfomt_by_name = {}
    
    with open('j:\\Repositorios\\fomt_studio\\Nucleos_de_Procesamiento\\data\\lib_mfomt.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header_mfomt = next(reader)
        for row in reader:
            if len(row) < 4: continue
            hex_id = row[1].lower().strip() # e.g. 0x002
            name = row[3].strip()
            args = row[4].strip() if len(row) > 4 else ""
            mfomt_by_hex[hex_id] = (name, args)
            mfomt_by_name[name] = (name, args)
            
    # 2. Parse Cruce
    fomt_to_mfomt_data = {}
    with open('j:\\Repositorios\\fomt_studio\\Cruce referencia fomt a Mfomt.csv', 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.split(',')
            if len(parts) < 2: continue
            
            fomt_str = parts[0].strip() # e.g. proc0x02F
            match = re.search(r'(0x[0-9A-Fa-f]+)', fomt_str, re.IGNORECASE)
            if not match: continue
            fomt_hex = match.group(1).lower()
            
            mfomt_str = parts[1].strip() # e.g. Proc030, Func0A2, TalkChoice2
            
            # Find matching MFOMT data
            mfomt_data = None
            if mfomt_str in mfomt_by_name:
                mfomt_data = mfomt_by_name[mfomt_str]
            else:
                # Try to extract hex from ProcXXX, FuncXXX, UnkXXX
                m2 = re.search(r'(?:Proc|Func|Unk)([0-9A-Fa-f]{3})', mfomt_str, re.IGNORECASE)
                if m2:
                    m_hex = "0x" + m2.group(1).lower()
                    if m_hex in mfomt_by_hex:
                        mfomt_data = mfomt_by_hex[m_hex]
                        
            if mfomt_data:
                fomt_to_mfomt_data[fomt_hex] = mfomt_data
                
    # 3. Apply to lib_fomt.csv
    output_rows = []
    with open('j:\\Repositorios\\fomt_studio\\Nucleos_de_Procesamiento\\data\\lib_fomt.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header_fomt = next(reader)
        output_rows.append(header_fomt)
        
        for row in reader:
            if len(row) < 4: 
                output_rows.append(row)
                continue
                
            hex_id = row[1].lower().strip()
            if hex_id in fomt_to_mfomt_data:
                new_name, new_args = fomt_to_mfomt_data[hex_id]
                
                # Only replace if new name is NOT generic, OR current name IS generic
                current_name = row[3]
                is_current_generic = bool(re.match(r'^(Proc|Func|Unk)[0-9A-Fa-f]{3}$', current_name, re.IGNORECASE))
                is_new_generic = bool(re.match(r'^(Proc|Func|Unk)[0-9A-Fa-f]{3}$', new_name, re.IGNORECASE))
                
                if (not is_new_generic) or is_current_generic:
                    row[3] = new_name
                    if new_args:
                        row[4] = new_args
            output_rows.append(row)
            
    # Write back
    with open('j:\\Repositorios\\fomt_studio\\Nucleos_de_Procesamiento\\data\\lib_fomt.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(output_rows)
        
    print(f"Mapped {len(fomt_to_mfomt_data)} entries.")

if __name__ == '__main__':
    rebuild()
