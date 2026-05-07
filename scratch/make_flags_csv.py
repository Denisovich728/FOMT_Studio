import csv

extracted = {}
with open(r"j:\Repositorios\fomt_studio\scratch\flags_extracted.csv", 'r', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        extracted[int(row['flag_id'], 16)] = row['values'].split('|')

known_names = {
    0: "System_DayOfWeek",
    1: "System_Season",
    2: "System_DayOfMonth",
    3: "System_Hour",
    4: "System_Minute",
    5: "System_Weather_Tomorrow",
    6: "System_Weather_Today",
    0x1E: "Stocking_Event_Active",
    0x1F: "Stocking_Item_Given"
}

with open(r"j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\flags.csv", 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['flag_id', 'Flag_name', 'type_value'])
    for fid in sorted(extracted.keys()):
        vals = extracted[fid]
        
        if fid in known_names:
            name = known_names[fid]
        else:
            name = f"Flag_{hex(fid).upper().replace('0X', '0x')}"
            
        # Determinar el tipo
        val_set = set(vals)
        val_set.discard("checked")
        
        is_binary = True
        for v in val_set:
            try:
                num = int(v, 16) if v.startswith("0x") else int(v)
                if num not in [0, 1, 2]: # Muchas flags binarias se setean a 2 en FOMT para indicar "ya completado"
                    is_binary = False
            except:
                is_binary = False
                
        type_val = "binary" if is_binary else "state"
        if len(val_set) > 3:
            type_val = "state"
            
        w.writerow([hex(fid).upper().replace('0X', '0x'), name, type_val])

print("flags.csv generado exitosamente.")
