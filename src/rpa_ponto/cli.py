from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api import PontoApiError, fetch_afd
from .config import Settings
from .converter import LayoutPendenteError, generate_import_file
from .erp import ErpAutomationError, import_into_erp
from .filename import AFD_PATTERN, next_afd_path, prune_afd_files
from .monitor import ExecutionReporter, rebuild_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automação de ponto para o ERP")
    parser.add_argument(
        "command",
        choices=("fetch", "import", "run", "report"),
        help="Etapa a executar",
    )
    parser.add_argument("--file", type=Path, help="Arquivo existente para importar")
    parser.add_argument("--output", type=Path, help="Caminho do arquivo gerado")
    return parser


def main() -> int:
    args = _parser().parse_args()
    reporter: ExecutionReporter | None = None
    try:
        settings = Settings.from_env()
        if args.command == "report":
            report = rebuild_report(settings.monitor_output_dir)
            print(f"Relatório HTML: {report.resolve()}")
            return 0
        reporter = ExecutionReporter.from_settings(settings, args.command)
        reporter.start()
        output = args.output or next_afd_path(
            Path("output"), settings.afd_initial_sequence
        )

        if args.command in {"fetch", "run"}:
            payload = fetch_afd(
                settings.ponto_api_url,
                settings.ponto_username,
                settings.ponto_password,
            )
            reporter.step("api_consultada")
            output = generate_import_file(payload, output)
            if AFD_PATTERN.fullmatch(output.name):
                removed = prune_afd_files(output.parent, settings.afd_keep_files)
                if removed:
                    print(f"AFDs antigos removidos: {len(removed)}")
            reporter.step("arquivo_gerado", message=output.name)
            print(f"Arquivo gerado: {output.resolve()}")

        if args.command in {"import", "run"}:
            import_file = args.file if args.command == "import" else output
            if import_file is None:
                raise ValueError("Use --file CAMINHO com o comando import.")
            import_into_erp(settings, import_file, reporter)
            print(f"Importação concluída no ERP: {import_file.resolve()}")
        reporter.finish("completed")
        return 0
    except (
        ValueError,
        FileNotFoundError,
        PontoApiError,
        LayoutPendenteError,
        ErpAutomationError,
    ) as exc:
        if reporter:
            reporter.finish("failed", str(exc))
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
