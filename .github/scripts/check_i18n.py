"""Comprueba que Consola_de_Comando/i18n.json es coherente entre idiomas.

Verifica que:
  - todos los idiomas tienen exactamente las mismas claves;
  - ningun valor esta vacio;
  - cada traduccion usa los mismos huecos {nombre} que el espanol.

Uso:  python .github/scripts/check_i18n.py
Sale con codigo 1 si encuentra problemas.
"""
import json
import os
import string
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
I18N = os.path.join(ROOT, "Consola_de_Comando", "i18n.json")
BASE = "es"


def placeholders(text):
    try:
        return sorted({f for _, f, _, _ in string.Formatter().parse(text) if f})
    except ValueError:
        return None  # llaves desbalanceadas


def main():
    with open(I18N, encoding="utf-8") as f:
        data = json.load(f)

    if BASE not in data:
        print(f"Falta el idioma base '{BASE}'.")
        return 1

    base = data[BASE]
    problems = []
    for lang, table in data.items():
        missing = sorted(set(base) - set(table))
        extra = sorted(set(table) - set(base))
        for key in missing:
            problems.append(f"[{lang}] falta la clave '{key}'")
        for key in extra:
            problems.append(f"[{lang}] clave '{key}' no existe en '{BASE}'")
        for key, value in table.items():
            if not isinstance(value, str) or not value.strip():
                problems.append(f"[{lang}] '{key}' esta vacia")
                continue
            if key in base and lang != BASE:
                ph, ph_base = placeholders(value), placeholders(base[key])
                if ph is None:
                    problems.append(f"[{lang}] '{key}' tiene llaves desbalanceadas")
                elif ph != ph_base:
                    problems.append(f"[{lang}] '{key}' usa {ph}, se esperaba {ph_base}")

    counts = ", ".join(f"{lang}={len(t)}" for lang, t in data.items())
    if problems:
        print(f"i18n.json: {len(problems)} problemas ({counts})")
        for p in problems:
            print("  " + p)
        return 1
    print(f"i18n.json correcto ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
