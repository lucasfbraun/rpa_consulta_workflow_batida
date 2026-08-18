from __future__ import annotations

import re
from pathlib import Path


AFD_PATTERN = re.compile(r"^AFD(\d+)\.txt$", re.IGNORECASE)


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


def prune_afd_files(output_dir: Path, keep: int = 1) -> list[Path]:
    """Remove AFDs antigos somente entre os filhos diretos de output_dir."""
    if keep < 1:
        raise ValueError("A quantidade de AFDs mantidos deve ser pelo menos 1.")
    if not output_dir.is_dir():
        return []

    resolved_output = output_dir.resolve()
    candidates: list[tuple[int, Path]] = []
    for candidate in output_dir.iterdir():
        match = AFD_PATTERN.fullmatch(candidate.name)
        if match and candidate.is_file():
            candidates.append((int(match.group(1)), candidate))
    candidates.sort(key=lambda item: item[0], reverse=True)

    removed = []
    for _, candidate in candidates[keep:]:
        resolved = candidate.resolve()
        if resolved.parent == resolved_output:
            resolved.unlink()
            removed.append(resolved)
    return removed
