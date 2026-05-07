import os
import re
import csv

event_dir = r"j:\Repositorios\fomt_studio\scratch\event_dump"
results = []

opcode_pattern = re.compile(r'(Proc|Func)([0-9A-F]{3})\((.*?)\)')
talk_msg_pattern = re.compile(r'TalkMessage\((0x[0-9A-Fa-f]+|\d+)\)')

for file in os.listdir(event_dir):
    if file.endswith(".txt"):
        with open(os.path.join(event_dir, file), 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            messages = {}
            for line in lines:
                m = re.match(r'const MESSAGE_(\d+) = "(.*?)";', line)
                if m:
                    messages[int(m.group(1))] = m.group(2)
            
            for i, line in enumerate(lines):
                match = opcode_pattern.search(line)
                if match:
                    op_type = match.group(1)
                    op_id = match.group(2)
                    args = match.group(3)
                    
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
                        'opcode': op_type + op_id,
                        'args': args,
                        'context': " | ".join(nearby_msgs)[:200]
                    })

with open(r"j:\Repositorios\fomt_studio\scratch\opcode_context_analysis.csv", 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['event', 'line', 'opcode', 'args', 'context'])
    writer.writeheader()
    writer.writerows(results)

print(f"Analysis complete. {len(results)} opcodes logged.")
