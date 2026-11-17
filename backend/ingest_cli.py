"""Script CLI para ejecutar la ingesta de PDFs de ÁgoraIA hacia ChromaDB."""

import argparse
import json
import sys
from pathlib import Path

# Permite ejecutar el script directamente desde backend/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.ingestion import KnowledgeBaseIngestor


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indexa los PDFs de ética periodística e IA en ChromaDB para ÁgoraIA."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Elimina la base vectorial existente antes de volver a indexar.",
    )
    args = parser.parse_args()

    ingestor = KnowledgeBaseIngestor()
    result = ingestor.ingest_all(reset=args.reset)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
