from __future__ import annotations

import re
from pathlib import Path


def next_afd_path(output_dir: Path, initial_sequence: str) -> Path:
    """Retorna o próximo nome AFD sem perder zeros à esquerda."""
    if not initial_sequence.isdigit():
        raise ValueError("A sequência inicial AFD deve conter somente números.")

    width = len(initial_sequence)
    pattern = re.compile(rf"^AFD(\d{{{width}}})\.txt$", re.IGNORECASE)
    highest = int(initial_sequence)

    if output_dir.is_dir():
        for candidate in output_dir.iterdir():
            match = pattern.fullmatch(candidate.name)
            if match:
                highest = max(highest, int(match.group(1)))

    next_sequence = str(highest + 1).zfill(width)
    if len(next_sequence) > width:
        raise OverflowError("A sequência numérica AFD excedeu o tamanho configurado.")
    return output_dir / f"AFD{next_sequence}.txt"

