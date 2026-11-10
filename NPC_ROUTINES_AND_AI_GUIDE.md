# FoMT Studio - NPC AI Routines & Motion System Guide
**Technical Reference and Playtesting Handbook for Harvest Moon: Friends of Mineral Town (GBA)**
*Engine: Titan Engine / SlipSpace AI Orchestrator*

---

## 1. Architecture Overview

NPC motion and artificial intelligence in *Harvest Moon: Friends of Mineral Town* are driven by a hierarchical, pointer-based binary structure embedded directly in the ROM.

```
ROM Master NPC Table (0x3D9A4)
  |-- Pointer to NPC 0 Master Struct (12 bytes)
  |-- Pointer to NPC 1 Master Struct (12 bytes)
  |-- ...
  `-- Pointer to NPC 31 Master Struct (12 bytes)
        |
        |--> [evaluator_func: 4 bytes] (ARM/Thumb function in ROM)
        |--> [schedules_count: 4 bytes] (Total number of schedule profiles)
        `--> [schedules_array_ptr: 4 bytes]
               |
               |--> Schedule 0 Header Pointer -> [num_entries, entries_ptr]
               |--> Schedule 1 Header Pointer -> [num_entries, entries_ptr]
               `--> ...
                      |
                      `--> Timeline Array: [time_val: 2B, pad: 2B, path_info_ptr: 4B]
                             |
                             `--> PathInfo Struct (12 bytes):
                                    - pts_ptr: 4 bytes (Pointer to movement points)
                                    - num_points: 2 bytes (Step count)
                                    - spawn_x: 2 bytes (Initial X coordinate)
                                    - spawn_y: 2 bytes (Initial Y coordinate)
                                    - half_0A: 2 bytes (Packed: map_id, spawn_dir, point_type)
