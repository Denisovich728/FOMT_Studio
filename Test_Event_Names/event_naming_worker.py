import os
import sys
import re
import json
import time
import urllib.request
import csv

# Add workspace to sys.path so project modules can be imported
workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from Banco_de_Datos.proyecto import FoMTProject
from Nucleos_Positronicos.Nucleo_de_Scripts.eventos import FoMTEventParser

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

BASE_CSV_PATH = os.path.join(workspace_dir, "Banco_de_Datos", "Cilixes", "fomt", "Fomt_Events_Listname.csv")
OUTPUT_DIR = os.path.abspath(os.path.dirname(__file__))
OUTPUT_CSV_PATH = os.path.join(OUTPUT_DIR, "Fomt_Events_Listname_named.csv")
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "naming_checkpoint.json")
LOG_PATH = os.path.join(OUTPUT_DIR, "naming_log.txt")

# Canonical NPC dictionary
NPC_CATALOG = [
    "Lillia", "Rick", "Popuri", "Barley", "May", "Saibara", "Gray", "Duke",
    "Manna", "Basil", "Anna", "Mary", "Thomas", "Harris", "Ellen", "Stu",
    "Jeff", "Sasha", "Karen", "Doctor", "Elli", "Carter", "Cliff", "Doug",
    "Ann", "Kai", "Gotz", "Zack", "Won", "Gourmet", "Harvest_Goddess", "Kappa",
    "Lou", "Lu", "Staid", "Nappy", "Bold", "Chef", "Aqua", "Hoggy", "Timid"
]

CANDIDATES = ["Ann", "Elli", "Karen", "Mary", "Popuri", "Harvest_Goddess"]

def find_latest_session_rom():
    sessions_dir = os.path.join(workspace_dir, "Sessions")
    candidates = []
    if os.path.exists(sessions_dir):
        for entry in os.listdir(sessions_dir):
            p = os.path.join(sessions_dir, entry, "source.gba")
            if os.path.isfile(p):
                candidates.append(p)
    if candidates:
        candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return candidates[0]
    return None

def clean_dialogue(code_text):
    messages = re.findall(r'const MESSAGE_\d+ = "(.*?)";', code_text, re.DOTALL)
    cleaned = []
    for m in messages:
        c = re.sub(r'\\[a-zA-Z0-9%!\.\?\n]', ' ', m)
        c = re.sub(r'[\x00-\x1f]', ' ', c)
        c = ' '.join(c.split())
        if c:
            cleaned.append(c)
    return ' | '.join(cleaned[:8])

def extract_key_actions(code_text):
    lines = [l.strip() for l in code_text.split('\n') if l.strip()]
    actions = []
    for l in lines:
        if any(l.startswith(k) for k in ('Set_Flag', 'Check_Flag', 'SetEntity', 'GiveItem', 'AddMoney', 'Inventory', 'PlayBGM', 'Change', 'Set_Hearth')):
            actions.append(l)
    return '; '.join(actions[:8])

def detect_npcs(code_text):
    found = set()
    for npc in NPC_CATALOG:
        clean_npc = npc.replace('Harvest_', '').replace('Sprite_', '')
        if re.search(r'\b' + clean_npc + r'\b', code_text, re.IGNORECASE):
            found.add(npc)
    return sorted(found)

def detect_heart_and_rival_flags(code_text):
    # Detect exact candidate heart flags
    heart_matches = re.findall(r'(Karen|Popuri|Ann|Mary|Elli)_Heart_(Black|Purple|Blue|Yellow|Orange)', code_text)
    # Detect exact rival event flags
    rival_matches = re.findall(r'Rival_([A-Za-z]+)_([A-Za-z]+)_Event_(\d+)', code_text)
    
    hearts = [f"{c}_Heart_{color}" for c, color in heart_matches]
    rivals = [f"Rival_{c1}_{c2}_{num}" for c1, c2, num in rival_matches]
    return hearts, rivals

