# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa
# Documentación y Localización Multilingüe de Opcodes VM FoMT
# Desarrollado por: Denisovich728
# ============================================================
"""
opcode_docs.py
══════════════════════════════════════════════════════════════
Provee descripciones técnicas, firmas de argumentos y ayuda
multilingüe (es, en, jp, ru, de, zh, pt, hi) para las llamadas
de la máquina virtual (VM) y funciones del engine de FoMT.
"""

from typing import Dict, Any, Optional

OPCODE_CATALOG: Dict[str, Dict[str, Any]] = {
    "SetEntityPosition": {
        "summary": {
            "es": "Establece la posición (X, Y) y elevación de una entidad en el mapa.",
            "en": "Sets the entity position (X, Y) and elevation on the map.",
            "jp": "マップ上のエンティティの座標(X, Y)と高度を設定します。",
            "de": "Setzt Position (X, Y) und Höhe einer Entität auf der Karte.",
            "ru": "Задает позицию (X, Y) и высоту сущности на карте.",
            "zh": "设置地图上实体的坐标(X, Y)与高度。",
            "pt": "Define a posição (X, Y) e elevação de uma entidade no mapa.",
            "hi": "मानचित्र पर इकाई की स्थिति (X, Y) और ऊंचाई सेट करता है।"
        },
        "args_doc": "entity_id, x, y, elevation"
    },
    "GetEntityX": {
        "summary": {
            "es": "Retorna la coordenada X actual de la entidad en el mapa.",
            "en": "Returns the current X coordinate of the entity on the map.",
            "jp": "エンティティの現在のX座標を返します。",
            "de": "Gibt die aktuelle X-Koordinate der Entität zurück.",
            "ru": "Возвращает текущую координату X сущности на карте.",
            "zh": "返回实体当前在地图上的X坐标。",
            "pt": "Retorna a coordenada X atual da entidade no mapa.",
            "hi": "मानचित्र पर इकाई का वर्तमान X निर्देशांक लौटाता है।"
        },
        "args_doc": "entity_id"
    },
    "GetEntityY": {
        "summary": {
            "es": "Retorna la coordenada Y actual de la entidad en el mapa.",
            "en": "Returns the current Y coordinate of the entity on the map.",
            "jp": "エンティティの現在のY座標を返します。",
            "de": "Gibt die aktuelle Y-Koordinate der Entität zurück.",
            "ru": "Возвращает текущую координату Y сущности на карте.",
            "zh": "返回实体当前在地图上的Y坐标。",
            "pt": "Retorna a coordenada Y atual da entidade no mapa.",
            "hi": "मानचित्र पर इकाई का वर्तमान Y निर्देशांक लौटाता है।"
        },
        "args_doc": "entity_id"
    },
    "SetEntityFacing": {
        "summary": {
            "es": "Cambia la orientación visual de la entidad (Arriba, Abajo, Izquierda, Derecha).",
            "en": "Sets entity facing direction (Up, Down, Left, Right).",
            "jp": "エンティティの向きを設定します (上, 下, 左, 右)。",
            "de": "Setzt die Blickrichtung der Entität (Oben, Unten, Links, Rechts).",
            "ru": "Задает направление взгляда сущности (Вверх, Вниз, Влево, Вправо).",
            "zh": "设置实体的朝向 (上, 下, 左, 右)。",
            "pt": "Define a orientação visual da entidade (Cima, Baixo, Esquerda, Direita).",
            "hi": "इकाई की दिशा निर्धारित करता है।"
        },
        "args_doc": "entity_id, direction (0=Down, 1=Right, 2=Up, 3=Left)"
    },
    "GetEntityFacing": {
        "summary": {
            "es": "Retorna la dirección u orientación actual de la entidad.",
            "en": "Returns the current facing direction of the entity.",
            "jp": "エンティティの現在の向きを返します。",
            "de": "Gibt die aktuelle Blickrichtung der Entität zurück.",
            "ru": "Возвращает текущее направление взгляда сущности.",
            "zh": "返回实体当前的朝向。",
            "pt": "Retorna a direção ou orientação atual da entidade.",
            "hi": "इकाई की वर्तमान दिशा लौटाता है।"
        },
        "args_doc": "entity_id"
    },
    "GetEntityLocation": {
        "summary": {
            "es": "Retorna el ID del mapa donde se encuentra actualmente la entidad.",
            "en": "Returns the map ID where the entity is currently located.",
            "jp": "エンティティが現在配置されているマップIDを返します。",
            "de": "Gibt die Karten-ID zurück, auf der sich die Entität befindet.",
            "ru": "Возвращает ID карты, на которой находится сущность.",
            "zh": "返回实体当前所在的地图ID。",
            "pt": "Retorna o ID do mapa onde a entidade está localizada.",
            "hi": "मानचित्र ID लौटाता है जहां इकाई स्थित है।"
        },
        "args_doc": "entity_id"
    },
    "Execute_Movement": {
        "summary": {
            "es": "Ejecuta la ruta de movimiento o secuencia cinemática para la entidad.",
            "en": "Executes the programmed movement path or sequence for the entity.",
            "jp": "エンティティに設定された移動ルートやシーケンスを実行します。",
            "de": "Führt die programmierte Bewegungssequenz für die Entität aus.",
            "ru": "Запускает запрограммированную последовательность движения сущности.",
            "zh": "执行为实体编排的移动路径或序列。",
            "pt": "Executa a rota de movimento programada para a entidade.",
            "hi": "इकाई के लिए प्रोग्राम किए गए आंदोलन पथ को निष्पादित करता है।"
        },
        "args_doc": "entity_id"
    },
    "SetEntityAnim": {
        "summary": {
            "es": "Aplica una animación u OAM específico a la entidad.",
            "en": "Sets an animation or OAM state on the entity.",
            "jp": "エンティティに特定のアニメーションまたはOAM状態を適用します。",
            "de": "Wendet eine spezifische Animation oder OAM-Status auf die Entität an.",
            "ru": "Применяет анимацию или состояние OAM к сущности.",
            "zh": "为实体应用特定动画或OAM状态。",
            "pt": "Aplica uma animação ou estado OAM específico à entidade.",
            "hi": "इकाई पर एक एनीमेशन लागू करता है।"
        },
        "args_doc": "entity_id, anim_id"
    },
    "Hide_Entity": {
        "summary": {
            "es": "Oculta temporalmente el sprite de la entidad en el renderizador de pantalla.",
            "en": "Temporarily hides the entity sprite from screen rendering.",
            "jp": "エンティティのスプライトを画面から一時的に非表示にします。",
            "de": "Versteckt das Sprite der Entität vorübergehend.",
            "ru": "Временно скрывает спрайт сущности на экране.",
            "zh": "在屏幕渲染中临时隐藏该实体的精灵。",
            "pt": "Oculta temporariamente o sprite da entidade na tela.",
            "hi": "इकाई स्प्राइट को अस्थायी रूप से छुपाता है।"
        },
        "args_doc": "entity_id"
    },
    "Spawn_Event_Entity": {
        "summary": {
            "es": "Instancia una entidad de evento en la posición designada.",
            "en": "Spawns an event entity at designated coordinates.",
            "jp": "指定された座標にイベントエンティティを生成します。",
            "de": "Spawnt eine Event-Entität an den angegebenen Koordinaten.",
            "ru": "Создает сущность события в указанных координатах.",
            "zh": "在指定坐标生成事件实体。",
            "pt": "Instancia uma entidade de evento na posição designada.",
            "hi": "नामित निर्देशांक पर एक इवेंट इकाई को स्पॉन करता है।"
        },
        "args_doc": "entity_id, template_id"
    },
    "Show_Emote": {
        "summary": {
            "es": "Muestra un globo gestual (corazón, interrogación, enfado, etc.) sobre la entidad.",
            "en": "Displays an emote bubble (heart, question, anger, etc.) over the entity.",
            "jp": "エンティティの頭上にエモートフキダシを表示します (ハート, 疑問, 怒り等)。",
            "de": "Zeigt eine Emotionsblase (Herz, Fragezeichen, Wut usw.) über der Entität.",
            "ru": "Отображает значок эмоции (сердце, вопрос, злость) над сущностью.",
            "zh": "在实体头顶显示情绪气泡 (爱心, 问号, 愤怒等)。",
            "pt": "Exibe um balão de emoção (coração, interrogação, raiva, etc.) sobre a entidade.",
            "hi": "इकाई के ऊपर एक इमोट बबल प्रदर्शित करता है।"
        },
        "args_doc": "entity_id, emote_id, duration"
    },
    "Fade_Out": {
        "summary": {
            "es": "Transición de oscurecimiento de pantalla a negro.",
            "en": "Screen fade-out transition to black.",
            "jp": "画面を黒へとフェードアウトさせます。",
            "de": "Bildschirm-Ausblendung nach Schwarz.",
            "ru": "Затемнение экрана до черного цвета.",
            "zh": "屏幕淡出黑屏过渡。",
            "pt": "Transição de escurecimento da tela para preto.",
            "hi": "स्क्रीन को काले रंग में फेड आउट करता है।"
        },
        "args_doc": "speed"
    },
    "Fade_In": {
        "summary": {
            "es": "Transición de iluminación de pantalla desde negro.",
            "en": "Screen fade-in transition from black.",
            "jp": "黒画面からフェードインして復帰させます。",
            "de": "Bildschirm-Einblendung aus Schwarz.",
            "ru": "Появление экрана из черного цвета.",
            "zh": "屏幕从黑屏淡入恢复过渡。",
            "pt": "Transição de iluminação da tela a partir do preto.",
            "hi": "काले रंग से स्क्रीन फेड इन करता है।"
        },
        "args_doc": "speed"
    },
    "TalkOpen": {
        "summary": {
            "es": "Abre la ventana de diálogo de texto para interacción.",
            "en": "Opens the text dialogue box for interaction.",
            "jp": "会話用メッセージボックスを開きます。",
            "de": "Öffnet das Text-Dialogfenster zur Interaktion.",
            "ru": "Открывает диалоговое окно для сообщений.",
            "zh": "打开交互文本对话框。",
            "pt": "Abre a caixa de diálogo de texto para interação.",
            "hi": "संवाद बॉक्स खोलता है।"
        },
        "args_doc": "speaker_id"
    },
    "TalkMessage": {
        "summary": {
            "es": "Imprime un mensaje de texto formateado en la ventana de diálogo activa.",
            "en": "Prints a formatted text message in the active dialogue box.",
            "jp": "アクティブなメッセージボックスにフォーマット済みテキストを表示します。",
            "de": "Gibt eine formatierte Textnachricht im aktiven Dialogfenster aus.",
            "ru": "Выводит форматированное текстовое сообщение в активное окно.",
            "zh": "在当前对话框中输出格式化文本消息。",
            "pt": "Imprime uma mensagem de texto formatada na janela de diálogo ativa.",
            "hi": "सक्रिय संवाद बॉक्स में टेक्स्ट संदेश प्रिंट करता है।"
        },
        "args_doc": "message_id"
    },
    "TalkClose": {
        "summary": {
            "es": "Cierra la ventana de diálogo activa y devuelve el control al motor.",
            "en": "Closes active dialogue box and returns control to the engine.",
            "jp": "会話ボックスを閉じてエンジンに制御を返します。",
            "de": "Schließt das Dialogfenster und gibt die Kontrolle an die Engine zurück.",
            "ru": "Закрывает диалоговое окно и возвращает управление движку.",
            "zh": "关闭对话框并将控制权归还给引擎。",
            "pt": "Fecha a janela de diálogo ativa e devolve o controle à engine.",
            "hi": "संवाद बॉक्स बंद करता है।"
        },
        "args_doc": "none"
    },
    "Give_Item": {
        "summary": {
            "es": "Otorga un objeto, cosecha o herramienta al inventario o mochila.",
            "en": "Gives an item, crop, or tool to the player's rucksack inventory.",
            "jp": "リュックやインベントリにアイテム/作物/道具を付与します。",
            "de": "Gibt dem Spieler einen Gegenstand oder Werkzeug ins Inventar.",
            "ru": "Выдает предмет, урожай или инструмент в инвентарь игрока.",
            "zh": "给予玩家背包特定道具、作物或工具。",
            "pt": "Concede um item, colheita ou ferramenta ao inventário da mochila.",
            "hi": "खिलाड़ी की इन्वेंट्री में एक आइटम देता है।"
        },
        "args_doc": "item_id, quantity"
    },
    "Check_Flag": {
        "summary": {
            "es": "Evalúa el estado booleano de una bandera de evento o progreso.",
            "en": "Evaluates the boolean state of an event or progress flag.",
            "jp": "イベントまたは進行フラグの論理状態(True/False)を評価します。",
            "de": "Prüft den booleschen Zustand eines Event-Flags.",
            "ru": "Проверяет булево состояние флага события или прогресса.",
            "zh": "评估事件或进度标志的布尔状态 (True/False)。",
            "pt": "Avalia o estado booleano de uma flag de evento ou progresso.",
            "hi": "इवेंट ध्वज की स्थिति की जांच करता है।"
        },
        "args_doc": "flag_id"
    },
    "Set_Flag": {
        "summary": {
            "es": "Activa (pone a 1) una bandera de evento en la memoria del juego.",
            "en": "Sets (activates to 1) an event flag in game memory.",
            "jp": "ゲームメモリ内のイベントフラグをON(1)に設定します。",
            "de": "Setzt ein Event-Flag im Spielspeicher auf aktiv (1).",
            "ru": "Активирует (устанавливает в 1) флаг события в памяти игры.",
            "zh": "将游戏内存中的事件标志置为激活 (1)。",
            "pt": "Ativa (define como 1) uma flag de evento na memória do jogo.",
            "hi": "गेम मेमोरी में एक इवेंट ध्वज को 1 पर सेट करता है।"
        },
        "args_doc": "flag_id"
    },
    "Clear_Flag": {
        "summary": {
            "es": "Desactiva (pone a 0) una bandera de evento en la memoria del juego.",
            "en": "Clears (resets to 0) an event flag in game memory.",
            "jp": "ゲームメモリ内のイベントフラグをOFF(0)にリセットします。",
            "de": "Setzt ein Event-Flag im Spielspeicher zurück (0).",
            "ru": "Сбрасывает (устанавливает в 0) флаг события в памяти игры.",
            "zh": "将游戏内存中的事件标志清零重置 (0)。",
            "pt": "Desativa (define como 0) uma flag de evento na memória do jogo.",
            "hi": "गेम मेमोरी में एक इवेंट ध्वज को 0 पर रीसेट करता है।"
        },
        "args_doc": "flag_id"
    }
}


