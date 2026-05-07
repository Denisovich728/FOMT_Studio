import csv
import os

def cleanup_lib():
    path = r'j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv'
    temp_path = path + '.tmp'
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
        
    cleaned_rows = []
    for row in rows:
        type_val = row['Type']
        hex_id = row['Hex_ID'] # e.g. 0x08D
        name = row['Name']
        
        # Extraer el ID hex puro (sin 0x y en mayúsculas)
        hex_pure = hex_id.replace('0x', '').upper()
        
        # Si el nombre es genérico (Proc/Func + algo)
        if name.startswith('Proc') or name.startswith('Func'):
            prefix = 'Proc' if type_val == 'proc' else 'Func'
            # Forzar que el nombre coincida con el hex_id real
            row['Name'] = f"{prefix}{hex_pure}"
        
        cleaned_rows.append(row)
        
    with open(temp_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)
        
    os.replace(temp_path, path)
    print("Cleanup complete.")

if __name__ == '__main__':
    cleanup_lib()
