import os
import re
import csv
from collections import defaultdict

event_dir = r"j:\Repositorios\fomt_studio\scratch\event_dump"
lib_fomt = r"j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv"
flags_csv = r"j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\flags.csv"

# Load current mappings
mapped_opcodes = {}
with open(lib_fomt, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) > 3:
            hex_id = row[1].upper().replace('0X', '0x')
            name = row[3]
            if not re.match(r'^(Proc|Func)[0-9A-F]+$', name):
                mapped_opcodes[hex_id] = name

mapped_flags = {}
with open(flags_csv, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader) # skip header
    for row in reader:
        fid = row[0].upper().replace('0X', '0x')
        name = row[1]
        if not re.match(r'^Flag_0x[0-9A-F]+$', name):
            mapped_flags[fid] = name

# Non-conclusive storage
non_conclusive_flags = defaultdict(list)
non_conclusive_opcodes = defaultdict(list)

flag_pattern = re.compile(r'(Check_Flag|Set_Flag)\((0x[0-9A-Fa-f]+|\d+)')
opcode_pattern = re.compile(r'(Proc|Func)([0-9A-F]{3})\((.*?)\)')
talk_msg_pattern = re.compile(r'TalkMessage\((0x[0-9A-Fa-f]+|\d+)\)')

for file in sorted(os.listdir(event_dir)):
    if not file.endswith(".txt") or not file.startswith("event_"):
        continue
    
    with open(os.path.join(event_dir, file), 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
        messages = {}
        for line in lines:
            m = re.match(r'const MESSAGE_(\d+) = "(.*?)";', line)
            if m:
                messages[int(m.group(1))] = m.group(2)
        
        for i, line in enumerate(lines):
            # Flags
            for match in flag_pattern.finditer(line):
                fid_str = match.group(2)
                fid = int(fid_str, 16) if fid_str.startswith('0x') else int(fid_str)
                hex_fid = hex(fid).upper().replace('0X', '0x')
                
                if hex_fid not in mapped_flags:
                    context = []
                    for j in range(max(0, i-5), min(len(lines), i+6)):
                        tm = talk_msg_pattern.search(lines[j])
                        if tm:
                            msg_id = int(tm.group(1), 16) if tm.group(1).startswith('0x') else int(tm.group(1))
                            if msg_id in messages:
                                context.append(messages[msg_id])
                    
                    non_conclusive_flags[hex_fid].append({
                        'event': file,
                        'context': " | ".join(context)[:200]
                    })
            
            # Opcodes
            for match in opcode_pattern.finditer(line):
                op_type = match.group(1)
                op_id = match.group(2)
                hex_op = "0x" + op_id.upper()
                
                if hex_op not in mapped_opcodes:
                    context = []
                    for j in range(max(0, i-5), min(len(lines), i+6)):
                        tm = talk_msg_pattern.search(lines[j])
                        if tm:
                            msg_id = int(tm.group(1), 16) if tm.group(1).startswith('0x') else int(tm.group(1))
                            if msg_id in messages:
                                context.append(messages[msg_id])
                    
                    non_conclusive_opcodes[hex_op].append({
                        'event': file,
                        'context': " | ".join(context)[:200]
                    })

# Write non-conclusive
with open(r"j:\Repositorios\fomt_studio\scratch\non_conclusive_flags.csv", 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['flag_id', 'occurrences'])
    for fid in sorted(non_conclusive_flags.keys()):
        occs = " || ".join([f"{o['event']}: {o['context']}" for o in non_conclusive_flags[fid]])
        writer.writerow([fid, occs])

with open(r"j:\Repositorios\fomt_studio\scratch\non_conclusive_opcodes.csv", 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['opcode_id', 'occurrences'])
    for oid in sorted(non_conclusive_opcodes.keys()):
        occs = " || ".join([f"{o['event']}: {o['context']}" for o in non_conclusive_opcodes[oid]])
        writer.writerow([oid, occs])

print(f"Non-conclusive flags: {len(non_conclusive_flags)}")
print(f"Non-conclusive opcodes: {len(non_conclusive_opcodes)}")