def get_opcode_doc(name: str, lang: str = "es") -> str:
    """Retorna la descripción traducida del opcode."""
    lang_key = (lang or "es").lower()
    entry = OPCODE_CATALOG.get(name)
    if entry and "summary" in entry:
        return entry["summary"].get(lang_key, entry["summary"].get("en", entry["summary"].get("es", "")))
    return ""


def get_opcode_full_tooltip(name: str, kind: str, hex_id: str, args: str, lang: str = "es") -> str:
    """Genera un tooltip completo y localizado para autocompletado y editores."""
    lang_key = (lang or "es").lower()
    kind_upper = kind.upper()
    args_disp = f"({args})" if args else "()"
    doc = get_opcode_doc(name, lang=lang_key)

    headers = {
        "es": f"{kind_upper} | ID: {hex_id}\nEstructura: {name}{args_disp}",
        "en": f"{kind_upper} | ID: {hex_id}\nStructure: {name}{args_disp}",
        "jp": f"{kind_upper} | ID: {hex_id}\n構文: {name}{args_disp}",
        "de": f"{kind_upper} | ID: {hex_id}\nStruktur: {name}{args_disp}",
        "ru": f"{kind_upper} | ID: {hex_id}\nСтруктура: {name}{args_disp}",
        "zh": f"{kind_upper} | ID: {hex_id}\n语法结构: {name}{args_disp}",
        "pt": f"{kind_upper} | ID: {hex_id}\nEstrutura: {name}{args_disp}",
        "hi": f"{kind_upper} | ID: {hex_id}\nसंरचना: {name}{args_disp}"
    }

    base_tip = headers.get(lang_key, headers["en"])
    if doc:
        return f"{base_tip}\n\n{doc}"
    return base_tip

