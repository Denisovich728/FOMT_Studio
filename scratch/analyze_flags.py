import os
import re
import csv

event_dir = r"j:\Repositorios\fomt_studio\scratch\event_dump"
results = []

# Regex to catch Set_Flag(id, val)
# It handles both hex and decimal
set_flag_pattern = re.compile(r'Set_Flag\((0x[0-9A-Fa-f]+|\d+),\s*(0x[0-9A-Fa-f]+|\d+)\)')
talk_msg_pattern = re.compile(r'TalkMessage\((0x[0-9A-Fa-f]+|\d+)\)')

for file in os.listdir(event_dir):
    if file.endswith(".txt"):
        with open(os.path.join(event_dir, file), 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            # Map of message IDs to content for this file
            messages = {}
            for line in lines:
                m = re.match(r'const MESSAGE_(\d+) = "(.*?)";', line)
                if m:
                    messages[int(m.group(1))] = m.group(2)
            
            for i, line in enumerate(lines):
                match = set_flag_pattern.search(line)
                if match:
                    flag_id_str = match.group(1)
                    val_str = match.group(2)
                    
                    flag_id = int(flag_id_str, 16) if flag_id_str.startswith('0x') else int(flag_id_str)
                    val = int(val_str, 16) if val_str.startswith('0x') else int(val_str)
                    
                    # Find nearby messages (within 10 lines before/after)
                    nearby_msgs = []
                    for j in range(max(0, i-10), min(len(lines), i+11)):
                        tm = talk_msg_pattern.search(lines[j])
                        if tm:
                            msg_id = int(tm.group(1), 16) if tm.group(1).startswith('0x') else int(tm.group(1))
                            if msg_id in messages:
                                nearby_msgs.append(messages[msg_id])
                    
                    results.append({
                        'event': file,
                        'line': i+1,
                        'flag_id': hex(flag_id),
                        'value': val,
                        'context': " | ".join(nearby_msgs)[:200]
                    })

with open(r"j:\Repositorios\fomt_studio\scratch\flag_context_analysis.csv", 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['event', 'line', 'flag_id', 'value', 'context'])
    writer.writeheader()
    writer.writerows(results)

print(f"Analysis complete. {len(results)} flags logged.")