```

### Packed Attributes (`half_0A`)
The 16-bit word at offset `0x0A` of each `PathInfo` structure encodes three distinct parameters:
- **Bits 0-9 (`0x03FF`):** `map_id` (Map index where the NPC exists).
- **Bits 10-11 (`0x0C00`):** `spawn_dir` (Initial facing direction: `0`=Down, `1`=Up, `2`=Left, `3`=Right).
- **Bit 12 (`0x1000`):** `point_type_select` (`0`=PathPointA, `1`=PathPointB).

---

## 2. Making NPCs Stand Still (Static Spawns)

### The Mechanics in ROM
In vanilla FoMT, static NPCs (such as shopkeepers behind counters or villagers resting in chairs) do not use dummy walking vectors. Instead:
- `num_points` is set to `0`.
- `pts_ptr` is set to `0x00000000` (NULL).
- The NPC spawns at `(spawn_x, spawn_y)`, faces `spawn_dir`, and executes zero movement vectors.

### How to Configure in FoMT Studio
1. Select the NPC and schedule in the Routine Editor.
2. Select the segment row in the table.
3. Open the **Floating Inspector** and click **"Quedarse Quieto" (Stand Still)**.
   - Alternatively: Set `Destino B (bx, by)` equal to `Origen A (ax, ay)`.
4. When `Destino == Origen`, the path nodes collapse to a single coordinate `[(ax, ay)]`. The compiler automatically outputs `num_points = 0` and `pts_ptr = 0`.
5. The NPC will stand stationary at that coordinate from the designated `time_val` until the next waypoint in the schedule.

---

## 3. Weather, Day, and Season Scheduling

### The Evaluator Function (`evaluator_func`)
The game does not store calendar or weather conditions inside the waypoint coordinates. Instead, each NPC has an assigned `evaluator_func` in ROM (e.g., `0x803DA7D` for Popuri, `0x803DC65` for Lillia).

Every in-game morning at 06:00 AM, the GBA engine invokes this function, which queries the global game flags:
- Day of the week (Monday through Sunday).
- Current weather (Sunny, Rain, Snow, Typhoon, Blizzard).
- Active festivals.
- Friendship / Heart levels and Marriage state.

The function returns a single integer: `schedule_id` (`0`, `1`, `2`, `3`...). The engine then loads that specific schedule profile for the day.

### Canonical Schedule Mapping (Example: Popuri, NPC ID 2)
| Schedule ID | Evaluator Condition | Canonical Routine |
| :--- | :--- | :--- |
| **Schedule 0** | Storm / Typhoon / Blizzard | Confined inside Poultry Farm 2F. |
| **Schedule 1** | Mon-Sat, Sunny / Clear | Morning walk to Hot Springs, returns home at 10:00 AM. |
| **Schedule 2** | Mon-Sat, Rainy / Snow | Remains inside Poultry Farm all day. |
| **Schedule 3** | Sunday, Sunny (Spring/Fall/Winter) | Church with Carter (10:00 AM), Rose Plaza (01:30 PM). |
| **Schedule 4** | Sunday, Rainy | Confined inside the Church with Carter until 04:00 PM. |
| **Schedule 5** | Sunday, Sunny (Summer only) | Mineral Beach with Kai from 01:00 PM to 04:00 PM. |
| **Schedule 6** | Married to Player (Sunny) | Lives at the Player's Farm. |
| **Schedule 7** | Married to Player (Family Visit) | Visits Lillia at Poultry Farm. |

To make an NPC perform an action on a specific day or weather type, select the corresponding **Horario (Schedule #)** from the dropdown in the editor.

---

## 4. Facing Direction & Pauses (Delays)

### Facing Direction
- **Initial Spawn Facing:** In the Floating Inspector, set the **"Vista"** dropdown:
  - `Abajo (Down)` = Facing camera (`DIR_DOWN`, `0`).
  - `Arriba (Up)` = Facing north (`DIR_UP`, `1`).
  - `Izquierda (Left)` = Facing west (`DIR_LEFT`, `2`).
  - `Derecha (Right)` = Facing east (`DIR_RIGHT`, `3`).
- **Mid-Route Facing:** In the inflection point editor, select any intermediate node to customize the facing direction for that segment.

### Pauses and Delays Before Moving
Movement points of type `PathPointB` are encoded as 8-byte structs:
```
[coord: 2 bytes] [speed: 2 bytes] [delay: 2 bytes] [flags: 2 bytes]
```
- **`delay` (16-bit word):** Measured in **engine ticks** (`60 ticks = 1 second` of real time).
- Entering `120` in the waypoint delay will cause the NPC to arrive at that tile, pause for 2 full seconds, and then resume moving along the next vector.
- In contrast, the `Hora / Minuto` fields on the timeline represent **in-game clock time** (minutes elapsed since midnight, `0..1439`).

---

## 5. Moving NPCs Between Maps and Houses

To make an NPC travel between different maps across their daily routine:
1. **Waypoint 1 (Map A):** Set `Hora = 07:00`, `Mapa = 0x02` (Poultry Farm Exterior), `Coords = (120, 140)`.
2. **Waypoint 2 (Map B):** Set `Hora = 10:00`, `Mapa = 0x17` (Hot Springs), `Coords = (272, 72)`.

### Transition Behavior:
- **Off-screen Transition:** If the player is not present in Map A when `10:00 AM` strikes, the engine instantly despawns the NPC from Map A and spawns them at the Waypoint 2 coordinates in Map B.
- **On-screen Walkout:** If the player is watching the NPC in Map A, ensure the path nodes lead directly onto the door/warp tile. When the scheduled time arrives, the NPC steps into the warp threshold and despawns naturally.

---

## 6. The "Broken Daily Dialogue" Glitch (Missing Text-Box)

### Symptom
When Popuri was moved to the top of the mountain (`Mothers_Hill_Peak`), or Lillia was placed outside her usual spots:
- They properly introduced themselves on the first interaction (`TalkMessage(0)` played fine).
- On subsequent daily interactions, pressing `A` caused the game to open and instantly close without loading any text box.

### Root Cause in the GBA Script Bytecode
In FoMT, every NPC has a **Personality Script** (e.g., Event `993` for Popuri, Event `994` for Lillia).

When spoken to, the script executes:
```c
if (Check_If_Single("Popuri") == 0) {
    // Has not introduced herself yet
    TalkMessage(0); // "Hello, my name is Popuri..."
    Free_Event_Entity("Popuri");
} else {
    // Normal daily interaction
    switch (GetEntityLocation(3)) {
        case "Poultry_Farm_House_Floor_02":
            ...
            break;
        case "Mothers_Hill_Middle":
        case "North_Side_Town":
        case "Rose_Square":
        case "South_Side_Town":
            ...
            break;
        case "Mineral_Beach":
            ...
            break;
    }
}
TalkClose();
exit;
```

Notice the critical design flaw in the original ROM:
1. The script checks `switch (GetEntityLocation(...))` with **only the maps where the NPC canonically travels**.
2. **There is no `default:` case.**
3. If Popuri is on `Mothers_Hill_Peak` (`0x16`), the switch fails to match any case.
4. The execution skips every `TalkMessage()` call and falls through directly to `TalkClose()` and `exit;`.

### How to Fix
To allow an NPC to speak on a new map:
1. Open the **Script IDE** in FoMT Studio.
2. Load the NPC's Personality Script (`Popuri_Personality` / ID `993`, `Lilia_Personaliti` / ID `994`).
3. Add the target map ID to the `switch (GetEntityLocation(...))` statement, or add a fallback `default:` block that routes unhandled locations to a generic dialogue line (e.g., `TalkMessage(138)`).
4. Recompile and reinject the script into the ROM.

---

## 7. Known Engine Quirks

### Saving Inside Indoor Rooms with Moving NPCs (The Church Anomaly)
- **Quirk:** Saving the game inside a room while an NPC is executing an active movement loop (e.g., Popuri in the Church) can cause the NPC to glide or walk oddly upon reloading the save.
- **Cause:** The GBA save file (SRAM/Flash 64K) preserves the physical coordinates of the NPC, but the vector motion interpreter reinitializes to step 0 when the ROM boots. The discrepancy between the preserved SRAM coordinates and vector step 0 causes an initial displacement glitch.
- **Resolution:** Leaving the room and re-entering triggers `InitMapEntities`, completely resetting all entity vectors and positions to their canonical state.

---
*Documentation compiled by FoMT Studio Suite - Engineering Reference.*

