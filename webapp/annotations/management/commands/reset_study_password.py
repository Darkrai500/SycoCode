import getpass
import os
import secrets
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from annotations.models import Profile, StudyEvent


class Command(BaseCommand):
    help = ("Restablece una contraseña dejando registro con cuenta, operador del sistema y fecha. "
            "El registro forma parte de la exportación de auditoría.")

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--credentials", required=True, help="Archivo privado nuevo para la contraseña temporal (permisos 600).")

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"]).first()
        if user is None:
            raise CommandError("Cuenta no encontrada.")
        path = Path(options["credentials"]).resolve()
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as exc:
            raise CommandError(f"No se puede crear el archivo privado: {exc}") from exc
        password = secrets.token_urlsafe(18)
        with os.fdopen(fd, "w") as out, transaction.atomic():
            user.set_password(password)
            user.save(update_fields=["password"])
            Profile.objects.update_or_create(user=user, defaults={"must_change_password": True})
            # The runbook's wrapper runs this as the service user through sudo: record the operator, not that user.
            operator = os.environ.get("SUDO_USER") or getpass.getuser()
            StudyEvent.objects.create(kind="password_reset", actor=operator, detail={"account": user.username})
            out.write(f"{user.username}: {password}\n")
        self.stdout.write(f"Contraseña temporal solo en {path}. Cambio obligatorio al entrar. Queda registrado.")
