import itertools
import json
import os
import random
import secrets
from collections import defaultdict
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import transaction
from annotations.models import Assignment, Conversation, Profile
from annotations.services import progress

class Command(BaseCommand):
    help = "Crea el equipo de un archivo privado y reparte el pool por conversación y estrato."

    def add_arguments(self, parser):
        parser.add_argument("--team", required=True, help="JSON privado con accounts y seed; consulta team.example.json.")
        parser.add_argument("--credentials", required=True, help="Archivo privado para las contraseñas iniciales (se crea, nunca se sobrescribe).")

    def handle(self, *args, **options):
        if not Conversation.objects.exists():
            raise CommandError("Ejecuta import_pool primero.")
        try:
            config = json.loads(Path(options["team"]).read_text())
            accounts, seed = config["accounts"], config["seed"]
            if not isinstance(accounts, list) or not accounts or type(seed) is not int:
                raise ValueError("Se requieren accounts (lista) y seed (entero).")
            usernames = []
            for account in accounts:
                if not isinstance(account, dict) or set(account) - {"username", "first_name", "last_name", "role"}:
                    raise ValueError("Cada cuenta admite solo username, first_name, last_name y role. No incluyas contraseñas.")
                username = account["username"]
                if not isinstance(username, str) or not username:
                    raise ValueError("Nombre de usuario vacío o inválido.")
                get_user_model()._meta.get_field("username").clean(username, None)
                if account["role"] not in ["control", "lead", "evaluator"]:
                    raise ValueError("Rol inválido: usa control, lead o evaluator.")
                for field in ["first_name", "last_name"]:
                    get_user_model()._meta.get_field(field).clean(account.get(field, ""), None)
                usernames.append(username)
            if len(set(u.casefold() for u in usernames)) != len(usernames):
                raise ValueError("Hay nombres de usuario duplicados.")
            if any(sum(a["role"] == role for a in accounts) != 1 for role in ["control", "lead"]):
                raise ValueError("Se requiere exactamente una cuenta control y una lead.")
            evaluator_names = [a["username"] for a in accounts if a["role"] == "evaluator"]
            lead_name = next(a["username"] for a in accounts if a["role"] == "lead")
            if not evaluator_names:
                raise ValueError("Se requiere al menos un evaluador.")
        except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
            raise CommandError(f"Configuración de equipo inválida: {exc}") from exc
        if get_user_model().objects.filter(username__in=usernames).exists():
            raise CommandError("El equipo ya existe; gestiona las cuentas en /admin/. No se cambió nada.")
        path = Path(options["credentials"]).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as exc:
            raise CommandError(f"No se puede crear el archivo privado: {exc}") from exc
        try:
            with os.fdopen(fd, "w") as out, transaction.atomic():
                people = {}
                for account in accounts:
                    username = account["username"]
                    admin = account["role"] == "control"
                    password = secrets.token_urlsafe(18)
                    user = get_user_model().objects.create_user(username=username, password=password,
                        first_name=account.get("first_name", ""), last_name=account.get("last_name", ""),
                        is_staff=admin, is_superuser=admin)
                    Profile.objects.create(user=user)
                    people[username] = user
                    out.write(f"{username}: {password}\n")
                groups = list(Conversation.objects.all())
                by_stratum = defaultdict(list)
                for case in groups:
                    by_stratum[(case.scenario, case.language)].append(case)
                assigned = {name: [] for name in evaluator_names}
                # Rotate continuously across strata, keeping conversations (and their turns) together.
                cycle = itertools.cycle(assigned)
                rng = random.Random(seed)
                for key in sorted(by_stratum):
                    cases = sorted(by_stratum[key], key=lambda g: g.id)
                    rng.shuffle(cases)
                    for case in cases:
                        assigned[next(cycle)].append(case)
                assigned[lead_name] = groups
                for name, cases in assigned.items():
                    random.Random("sycocode-phase1-"+name).shuffle(cases)
                    Assignment.objects.bulk_create([Assignment(user=people[name], conversation=case, position=i) for i, case in enumerate(cases)])
                out.flush()
                os.fsync(out.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        self.stdout.write(f"Equipo creado. Contraseñas iniciales solo en {path} (permisos 600). Cambio obligatorio al entrar.")
        for name in [lead_name, *evaluator_names]:
            p = progress(people[name])
            self.stdout.write(f"{name}: {p['groups']} conversaciones, {p['total']} respuestas")
