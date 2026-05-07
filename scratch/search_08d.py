import csv
with open('j:\\Repositorios\\fomt_studio\\Nucleos_de_Procesamiento\\data\\lib_fomt.csv', 'r', encoding='utf-8') as f:
    r = csv.reader(f)
    for row in r:
        if '0x08D' in row[1].upper() or '08D' in row[1].upper():
            print("Found 08D:", row)
