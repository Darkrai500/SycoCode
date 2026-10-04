from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from annotations.models import Annotation, Profile, Unit


class Command(BaseCommand):
    help = "Concede o revoca adjudicación a una cuenta evaluadora sin elevarla a staff."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        action = parser.add_mutually_exclusive_group(required=True)
        action.add_argument("--enable", action="store_true")
        action.add_argument("--disable", action="store_true")

    def handle(self, *args, **options):
        username = options["username"]
        user = get_user_model().objects.filter(username=username, is_active=True).first()
        if user is None:
            raise CommandError("Cuenta activa no encontrada.")
        if options["enable"]:
            if user.is_staff or user.is_superuser:
                raise CommandError("El permiso se reserva para una cuenta evaluadora sin administración.")
            if Unit.objects.count() == 0 or Annotation.objects.filter(user=user).count() != Unit.objects.count():
                raise CommandError("La cuenta debe haber terminado las 320 unidades antes de ver votos ajenos.")
        with transaction.atomic():
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.can_adjudicate = options["enable"]
            profile.save(update_fields=["can_adjudicate"])
        self.stdout.write(f"{username}: can_adjudicate={profile.can_adjudicate}; is_staff={user.is_staff}; is_superuser={user.is_superuser}")
