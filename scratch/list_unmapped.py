import csv
import re

unmapped = []
with open(r'j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) > 3:
            name = row[3]
            if re.match(r'^(Proc|Func)[0-9A-F]+$', name):
                unmapped.append((row[1], name))

for hex_id, name in unmapped:
    print(f"{hex_id}: {name}")