def ask_llama(event_id, dialogue, actions, npcs, heart_flags, rival_flags):
    # Rule 1: Deterministic resolution for explicit single candidate heart events
    if heart_flags:
        # Check if a heart flag is being SET in the event
        set_hearts = re.findall(r'Set_Flag\("(?:Karen|Popuri|Ann|Mary|Elli)_Heart_(?:Black|Purple|Blue|Yellow|Orange)"', actions)
        if set_hearts:
            flag_name = set_hearts[0].replace('Set_Flag("', '').replace('"', '')
            return flag_name
        return heart_flags[0]

    # Rule 2: Deterministic resolution for rival events
    if rival_flags:
        set_rivals = re.findall(r'Set_Flag\("Rival_[A-Za-z]+_[A-Za-z]+_Event_\d+"', actions)
        if set_rivals:
            flag_name = set_rivals[0].replace('Set_Flag("', '').replace('"', '')
            return flag_name
        return rival_flags[0]

    # Rule 3: Use Llama 3b with canonical guide knowledge and detected NPCs
    npc_str = ", ".join(npcs) if npcs else "Unknown NPC"
    prompt = (
        "You are an expert game analyst naming event scripts for the GBA RPG game Harvest Moon: Friends of Mineral Town (FoMT).\n"
        "Generate a concise, descriptive event identifier in Pascal_Snake_Case based on canonical game guides (Fogu / Ushi No Tane / GameFAQs).\n\n"
        "Rules:\n"
        "1. Marriage Candidate Heart Events: Format MUST be <Candidate>_Heart_<Color> (e.g. Karen_Heart_Black, Popuri_Heart_Blue, Ann_Heart_Yellow, Elli_Heart_Purple, Mary_Heart_Black).\n"
        "2. Rival Heart Events: Format MUST be Rival_<Candidate>_<Rival>_<Num> (e.g. Rival_Karen_Rick_1, Rival_Ann_Cliff_1).\n"
        "3. Regular Town/Cutscene Events: ALWAYS include the primary NPC name(s) involved and the situation (e.g. Barley_Horse_Evaluation, Carter_Church_Confession, Cliff_Collapses_Square, May_Missing_Search, Duke_Winery_Job_Offer, Zack_Shipping_Intro, Won_Sells_Apple, Gray_Saibara_Hammer, Ellen_Socks_Winter, Lu_Cooking_Recipe, Thomas_Winter_Request).\n"
        "4. Festivals: Name the festival and phase (e.g. Cooking_Festival_Judging, Goddess_Festival_Dance, Chicken_Festival_Sumo, Spring_Horse_Race_Betting, Starry_Night_Dinner).\n"
        "5. Respond ONLY with the single identifier name (max 38 characters). No quotes, no markdown, no explanation.\n\n"
        f"Event ID: {event_id}\n"
        f"NPCs Involved: {npc_str}\n"
        f"Dialogue Snippet: {dialogue if dialogue else '(No direct dialogue)'}\n"
        f"Key Actions: {actions if actions else '(Standard cutscene flow)'}\n\n"
        "Event Name:"
    )

    req_data = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": 25
        }
    }

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(req_data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw = data.get("response", "").strip()
            
            cleaned = re.sub(r'^(Event_Name|EventName|Name):\s*', '', raw, flags=re.IGNORECASE).strip()
            cleaned = cleaned.replace('`', '').replace('"', '').replace("'", "").replace('-', '_')
            cleaned = re.sub(r'[^\w]', '', cleaned)
            return cleaned[:40] if cleaned else f"Event_{event_id}"
    except Exception as e:
        return f"Error_Event_{event_id}"

def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_checkpoint(data):
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def save_csv(event_records):
    sorted_records = sorted(event_records.values(), key=lambda x: int(x["ID"]))
    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Event_Name", "ID"])
        for r in sorted_records:
            writer.writerow([r["Event_Name"], r["ID"]])

def main():
    print(f"=== FoMT Event Naming Worker (Upgraded with NPC & Heart Guide Engine) ===")
    rom_path = find_latest_session_rom()
    if not rom_path:
        print("ERROR: No session ROM found!")
        sys.exit(1)

    print(f"Using ROM: {rom_path}")
    print(f"Output CSV: {OUTPUT_CSV_PATH}")
    print(f"Log: {LOG_PATH}")

    import tempfile
    proj = FoMTProject()
    with tempfile.TemporaryDirectory() as tmpdir:
        proj.create_new(rom_path, tmpdir)
        parser = FoMTEventParser(proj)
        total_events = parser.get_event_count()
        print(f"Total events in ROM: {total_events}")

        # Read base CSV
        base_events = {}
        if os.path.exists(BASE_CSV_PATH):
            with open(BASE_CSV_PATH, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        base_events[int(row[1])] = row[0]

        # Load existing progress
        checkpoint = load_checkpoint()
        event_records = {}
        for eid, name in checkpoint.items():
            event_records[int(eid)] = {"Event_Name": name, "ID": int(eid)}

        processed_this_run = 0
        t_start = time.time()

        for eid in range(1, total_events + 1):
            eid_str = str(eid)
            base_name = base_events.get(eid, f"Unknow_Event_{eid}")

            # If already processed in checkpoint, keep it
            if eid_str in checkpoint:
                continue

            # If already has a clean curated name (not starting with Unknow/Unknown), keep it
            if not base_name.lower().startswith("unknow"):
                checkpoint[eid_str] = base_name
                event_records[eid] = {"Event_Name": base_name, "ID": eid}
                with open(LOG_PATH, "a", encoding="utf-8") as log:
                    log.write(f"[{eid:04d}/{total_events:04d}] Kept canonical: {base_name}\n")
                continue

            # Decompile event
            t0 = time.time()
            hint, offset = parser.get_event_name_and_offset(eid)
            if offset is None:
                new_name = f"Unused_Event_{eid}"
                elapsed = time.time() - t0
                reason = "NULL offset"
            else:
                code, _ = parser.decompile_to_ui(eid)
                cleaned_lines = [l.strip() for l in code.split('\n') if l.strip() and not l.strip().startswith('//') and not l.strip().startswith('#')]
                stmts = [l for l in cleaned_lines if not l.startswith('script ') and l != '{' and l != '}']
                
                if not stmts or stmts == ['exit;']:
                    new_name = f"Empty_Event_{eid}"
                    elapsed = time.time() - t0
                    reason = "Empty script"
                else:
                    dialogue = clean_dialogue(code)
                    actions = extract_key_actions(code)
                    npcs = detect_npcs(code)
                    heart_flags, rival_flags = detect_heart_and_rival_flags(code)
                    new_name = ask_llama(eid, dialogue, actions, npcs, heart_flags, rival_flags)
                    elapsed = time.time() - t0
                    info_tags = []
                    if heart_flags: info_tags.append(f"Heart: {heart_flags[0]}")
                    if rival_flags: info_tags.append(f"Rival: {rival_flags[0]}")
                    if npcs: info_tags.append(f"NPCs: {', '.join(npcs[:2])}")
                    tag_str = f" [{'; '.join(info_tags)}]" if info_tags else ""
                    reason = f"Llama 3b + Guide{tag_str} ({elapsed:.1f}s)"

            checkpoint[eid_str] = new_name
            event_records[eid] = {"Event_Name": new_name, "ID": eid}
            processed_this_run += 1

            msg = f"[{eid:04d}/{total_events:04d}] ID {eid}: '{base_name}' -> '{new_name}' ({reason})"
            print(msg, flush=True)
            with open(LOG_PATH, "a", encoding="utf-8") as log:
                log.write(msg + "\n")

            # Persist checkpoint and CSV every 5 items
            if processed_this_run % 5 == 0 or eid == total_events:
                save_checkpoint(checkpoint)
                save_csv(event_records)

        # Final save
        save_checkpoint(checkpoint)
        save_csv(event_records)
        total_time = time.time() - t_start
        print(f"=== COMPLETED: Processed {processed_this_run} events in {total_time/60:.1f} minutes ===")

if __name__ == "__main__":
    main()
