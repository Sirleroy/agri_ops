import secrets
import string
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create the AgriOps ops dashboard user'

    def handle(self, *args, **options):
        suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        username = f'ops_agriops_{suffix}'

        if User.objects.filter(is_staff=True, username__startswith='ops_agriops_').exists():
            self.stdout.write(self.style.WARNING('Ops user already exists. Aborting.'))
            return

        password = secrets.token_urlsafe(24)
        User.objects.create_user(
            username=username,
            password=password,
            is_staff=True,
            is_superuser=False,
            system_role='staff',
        )

        self.stdout.write(self.style.SUCCESS('\nOps user created:'))
        self.stdout.write(f'  Username: {username}')
        self.stdout.write(f'  Password: {password}')
        self.stdout.write(self.style.WARNING('\nSave these credentials to your password manager NOW. They will not be shown again.'))
