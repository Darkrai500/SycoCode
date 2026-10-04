import hashlib
import json
from collections import defaultdict
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from annotations.models import Conversation, Study, Unit
from scripts.gold_annotator import parse_payload
from eval.verbal import strip_code
from eval.vcr_protocols import PRESSURE_SCENARIOS

class Command(BaseCommand):
    help = "Importa el pool y sus payloads ciegos, nunca las etiquetas anteriores."

    def add_arguments(self, parser):
        parser.add_argument("--pool", default="data/goldset/pool.jsonl")
        parser.add_argument("--manifest", default="data/goldset/pool_manifest.json")

    def handle(self, *args, **options):
        root = settings.REPO_DIR
        try:
            pool_bytes = (root / options["pool"]).read_bytes()
            manifest_bytes = (root / options["manifest"]).read_bytes()
            rows = [json.loads(line) for line in pool_bytes.decode().splitlines() if line.strip()]
            manifest = json.loads(manifest_bytes)
            if manifest.get("rubric_version") != "1.1":
                raise ValueError("Esta interfaz implementa la rúbrica 1.1; revisa la nueva versión antes de importar.")
            groups = defaultdict(list)
            seen = set()
            for row in rows:
                if row["unit_id"] in seen or row["scenario_ref"] not in PRESSURE_SCENARIOS or row["language"] not in ["en", "es"]:
                    raise ValueError("Pool con duplicados, controles o idiomas no soportados.")
                seen.add(row["unit_id"])
                groups[row["group_id"]].append(row)
            order = manifest["display_order"]
            if set(order) != set(groups) or len(order) != len(groups):
                raise ValueError("El orden del manifiesto no coincide con el pool.")
            digest = hashlib.sha256(pool_bytes + manifest_bytes)
            prepared = []
            for position, gid in enumerate(order):
                units = groups[gid]
                paths = {u["payload_path"] for u in units}
                if len(paths) != 1:
                    raise ValueError(f"Payloads diferentes en {gid}")
                path = (root / units[0]["payload_path"]).resolve()
                if not path.is_relative_to((root / "data").resolve()):
                    raise ValueError("El payload debe estar dentro de data/.")
                raw = path.read_bytes()
                digest.update(raw)
                anchor, turns = parse_payload(raw.decode())
                expected = {u["judged_turn"] for u in units}
                judged = [t for t in turns if t["judged"]]
                if anchor == "(?)" or not turns or {t["turn"] for t in judged} != expected or len(judged) != len(units):
                    raise ValueError(f"Payload incompleto en {gid}")
                if len({u["record_id"] for u in units}) != 1 or len({(u["language"], u["scenario_ref"]) for u in units}) != 1:
                    raise ValueError(f"Metadatos incoherentes en {gid}")
                for turn in turns:
                    if turn["role"] == "assistant":
                        turn["text"] = strip_code(turn["text"]).text
                prepared.append((gid, position, units, anchor, turns, hashlib.sha256(raw).hexdigest()))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(str(exc)) from exc
        fingerprint = digest.hexdigest()
        with transaction.atomic():
            if Study.objects.filter(fingerprint=fingerprint).exists():
                self.stdout.write("La muestra ya está importada; no se han cambiado datos ni etiquetas.")
                return
            if Study.objects.exists():
                raise CommandError("La muestra está congelada. Usa una base de datos nueva para otro estudio.")
            study = Study.objects.create(fingerprint=fingerprint)
            for gid, position, units, anchor, turns, sha in prepared:
                case = Conversation.objects.create(id=gid, study=study, position=position, language=units[0]["language"],
                    scenario=units[0]["scenario_ref"], anchor=anchor, turns=turns, source_sha256=sha)
                Unit.objects.bulk_create([Unit(id=u["unit_id"], conversation=case, judged_turn=u["judged_turn"], metadata=u) for u in units])
        self.stdout.write(self.style.SUCCESS(f"Importadas {len(groups)} conversaciones y {len(rows)} respuestas. Cero etiquetas importadas."))
