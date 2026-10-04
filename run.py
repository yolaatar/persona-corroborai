"""Run the corroboration on a folder of extracts.

Usage:
    python run.py --data <dossier des extractions> --out <dossier de sortie>

The data folder is opened read-only. Results go to --out.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from corroborai.engine import run_engine
from corroborai.loader import load_inputs
from corroborai.report import write_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, type=Path, help="Dossier contenant les extractions Système A / B")
    parser.add_argument("--out", required=True, type=Path, help="Dossier de sortie du rapport")
    args = parser.parse_args()

    if args.out.resolve() == args.data.resolve() or args.data.resolve() in args.out.resolve().parents:
        parser.error("Le dossier de sortie ne doit pas être le dossier des données sources.")

    inputs = load_inputs(args.data)
    results, meta = run_engine(inputs)
    info = write_outputs(results, meta, inputs, args.data, args.out)

    print(f"Lignes source : {info['rows_source']}  |  lignes cible : {info['rows_target']}")
    for verdict, n in info["verdict_counts"].items():
        print(f"  {n:>3}  {verdict}")
    print(f"Rapport écrit dans : {args.out}")


if __name__ == "__main__":
    main()
