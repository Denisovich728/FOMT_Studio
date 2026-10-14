# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.8.0)
# Núcleo de Rutinas AI: Condiciones de Horarios de NPCs
# ============================================================
"""
npc_schedule_conditions.py
══════════════════════════════════════════════════════════════
Base de conocimiento de condiciones de activación de horarios
para los 32 aldeanos de Mineral Town (Harvest Moon: FoMT).
Alineado 100% con los punteros de la Master Table ROM en 0x3D9A4.
Mapea el retorno de las funciones evaluadoras nativas en ROM
(0x803DC64, 0x803DA24, 0x803DA7C, etc.) a condiciones legibles
en español: Clima, Días, Festivales, Matrimonio y Eventos Especiales.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass


# =============================================================================
# Diccionario canónico de condiciones por NPC_ID (0..31) y SCHEDULE_ID
# =============================================================================
NPC_SCHEDULE_CONDITIONS: Dict[int, Dict[int, Dict[str, Any]]] = {
    # 0: Lillia (Granja Avícola)
    0: {
        0: {
            "name": "Tormenta / Huracán / Ventisca",
            "short": "🌪️ Tormenta (En Casa)",
            "weather": "Tormenta / Ventisca",
            "days": "Cualquier día de mal tiempo",
            "detail": "Permanece confinada en el piso superior de la granja avícola debido a su delicada salud.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Atención en Tienda)",
            "short": "☀️ Lun-Sáb Soleado (Mostrador)",
            "weather": "Soleado / Nublado",
            "days": "Lunes a Sábado",
            "detail": "Atiende el mostrador de la Granja Avícola vendiendo gallinas y alimento de 11:00 a 16:00.",
            "icon": "☀️"
        },
        2: {
            "name": "Domingo (Día de Descanso / Paseo)",
            "short": "🚶 Domingo (Descanso en Granja)",
            "weather": "Cualquiera",
            "days": "Domingos",
            "detail": "La tienda de aves permanece cerrada. Descansa en su habitación o sale al corral.",
            "icon": "🚶"
        },
        3: {
            "name": "Día de Consulta Médica / Festival",
            "short": "🏥 Consulta Médica / Festival",
            "weather": "Soleado",
            "days": "Días festivos o cita médica",
            "detail": "Visita al Doctor en la Clínica Mineral para un chequeo médico de rutina.",
            "icon": "🏥"
        }
    },

    # 1: Rick (Granja Avícola)
    1: {
        0: {
            "name": "Tormenta / Clima Severo",
            "short": "🌪️ Tormenta (En Granja)",
            "weather": "Tormenta / Ventisca",
            "days": "Cualquier día",
            "detail": "Encierra a las aves en el gallinero y permanece dentro de la casa.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Trabajo y Paseo al Pueblo)",
            "short": "☀️ Lun-Sáb Soleado (Pueblo y Corral)",
            "weather": "Soleado",
            "days": "Lunes a Sábado",
            "detail": "Cuida a las gallinas por la mañana, atiende entregas en la Herrería y almuerza en la Posada.",
            "icon": "☀️"
        },
        2: {
            "name": "Martes Soleado (Día Libre / Charla con Doug)",
            "short": "🚶 Martes Libre (Posada de Doug)",
            "weather": "Soleado / Nublado",
            "days": "Martes",
            "detail": "Pasa la tarde en la Posada de Doug conversando en la taberna.",
            "icon": "🚶"
        },
        3: {
            "name": "Día Lluvioso (Trabajo Bajo Cubierto)",
            "short": "🌧️ Lluvioso (Dentro de Granja)",
            "weather": "Lluvia",
            "days": "Días lluviosos",
            "detail": "Realiza tareas dentro del gallinero y casa principal.",
            "icon": "🌧️"
        },
        4: {
            "name": "Festivales de Mineral Town",
            "short": "🎪 Festivales Locales",
            "weather": "Cualquiera",
            "days": "Días de festival",
            "detail": "Asiste a las festividades de la Plaza Rosa, en especial el Festival de Gallinas (7 de Verano).",
            "icon": "🎪"
        }
    },

    # 2: Popuri (Granja Avícola - Bachelorette)
    2: {
        0: {
            "name": "Tormenta / Tifón / Ventisca",
            "short": "🌪️ Tormenta (En Casa)",
            "weather": "Tormenta / Ventisca",
            "days": "Días extremos",
            "detail": "Confinada en su habitación del segundo piso de la Granja Avícola por mal tiempo.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Aguas Termales)",
            "short": "☀️ Lun-Sáb Soleado (Aguas Termales)",
            "weather": "Soleado / Despejado",
            "days": "Lunes a Sábado",
            "detail": "Paseo matutino a las Aguas Termales de 07:30 a 10:00, regreso a la Granja y por la tarde en casa.",
            "icon": "☀️"
        },
        2: {
            "name": "Lunes a Sábado Lluvioso (Permanencia en Granja)",
            "short": "🌧️ Lun-Sáb Lluvia (En Granja Avícola)",
            "weather": "Lluvia / Nieve",
            "days": "Lunes a Sábado",
            "detail": "Permanece dentro de la Granja Avícola cuidando las gallinas y charlando con Lillia.",
            "icon": "🌧️"
        },
        3: {
            "name": "Domingo Soleado [Prim/Oto/Inv] (Carter & Plaza Rosa)",
            "short": "⛪ Domingo Soleado (Iglesia / Plaza)",
            "weather": "Soleado (No Verano)",
            "days": "Domingos (Primavera, Otoño, Invierno)",
            "detail": "Asiste al servicio de la Iglesia con Carter de 10:00 a 13:00 y pasa la tarde en la Plaza Rosa de 13:30 a 16:00.",
            "icon": "⛪"
        },
        4: {
            "name": "Domingo Lluvioso (Confinamiento en Iglesia)",
            "short": "🌧️ Domingo Lluvia (Iglesia Carter)",
            "weather": "Lluvia / Nieve",
            "days": "Domingos Lluviosos",
            "detail": "Asiste a la Iglesia con Carter y permanece allí resguardada hasta las 16:00 antes de regresar.",
            "icon": "🌧️"
        },
        5: {
            "name": "Verano Soleado - Domingos (Cita en la Playa con Kai)",
            "short": "🏖️ Verano Soleado (Playa Mineral con Kai)",
            "weather": "Soleado (Verano)",
            "days": "Domingos de Verano",
            "detail": "Baja a la Playa Mineral de 13:00 a 16:00 a pasar la tarde junto al puesto de Kai.",
            "icon": "🏖️"
        },
        6: {
            "name": "Casada con el Jugador (Día de Granja Soleado)",
            "short": "👰 Casada (Granja Soleada)",
            "weather": "Soleado",
            "days": "Días ordinarios",
            "detail": "Vive en la Casa del Jugador, atiende la cocina y pasea por el terreno de la granja.",
            "icon": "👰"
        },
        7: {
            "name": "Casada (Visita Familiar a la Granja Avícola)",
            "short": "👰 Casada (Visita a Lillia)",
            "weather": "Soleado",
            "days": "Días de visita familiar",
            "detail": "Visita a su madre Lillia y a Rick en la Granja Avícola de 09:00 a 18:00.",
            "icon": "🚶"
        },
        8: {
            "name": "Casada con el Jugador (Día Lluvioso)",
            "short": "👰🌧️ Casada (Día Lluvioso en Granja)",
            "weather": "Lluvia / Nieve",
            "days": "Días de lluvia",
            "detail": "Permanece en la casa del jugador todo el día por el clima adverso.",
            "icon": "🌧️"
        },
        9: {
            "name": "Casada (Rutina Estacional Alternativa)",
            "short": "👰 Casada (Rutina Conyugal)",
            "weather": "Cualquiera",
            "days": "Temporadas específicas",
            "detail": "Vida cotidiana de matrimonio en la granja del jugador.",
            "icon": "👰"
        },
        10: {
            "name": "Casada (Visita de Fin de Semana a la Granja Avícola)",
            "short": "👰 Casada (Fin de Semana Avícola)",
            "weather": "Soleado",
            "days": "Domingos de casada",
            "detail": "Pasa el domingo en la Granja Avícola ayudando a Lillia.",
            "icon": "🚶"
        },
        11: {
            "name": "Casada con el Jugador (Otoño / Invierno)",
            "short": "👰 Casada (Temporada Fría)",
            "weather": "Soleado",
            "days": "Otoño / Invierno",
            "detail": "Rutina de invierno dentro de la casa del jugador.",
            "icon": "❄️"
        },
        12: {
            "name": "Casada (Rutina Especial 1)",
            "short": "👰 Casada (Rutina Especial)",
            "weather": "Cualquiera",
            "days": "Especial",
            "detail": "Rutina conyugal secundaria.",
            "icon": "👰"
        },
        13: {
            "name": "Casada (Rutina Especial 2)",
            "short": "👰 Casada (Rutina Especial)",
            "weather": "Cualquiera",
            "days": "Especial",
            "detail": "Rutina conyugal secundaria.",
            "icon": "👰"
        },
        14: {
            "name": "Casada (Rutina Especial 3)",
            "short": "👰 Casada (Rutina Especial)",
            "weather": "Cualquiera",
            "days": "Especial",
            "detail": "Rutina conyugal secundaria.",
            "icon": "👰"
        },
        15: {
            "name": "Casada (Rutina Especial 4)",
            "short": "👰 Casada (Rutina Especial)",
            "weather": "Cualquiera",
            "days": "Especial",
            "detail": "Rutina conyugal secundaria.",
            "icon": "👰"
        },
        16: {
            "name": "Festival de Gallinas (Granja Avícola)",
            "short": "🐔 Festival de Gallinas (7 Verano)",
            "weather": "Soleado",
            "days": "7 de Verano",
            "detail": "Preparativos matutinos del Festival de Gallinas en la Granja Avícola.",
            "icon": "🐔"
        },
        17: {
            "name": "Evento de Corazón: Visita a la Granja del Jugador (10:00 AM)",
            "short": "💖 Evento Corazón (Visita a Granja)",
            "weather": "Soleado",
            "days": "Día del evento",
            "detail": "Llega a la granja del jugador a las 10:00 para invitarle o regalarle un huevo.",
            "icon": "💖"
        },
        18: {
            "name": "Evento de Corazón: Encuentro Matutino (06:00 AM)",
            "short": "💖 Encuentro Matutino (Granja)",
            "weather": "Soleado",
            "days": "Día del evento",
            "detail": "Espera al jugador en el camino de la granja a las 06:00 AM.",
            "icon": "💖"
        },
        19: {
            "name": "Día de Agradecimiento de Primavera / Acción de Gracias",
            "short": "🍪 Día de Acción de Gracias (Galletas)",
            "weather": "Soleado",
            "days": "14 de Primavera / 14 de Invierno",
            "detail": "Entrega galletas o chocolates al jugador en Mineral Town.",
            "icon": "🍪"
        },
        20: {
            "name": "Festival de Fuegos Artificiales en la Playa",
            "short": "🎆 Festival de Fuegos Artificiales (Playa)",
            "weather": "Soleado",
            "days": "24 de Verano",
            "detail": "Baja a la Playa Mineral a ver los fuegos artificiales de noche.",
            "icon": "🎆"
        },
        21: {
            "name": "Cena Familiar / Noche en Granja Avícola",
            "short": "🌙 Noche en Granja Avícola",
            "weather": "Cualquiera",
            "days": "Especial",
            "detail": "Permanece en su habitación de la planta alta.",
            "icon": "🌙"
        },
        22: {
            "name": "Casada: Búsqueda en Mina de la Cascada",
            "short": "👰⛏️ Casada (Mina de Cascada)",
            "weather": "Soleado",
            "days": "Días de exploración",
            "detail": "Acompaña o visita la zona de la cascada y mina.",
            "icon": "⛏️"
        },
        23: {
            "name": "Aniversario de Bodas / Cumpleaños con Jugador",
            "short": "🎂 Aniversario / Cumpleaños",
            "weather": "Cualquiera",
            "days": "Día festivo conyugal",
            "detail": "Celebración en la mesa principal de la casa del jugador.",
            "icon": "🎂"
        }
    },

    # 3: Harris (Policía)
    3: {
        0: {
            "name": "Tormenta / Emergencia",
            "short": "🌪️ Tormenta (En Alcaldía)",
            "weather": "Tormenta / Ventisca",
            "days": "Cualquier día severo",
            "detail": "Permanece de guardia en la casa del Alcalde Thomas coordinando la seguridad.",
            "icon": "🌪️"
        },
        1: {
            "name": "Patrulla Diaria Soleada (Mineral Town)",
            "short": "👮 Patrulla General Soleada",
            "weather": "Soleado",
            "days": "Lunes a Domingo",
            "detail": "Ronda matutina por Pueblo Norte y Sur, almuerza en la Posada y patrulla la Granja Yodel por la tarde.",
            "icon": "👮"
        },
        2: {
            "name": "Patrulla en Día Lluvioso",
            "short": "🌧️ Patrulla con Lluvia",
            "weather": "Lluvia",
            "days": "Días de lluvia",
            "detail": "Ronda preventiva con paraguas protegiendo las propiedades de los aldeanos.",
            "icon": "🌧️"
        }
    },

    # 4: Barley (Granja Yodel)
    4: {
        0: {
            "name": "Tormenta / Ventisca",
            "short": "🌪️ Tormenta (En Granja Yodel)",
            "weather": "Tormenta",
            "days": "Cualquier día severo",
            "detail": "Se resguarda en la casa principal de la Granja Yodel cuidando del ganado.",
            "icon": "🌪️"
        },
        1: {
            "name": "Martes a Domingo Soleado (Atención en Granja)",
            "short": "🐄 Lun-Dom Soleado (Venta de Ganado)",
            "weather": "Soleado",
            "days": "Martes a Domingo (Excepto Lunes)",
            "detail": "Vende vacas, ovejas y suministros ganaderos en la Granja Yodel de 08:00 a 15:00.",
            "icon": "🐄"
        },
        2: {
            "name": "Lunes Soleado (Día Libre / Aguas Termales)",
            "short": "♨️ Lunes Libre (Aguas Termales con May)",
            "weather": "Soleado",
            "days": "Lunes",
            "detail": "La tienda cierra. Barley lleva a May a las Aguas Termales y visita al Alcalde Thomas.",
            "icon": "♨️"
        }
    },

    # 5: Saibara (Herrero)
    5: {
        0: {
            "name": "Tormenta / Huracán",
            "short": "🌪️ Tormenta (En Herrería)",
            "weather": "Tormenta",
            "days": "Cualquier día severo",
            "detail": "Mantiene el fuego apagado y descansa dentro del taller.",
            "icon": "🌪️"
        },
        1: {
            "name": "Viernes a Miércoles Soleado (Fragua Abierta)",
            "short": "⚒️ Vie-Mié Soleado (Fragua Abierta)",
            "weather": "Soleado",
            "days": "Viernes a Miércoles (Excepto Jueves)",
            "detail": "Forja herramientas y accesorios de mithril y oricalco en el taller de 10:00 a 16:00.",
            "icon": "⚒️"
        },
        2: {
            "name": "Jueves Soleado (Día Libre / Cima de la Colina)",
            "short": "🚶 Jueves Libre (Colina Madre y Posada)",
            "weather": "Soleado",
            "days": "Jueves",
            "detail": "El taller está cerrado. Sube a la Cima de la Colina Madre y por la tarde cena en la Posada.",
            "icon": "🚶"
        }
    },

    # 6: Gray (Aprendiz de Herrero)
    6: {
        0: {
            "name": "Tormenta / Ventisca",
            "short": "🌪️ Tormenta (En Posada)",
            "weather": "Tormenta",
            "days": "Cualquier día severo",
            "detail": "Pasa el día encerrado en su habitación del segundo piso de la Posada de Doug.",
            "icon": "🌪️"
        },
        1: {
            "name": "Viernes a Miércoles Soleado (Aprendizaje en Herrería)",
            "short": "⚒️ Vie-Mié Soleado (Herrería y Biblioteca)",
            "weather": "Soleado",
            "days": "Viernes a Miércoles (Excepto Jueves)",
            "detail": "Trabaja en la forja por la mañana (07:00-13:00) y va a la Biblioteca a leer y ver a Mary por la tarde.",
            "icon": "⚒️"
        },
        2: {
            "name": "Jueves Soleado (Día Libre / Cima de la Montaña)",
            "short": "🚶 Jueves Libre (Cima de Colina Madre)",
            "weather": "Soleado",
            "days": "Jueves",
            "detail": "Taller cerrado. Sube a la Cima de la Colina Madre a despejarse de 08:00 a 13:00.",
            "icon": "🚶"
        },
        3: {
            "name": "Lunes (Biblioteca Cerrada / Tarde en la Posada)",
            "short": "📖 Lunes (Descanso en Posada)",
            "weather": "Cualquiera",
            "days": "Lunes",
            "detail": "Como la Biblioteca está cerrada, pasa toda la tarde en la Posada practicando artesanías.",
            "icon": "📖"
        }
    },

    # 7: Duke (Bodega Aja)
    7: {
        0: {
            "name": "Tormenta / Huracán",
            "short": "🌪️ Tormenta (En Bodega)",
            "weather": "Tormenta",
            "days": "Cualquier día severo",
            "detail": "Se resguarda en la bodega y supervisa que los barriles de vino no sufran daños.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Trabajo en Viñedo y Bar)",
            "short": "🍇 Lun-Sáb Soleado (Viñedo y Taberna)",
            "weather": "Soleado",
            "days": "Lunes a Sábado",
            "detail": "Pasa la mañana en el viñedo y bodega, y cada noche de 19:30 a 22:00 bebe en la Posada de Doug.",
            "icon": "🍇"
        },
        2: {
            "name": "Domingo (Día de Descanso / Iglesia)",
            "short": "⛪ Domingo (Servicio en Iglesia)",
            "weather": "Cualquiera",
            "days": "Domingos",
            "detail": "Descansa de los viñedos y acude a la Iglesia de Carter.",
            "icon": "⛪"
        }
    },

    # 8: Manna (Bodega Aja)
    8: {
        0: {
            "name": "Tormenta / Clima Severo",
            "short": "🌪️ Tormenta (En Casa)",
            "weather": "Tormenta",
            "days": "Cualquier día severo",
            "detail": "Permanece dentro de la vivienda de la Bodega.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Venta de Vino y Charla)",
            "short": "🍷 Lun-Sáb Soleado (Tienda de Vino y Plaza)",
            "weather": "Soleado",
            "days": "Lunes a Sábado",
            "detail": "Atiende el mostrador de la Bodega por la mañana y pasa la tarde charlando en la Plaza Rosa.",
            "icon": "🍷"
        }
    },

    # 9: Basil (Botánico)
    9: {
        0: {
            "name": "Tormenta / Ventisca",
            "short": "🌪️ Tormenta (En Estudio)",
            "weather": "Tormenta",
            "days": "Cualquier día severo",
            "detail": "Se queda en su estudio escribiendo libros de flora y botánica.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Domingo Soleado (Investigación de Montaña)",
            "short": "🌿 Diario Soleado (Colina Madre y Taberna)",
            "weather": "Soleado",
            "days": "Lunes a Domingo",
            "detail": "Sube a la Colina Madre a recolectar muestras de hierbas y plantas, y cena en la Posada.",
            "icon": "🌿"
        }
    },

    # 10: Anna (Esposa de Basil)
    10: {
        0: {
            "name": "Tormenta / Huracán",
            "short": "🌪️ Tormenta (En Casa)",
            "weather": "Tormenta",
            "days": "Cualquier día severo",
            "detail": "Permanece en su casa cuidando del hogar.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Té y Charla en Plaza Rosa)",
            "short": "☕ Lun-Sáb Soleado (Plaza Rosa con Manna)",
            "weather": "Soleado",
            "days": "Lunes a Sábado",
            "detail": "Se reúne con Manna y Sasha en la Plaza Rosa para tomar el té y charlar de 13:00 a 16:00.",
            "icon": "☕"
        }
    },

    # 11: Mary (Biblioteca - Bachelorette)
    11: {
        0: {
            "name": "Tormenta / Huracán / Ventisca",
            "short": "🌪️ Tormenta (En Casa)",
            "weather": "Tormenta / Ventisca",
            "days": "Cualquier día",
            "detail": "El clima extremo obliga a permanecer en casa. La biblioteca y tiendas están cerradas.",
            "icon": "🌪️"
        },
        1: {
            "name": "Martes a Domingo Soleado (Biblioteca Abierta)",
            "short": "☀️ Mar-Dom Soleado (Biblioteca)",
            "weather": "Soleado / Nublado",
            "days": "Martes a Domingo",
            "detail": "Atiende en el mostrador de la Biblioteca de 09:00 a 16:00 y ayuda a los lectores.",
            "icon": "☀️"
        },
        2: {
            "name": "Lunes Soleado (Día Libre / Colina Madre)",
            "short": "🚶 Lunes Soleado (Colina Madre con Padres)",
            "weather": "Soleado",
            "days": "Lunes",
            "detail": "Biblioteca cerrada. Sube por la mañana a la Colina Madre y pasa por el Supermercado por la tarde.",
            "icon": "🚶"
        },
        3: {
            "name": "Lunes Lluvioso (Visita a la Casa de Ellen)",
            "short": "🌧️ Lunes Lluvia (Casa de Ellen y Jeff)",
            "weather": "Lluvia",
            "days": "Lunes lluviosos",
            "detail": "Va a la Casa de Ellen a charlar con Stu y luego compra en el Supermercado de Jeff.",
            "icon": "🌧️"
        },
        4: {
            "name": "Festivales de Mineral Town",
            "short": "🎪 Festivales Locales",
            "weather": "Cualquiera",
            "days": "Días festivos",
            "detail": "Participa en los eventos festivos en la Plaza Rosa o la Playa.",
            "icon": "🎪"
        }
    },

    # 12: Thomas (Alcalde)
    12: {
        0: {
            "name": "Tormenta / Emergencia",
            "short": "🌪️ Tormenta (En Alcaldía)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Coordina las medidas del pueblo desde su residencia oficial.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Domingo Soleado (Gestión Municipal)",
            "short": "🏛️ Diario Soleado (Visitas y Alcaldía)",
            "weather": "Soleado",
            "days": "Lunes a Domingo",
            "detail": "Atiende en la Alcaldía por la mañana, visita la Casa de Ellen y almuerza en el Supermercado.",
            "icon": "🏛️"
        }
    },

    # 13: Kano (Fotógrafo)
    13: {
        0: {
            "name": "Tormenta / Ventisca",
            "short": "🌪️ Tormenta (En Alcaldía)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Permanece en su habitación de la casa del Alcalde Thomas.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Domingo Soleado (Fotografía y Paseo)",
            "short": "📷 Diario Soleado (Bosque y Granja Yodel)",
            "weather": "Soleado",
            "days": "Lunes a Domingo",
            "detail": "Recorre el Bosque de Gotz y la Granja Yodel tomando fotografías de animales y paisajes.",
            "icon": "📷"
        }
    },

    # 14: Ellen (Abuela)
    14: {
        0: {
            "name": "Horario Perpetuo (En Mecedora)",
            "short": "👵 Confinada en Mecedora (Todo Clima)",
            "weather": "Cualquiera",
            "days": "Todos los días del año",
            "detail": "Permanece sentada en su mecedora en la sala de su casa recibiendo a los aldeanos y al jugador.",
            "icon": "👵"
        }
    },

    # 15: Stu (Nieto de Ellen)
    15: {
        0: {
            "name": "Tormenta / Lluvia Severa",
            "short": "🌪️ Tormenta (En Casa con Ellen)",
            "weather": "Tormenta / Lluvia",
            "days": "Días de mal tiempo",
            "detail": "Juega dentro de la casa junto a su abuela Ellen.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Domingo Soleado (Juegos en Plaza e Iglesia)",
            "short": "⚽ Diario Soleado (Pueblo y Granja)",
            "weather": "Soleado",
            "days": "Lunes a Domingo",
            "detail": "Corre por el pueblo, juega al escondite con May y visita la Iglesia de Carter.",
            "icon": "⚽"
        }
    },

    # 16: Jeff (Supermercado)
    16: {
        0: {
            "name": "Tormenta / Huracán",
            "short": "🌪️ Tormenta (Trastienda)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Permanece en la trastienda cuidando el inventario de provisiones.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Mostrador de Ventas)",
            "short": "🛒 Lun-Sáb Soleado (Supermercado Abierto)",
            "weather": "Soleado",
            "days": "Lunes a Sábado (Excepto Martes y Domingo)",
            "detail": "Atiende el mostrador vendiendo semillas, harina y provisiones de 09:00 a 17:00.",
            "icon": "🛒"
        },
        2: {
            "name": "Martes y Domingo (Día Libre / Pintura)",
            "short": "🎨 Días Libres (Iglesia y Clínica)",
            "weather": "Cualquiera",
            "days": "Martes y Domingos",
            "detail": "Tienda cerrada. Va a la Iglesia a orar, consulta al Doctor y cena en la Posada.",
            "icon": "🎨"
        }
    },

    # 17: Sasha (Supermercado)
    17: {
        0: {
            "name": "Tormenta / Ventisca",
            "short": "🌪️ Tormenta (En Trastienda)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Permanece dentro del hogar familiar en el Supermercado.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Supermercado y Plaza)",
            "short": "☕ Lun-Sáb Soleado (Plaza Rosa con Amigas)",
            "weather": "Soleado",
            "days": "Lunes a Sábado",
            "detail": "Ayuda a Jeff por la mañana y baja a la Plaza Rosa a charlar con Anna y Manna de 13:00 a 16:00.",
            "icon": "☕"
        }
    },

    # 18: Karen (Supermercado - Bachelorette)
    18: {
        0: {
            "name": "Tormenta / Huracán / Ventisca",
            "short": "🌪️ Tormenta (En Trastienda)",
            "weather": "Tormenta / Ventisca",
            "days": "Días extremos",
            "detail": "Permanece confinada en el Supermercado ayudando a sus padres.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Supermercado y Aguas Termales)",
            "short": "☀️ Lun-Sáb Soleado (Supermercado y Banco)",
            "weather": "Soleado",
            "days": "Lunes a Sábado (Excepto Martes y Domingo)",
            "detail": "Atiende en la tienda, descansa en el banco exterior y cena en la Posada de Doug cada noche.",
            "icon": "☀️"
        },
        2: {
            "name": "Martes Soleado (Día Libre / Paseo a las Aguas Termales)",
            "short": "♨️ Martes Soleado (Aguas Termales)",
            "weather": "Soleado",
            "days": "Martes",
            "detail": "Pasea hasta las Aguas Termales de 10:00 a 13:00 y por la tarde visita la Posada.",
            "icon": "♨️"
        },
        3: {
            "name": "Domingo Soleado (Taberna de Doug por la Noche)",
            "short": "🍺 Domingo Noche (Posada de Doug)",
            "weather": "Soleado / Nublado",
            "days": "Domingos",
            "detail": "Pasa la tarde en la Playa Mineral y la noche en la taberna de la Posada bebiendo vino.",
            "icon": "🍺"
        },
        4: {
            "name": "Día Lluvioso (Dentro del Supermercado)",
            "short": "🌧️ Lluvioso (En Supermercado)",
            "weather": "Lluvia",
            "days": "Días lluviosos",
            "detail": "Pasa el día completo dentro del Supermercado protegiéndose del agua.",
            "icon": "🌧️"
        }
    },

    # 19: Doctor (Clínica Mineral)
    19: {
        0: {
            "name": "Tormenta / Emergencia Médica",
            "short": "🌪️ Tormenta (En Consulta)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Permanece en la Clínica de guardia para emergencias médicas del pueblo.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Consultas Médicas)",
            "short": "🩺 Lun-Sáb Soleado (Clínica Abierta)",
            "weather": "Soleado / Nublado",
            "days": "Lunes a Sábado (Excepto Miércoles)",
            "detail": "Atiende a los pacientes en la Clínica Mineral de 09:00 a 19:00 junto a Elli.",
            "icon": "🩺"
        },
        2: {
            "name": "Miércoles Soleado (Día Libre / Montaña e Iglesia)",
            "short": "🚶 Miércoles Libre (Colina Madre y Biblioteca)",
            "weather": "Soleado",
            "days": "Miércoles",
            "detail": "Clínica cerrada. Sube a la Colina Madre a buscar hierbas medicinales y visita la Iglesia.",
            "icon": "🚶"
        }
    },

    # 20: Elli (Enfermera de la Clínica - Bachelorette)
    20: {
        0: {
            "name": "Tormenta / Clima Severo",
            "short": "🌪️ Tormenta (En Clínica)",
            "weather": "Tormenta / Ventisca",
            "days": "Días extremos",
            "detail": "Permanece en la habitación de la planta alta de la Clínica cuidando de los enfermos.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Enfermería en Clínica)",
            "short": "🩺 Lun-Sáb Soleado (Atención en Clínica)",
            "weather": "Soleado",
            "days": "Lunes a Sábado (Excepto Miércoles)",
            "detail": "Ayuda al Doctor, receta medicamentos y atiende a los aldeanos de 09:00 a 19:00.",
            "icon": "🩺"
        },
        2: {
            "name": "Miércoles Soleado (Día Libre / Visita a la Abuela Ellen)",
            "short": "👵 Miércoles Libre (Casa de Ellen y Jeff)",
            "weather": "Soleado",
            "days": "Miércoles",
            "detail": "Clínica cerrada. Pasa todo el día cocinando y cuidando a su abuela Ellen y a su hermano Stu.",
            "icon": "👵"
        },
        3: {
            "name": "Festivales de Mineral Town",
            "short": "🎪 Festivales Locales",
            "weather": "Cualquiera",
            "days": "Días festivos",
            "detail": "Asiste a los festivales del pueblo en la Plaza Rosa.",
            "icon": "🎪"
        }
    },

    # 21: Carter (Pastor de la Iglesia)
    21: {
        0: {
            "name": "Tormenta / Oración en Iglesia",
            "short": "🌪️ Tormenta (Refugio en Iglesia)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Mantiene las puertas de la Iglesia abiertas como refugio para quien lo necesite.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Domingo Soleado (Misa y Confesionario)",
            "short": "⛪ Diario Soleado (Servicio Religioso)",
            "weather": "Soleado",
            "days": "Lunes a Domingo",
            "detail": "Ofrece misa, atiende el confesionario y pasea por el patio trasero a tocar música de 09:00 a 16:00.",
            "icon": "⛪"
        }
    },

    # 22: Cliff (Posada / Bodega)
    22: {
        0: {
            "name": "Tormenta / Ventisca",
            "short": "🌪️ Tormenta (En Posada)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Permanece en su habitación alquilada en la Posada de Doug.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado (Trabajo en Viñedos de Aja)",
            "short": "🍇 Lun-Sáb (Cosecha en Bodega Aja)",
            "weather": "Soleado",
            "days": "Lunes a Sábado",
            "detail": "Trabaja cosechando uvas en la Bodega Aja de 10:00 a 16:00 (si tiene empleo).",
            "icon": "🍇"
        },
        2: {
            "name": "Domingo (Oración en Iglesia de Carter)",
            "short": "⛪ Domingo (Oración en Iglesia)",
            "weather": "Cualquiera",
            "days": "Domingos",
            "detail": "Pasa la mayor parte del día rezando y reflexionando en la Iglesia de Carter.",
            "icon": "⛪"
        }
    },

    # 23: Doug (Posadero)
    23: {
        0: {
            "name": "Tormenta / Servicio de Huéspedes",
            "short": "🌪️ Tormenta (En Taberna)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Atiende a los huéspedes confinados en la Posada y cocina platos calientes.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Domingo Soleado (Atención en Taberna)",
            "short": "🍳 Diario Soleado (Cocina y Mostrador)",
            "weather": "Soleado",
            "days": "Lunes a Domingo",
            "detail": "Cocina recetas tradicionales y atiende a los clientes de la taberna de 08:00 a 22:00.",
            "icon": "🍳"
        }
    },

    # 24: Ann (Posada de Doug - Bachelorette)
    24: {
        0: {
            "name": "Tormenta / Huracán / Ventisca",
            "short": "🌪️ Tormenta (En Posada)",
            "weather": "Tormenta / Ventisca",
            "days": "Cualquier día",
            "detail": "Permanece confinada en la Posada de Doug sin salir al exterior.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Domingo Soleado (Limpieza y Cocina)",
            "short": "🍳 Lun-Dom Soleado (Posada Abierta)",
            "weather": "Soleado",
            "days": "Lunes a Domingo",
            "detail": "Limpia las habitaciones, cocina con Doug y atiende a los clientes en el mostrador.",
            "icon": "🍳"
        },
        2: {
            "name": "Paseo Matutino a las Aguas Termales",
            "short": "♨️ Mañana Soleada (Aguas Termales)",
            "weather": "Soleado",
            "days": "Días despejados",
            "detail": "Sube a las Aguas Termales de 07:30 a 10:00 antes de empezar el trabajo en la Posada.",
            "icon": "♨️"
        },
        3: {
            "name": "Festivales de Mineral Town",
            "short": "🎪 Festivales Locales",
            "weather": "Cualquiera",
            "days": "Días festivos",
            "detail": "Participa en las fiestas locales, especialmente el Concurso de Cocina (22 de Primavera).",
            "icon": "🎪"
        }
    },

    # 25: Kai (Chiringuito de Playa)
    25: {
        0: {
            "name": "Tormenta / Mal Tiempo en Playa",
            "short": "🌪️ Tormenta (En Posada)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "El chiringuito cierra y Kai permanece a resguardo en la Posada de Doug.",
            "icon": "🌪️"
        },
        1: {
            "name": "Verano Soleado (Atención en Chiringuito)",
            "short": "🏖️ Verano Soleado (Chiringuito de Playa)",
            "weather": "Soleado (Verano)",
            "days": "Lunes a Sábado de Verano",
            "detail": "Vende maíz asado, espaguetis y batidos en el chiringuito de la Playa de 11:00 a 17:00.",
            "icon": "🏖️"
        },
        2: {
            "name": "Domingo de Verano (Paseo por la Playa con Popuri)",
            "short": "🌊 Domingo de Verano (Playa Mineral)",
            "weather": "Soleado (Verano)",
            "days": "Domingos de Verano",
            "detail": "Pasea por la orilla del mar conversando con Popuri y descansando en el muelle.",
            "icon": "🌊"
        }
    },

    # 26: Gotz (Carpintero)
    26: {
        0: {
            "name": "Tormenta / Huracán",
            "short": "🌪️ Tormenta (En Cabaña)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Permanece en su cabaña del bosque afilando hachas y sierras.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Sábado Soleado (Taller y Tala en Bosque)",
            "short": "🪓 Lun-Sáb Soleado (Cabaña y Tala de Leña)",
            "weather": "Soleado",
            "days": "Lunes a Sábado (Excepto Domingo)",
            "detail": "Vende madera y ofrece ampliaciones de la granja de 11:00 a 16:00, y tala leña en el bosque.",
            "icon": "🪓"
        },
        2: {
            "name": "Domingo (Paseo a la Montaña y Cima)",
            "short": "🚶 Domingo Libre (Cima de Colina Madre)",
            "weather": "Soleado",
            "days": "Domingos",
            "detail": "Taller cerrado. Sube a la Cima de la Colina Madre a recordar a su familia.",
            "icon": "🚶"
        }
    },

    # 27: Zack (Comprador de la Playa)
    27: {
        0: {
            "name": "Tormenta / Huracán",
            "short": "🌪️ Tormenta (En Casa de Playa)",
            "weather": "Tormenta",
            "days": "Días extremos",
            "detail": "Permanece en su casa de la playa revisando pedidos comerciales.",
            "icon": "🌪️"
        },
        1: {
            "name": "Lunes a Domingo Soleado (Recogida de Envíos a las 17:00)",
            "short": "📦 Diario Soleado (Recogida en Granja)",
            "weather": "Soleado / Nublado",
            "days": "Lunes a Domingo",
            "detail": "Llega a la Granja del Jugador puntualmente a las 17:00 para vaciar el buzón de envíos y pagar las ganancias.",
            "icon": "📦"
        }
    },

    # 28: Won (Vendedor Ambulante)
    28: {
        0: {
            "name": "Horario Comercial Continuo",
            "short": "🍎 Venta en Casa de Zack (11:00 a 16:30)",
            "weather": "Cualquiera",
            "days": "Lunes a Domingo",
            "detail": "Vende semillas raras, bolas de perro y compra productos en la Casa de Zack de la Playa.",
            "icon": "🍎"
        }
    },

    # 29: Van (Comerciante Viajero)
    29: {
        0: {
            "name": "Miércoles de Visita a Mineral Town",
            "short": "💎 Miércoles (Posada de Doug Planta Alta)",
            "weather": "Cualquiera",
            "days": "Miércoles (Si está desbloqueado)",
            "detail": "Abre su tienda secreta de minerales raros y discos en el segundo piso de la Posada.",
            "icon": "💎"
        }
    },

    # 30: Lou (Cocinera Viajera)
    30: {
        0: {
            "name": "Domingo de Visita a Mineral Town",
            "short": "🍲 Domingos (Posada de Doug Planta Alta)",
            "weather": "Cualquiera",
            "days": "Domingos (Si está desbloqueada)",
            "detail": "Comparte recetas culinarias gourmet en la Posada de Doug.",
            "icon": "🍲"
        }
    },

    # 31: Gourmet (Juez Gastronómico)
    31: {
        0: {
            "name": "Festival de Cocina (22 de Primavera)",
            "short": "🍽️ Festival de Cocina (22 de Primavera)",
            "weather": "Soleado",
            "days": "22 de Primavera",
            "detail": "Juez principal del concurso de cocina en la Plaza Rosa de 10:00 a 18:00.",
            "icon": "🍽️"
        }
    }
}


@dataclass
class ScheduleCondition:
    """Clase de conveniencia para encapsular las condiciones de activación de horarios."""
    name: str
    short: str
    weather: str
    days: str
    detail: str
    icon: str = "📅"
    location_badge: str = "Mineral Town"
    is_festival: bool = False
    is_marriage: bool = False

    @property
    def condition_desc(self) -> str:
        return self.detail

    @classmethod
    def from_data(cls, data):
        if isinstance(data, cls):
            return data
        if isinstance(data, dict):
            name = data.get("name", "Horario")
            short = data.get("short", name)
            weather = data.get("weather", "Cualquiera")
            days = data.get("days", "Cualquiera")
            detail = data.get("detail", "")
            icon = data.get("icon", "📅")
            is_fest = data.get("is_festival", False) or "festival" in name.lower() or "festival" in days.lower()
            is_marr = data.get("is_marriage", False) or "matrimonio" in name.lower() or "casad" in name.lower()
            loc = data.get("location_badge", "Mineral Town")
            if loc == "Mineral Town":
                if "(" in short and ")" in short:
                    loc = short.split("(")[1].split(")")[0]
                elif "[" in short and "]" in short:
                    loc = short.split("[")[1].split("]")[0]
            return cls(
                name=name, short=short, weather=weather, days=days,
                detail=detail, icon=icon, location_badge=loc,
                is_festival=is_fest, is_marriage=is_marr
            )
        return cls("Horario", "Horario", "Cualquiera", "Cualquiera", "")


def get_schedule_condition_info(npc_id: int, schedule_id: int, waypoints: Optional[list] = None) -> Dict[str, Any]:
    """
    Retorna la información completa de la condición de activación para un horario específico.
    Si no existe una regla fija, genera una estimación heurística precisa a partir de los waypoints.
    """
    npc_dict = NPC_SCHEDULE_CONDITIONS.get(npc_id, {})
    cond = npc_dict.get(schedule_id)
    if cond:
        return cond

    # Heurística contextual según la ruta y waypoints del NPC
    wps = waypoints or []
    first_map = (wps[0].map_id & 0xFF) if wps and hasattr(wps[0], "map_id") else None

    # 1. Rutina matrimonial: La bachelorette vive en la Granja del Jugador (0x1D)
    if first_map == 0x1D:
        sub_type = "Vida Conyugal en la Granja"
        icon = "👰"
        if len(wps) == 1:
            desc = "Permanece en la casa de la granja cuidando del hogar durante todo el día."
        elif any((wp.map_id & 0xFF) in (0x05, 0x06, 0x07) for wp in wps):
            sub_type = "Visita al Pueblo (Casada)"
            desc = "Pasea por el pueblo durante la tarde y regresa a la granja por la noche."
            icon = "🛍️"
        else:
            desc = "Rutina matrimonial diaria en la granja del jugador."

        return {
            "name": f"Matrimonio: {sub_type} (#{schedule_id})",
            "short": f"{icon} Casada ({sub_type})",
            "weather": "Cualquier clima",
            "days": "Días ordinarios de casada",
            "detail": desc,
            "icon": icon,
            "location_badge": "Granja del Jugador",
            "is_marriage": True,
            "is_festival": False
        }

    # 2. Gotz (26): Obras de ampliación en la Granja
    if npc_id == 26:
        if first_map == 0x1D:
            return {
                "name": "Ampliación de la Casa del Jugador",
                "short": "🔨 Carpintería (Ampliando Casa)",
                "weather": "Soleado",
                "days": "3 días continuos de obra",
                "detail": "Trabaja martillando y ampliando la casa del jugador de 06:00 a 18:00.",
                "icon": "🔨",
                "location_badge": "Granja del Jugador"
            }
        elif first_map == 0x11:
            return {
                "name": "Ampliación del Gallinero",
                "short": "🔨 Carpintería (Ampliando Gallinero)",
                "weather": "Soleado",
                "days": "3 días continuos de obra",
                "detail": "Trabaja en la ampliación del gallinero de la granja para albergar 8 gallinas.",
                "icon": "🔨",
                "location_badge": "Gallinero de la Granja"
            }
        elif first_map == 0x25:
            return {
                "name": "Ampliación del Establo de Animales",
                "short": "🔨 Carpintería (Ampliando Establo)",
                "weather": "Soleado",
                "days": "3 días continuos de obra",
                "detail": "Trabaja en la ampliación del establo de vacas y ovejas para albergar 16 animales.",
                "icon": "🔨",
                "location_badge": "Establo de la Granja"
            }

    # 3. Día de Festival / Evento (1 solo hito y en mapas públicos)
    if len(wps) == 1 and first_map in (0x01, 0x06, 0x08, 0x00, 0x07):
        return {
            "name": f"Día de Festival en Mineral Town (#{schedule_id})",
            "short": "🎪 Festival de Mineral Town",
            "weather": "Soleado",
            "days": "Días de festival",
            "detail": "Permanece en la plaza o playa celebrando el festival del pueblo.",
            "icon": "🎪",
            "location_badge": "Zona de Festival",
            "is_festival": True
        }

    # 4. Horario 0 con estancia en casa: Tormenta
    if schedule_id == 0:
        return {
            "name": f"Tormenta / Huracán / Confinamiento (#{schedule_id})",
            "short": f"🌪️ Tormenta (En Casa)",
            "weather": "Tormenta / Ventisca",
            "days": "Días severos",
            "detail": "Permanece a resguardo dentro de casa debido al temporal extremo.",
            "icon": "🌪️",
            "location_badge": "Interior"
        }

    # 5. Fallback descriptivo con conteo de hitos
    times_summary = ""
    if wps and len(wps) > 0:
        first_t = wps[0].time_to_str() if hasattr(wps[0], 'time_to_str') else ""
        times_summary = f"Inicia a las {first_t}."

    return {
        "name": f"Horario Condicional #{schedule_id}",
        "short": f"⚙️ Horario #{schedule_id} ({len(wps)} hitos)",
        "weather": "Condicional / Evento",
        "days": "Días designados",
        "detail": f"Rutina orquestada en ROM con {len(wps)} hitos. {times_summary}",
        "icon": "⚙️",
        "location_badge": "Mineral Town"
    }


def get_npc_schedule_condition(npc_id: int, schedule_id: int, schedule_or_waypoints=None) -> ScheduleCondition:
    """Obtiene la condición de activación como un objeto estructurado ScheduleCondition."""
    wps = getattr(schedule_or_waypoints, 'waypoints', schedule_or_waypoints) if schedule_or_waypoints else None
    info = get_schedule_condition_info(npc_id, schedule_id, wps)
    return ScheduleCondition.from_data(info)
