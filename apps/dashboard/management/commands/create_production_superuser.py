"""
One-time management command to create the production superuser and company.
Run once after first deployment, then delete this file.

Usage:
    python manage.py create_production_superuser
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Create production superuser and initial company'

    def handle(self, *args, **options):
        from apps.users.models import CustomUser
        from apps.companies.models import Company

        with transaction.atomic():
            # Create company
            company, created = Company.objects.get_or_create(
                name='Ake Collective',
                defaults={
                    'country': 'Nigeria',
                    'city': 'Kano',
                    'plan_tier': 'pro',
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'  Company created: {company}')
            else:
                self.stdout.write(f'  Company already exists: {company}')

            # Create superuser
            if CustomUser.objects.filter(username='ezinna').exists():
                self.stdout.write('  Superuser already exists — skipping.')
                return

            user = CustomUser.objects.create_superuser(
                username='ezinna',
                email='ohahezinna@gmail.com',
                password='AgriOps2026!Secure',
                system_role='org_admin',
                company=company,
            )
            self.stdout.write(self.style.SUCCESS(
                f'  Superuser created: {user.username} / AgriOps2026!Secure'
            ))
            self.stdout.write(self.style.WARNING(
                '  IMPORTANT: Change this password immediately after first login!'
            ))
