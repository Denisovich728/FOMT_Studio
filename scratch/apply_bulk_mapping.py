import csv

# Mapeos de Opcodes
opcode_updates = {
    '0x0CA': ('Anim_Door_Open', 'door_id'),
    '0x12B': ('Screen_Flash', 'r, g, b'),
    '0x129': ('Set_Spouse_Nickname', 'nickname_id'),
    '0x0A6': ('Open_Name_Entry_UI', 'type'),
    '0x0B8': ('Put_Flower_In_Vase', 'item_id'),
    '0x146': ('Play_SE_ID', 'se_id'),
}

# Mapeos de Flags
flag_updates = {
    '0x19F': ('Selected_Festival_Partner', 'state'),
    '0x19E': ('Event_Fireworks_Active', 'binary'),
    '0x194': ('Event_BeachDay_Active', 'binary'),
    '0x04A': ('Event_Karen_Cooking_Status', 'binary'), # Originalmente 0x4A en hex
    '0x35': ('Spouse_Works_At_Store', 'binary'),
    '0x15F': ('Event_Goddess_Shipment_Reward_Active', 'binary'),
}

# Actualizar Opcodes
rows = []
with open(r'j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        hex_id = row[1].upper().replace('0X', '0x')
        if hex_id in opcode_updates:
            row[3] = opcode_updates[hex_id][0]
            row[4] = opcode_updates[hex_id][1]
        rows.append(row)

with open(r'j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(rows)

# Actualizar Flags
flag_rows = []
with open(r'j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\flags.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    flag_rows.append(header)
    for row in reader:
        fid = row[0].upper().replace('0X', '0x')
        if fid in flag_updates:
            row[1] = flag_updates[fid][0]
            row[2] = flag_updates[fid][1]
        flag_rows.append(row)

with open(r'j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\flags.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(flag_rows)

print("Mapping updated successfully.")
