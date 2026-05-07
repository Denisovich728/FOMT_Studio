import csv
updates = {
    '0x08D': ('Reset_NPC_Schedule', 'npc_id'),
    '0x046': ('Remove_Held_Item', ''),
    '0x09B': ('Show_Profile_UI', 'profile_id'),
    '0x04A': ('Give_Item', 'item_id')
}

rows = []
with open(r"j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv", 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        hex_id = row[1].upper().replace('0X', '0x')
        if hex_id in updates:
            row[3] = updates[hex_id][0]
            row[4] = updates[hex_id][1]
        rows.append(row)

with open(r"j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv", 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print("lib_fomt.csv actualizado con los nuevos mapeos!")
