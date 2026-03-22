from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.companies.models import Company

User = get_user_model()

DEMO_USERS = [
    {'first_name': 'Amina',       'last_name': 'Yusuf',    'role': 'manager', 'title': 'Operations Manager'},
    {'first_name': 'Chukwuemeka', 'last_name': 'Obi',      'role': 'manager', 'title': 'Procurement Manager'},
    {'first_name': 'Fatima',      'last_name': 'Al-Hassan', 'role': 'staff',   'title': 'Compliance Officer'},
    {'first_name': 'Biodun',      'last_name': 'Adeleke',  'role': 'staff',   'title': 'Inventory Officer'},
    {'first_name': 'Ngozi',       'last_name': 'Eze',      'role': 'staff',   'title': 'Sales Coordinator'},
    {'first_name': 'Musa',        'last_name': 'Garba',    'role': 'staff',   'title': 'Field Officer'},
    {'first_name': 'Aisha',       'last_name': 'Bello',    'role': 'staff',   'title': 'Logistics Officer'},
    {'first_name': 'Tunde',       'last_name': 'Fashola',  'role': 'staff',   'title': 'Finance Officer'},
    {'first_name': 'Halima',      'last_name': 'Sule',     'role': 'viewer',  'title': 'Audit & Compliance'},
    {'first_name': 'Emeka',       'last_name': 'Nwosu',    'role': 'viewer',  'title': 'Board Observer'},
    {'first_name': 'Zainab',      'last_name': 'Kwara',    'role': 'viewer',  'title': 'NGO Liaison'},
]

class Command(BaseCommand):
    help = 'Seed demo users for Savanna Agro Trading Ltd'

    def handle(self, *args, **options):
        try:
            company = Company.objects.get(name='Savanna Agro Trading Ltd')
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR('Savanna Agro Trading Ltd not found. Create the company first via request access flow.'))
            return

        created = 0
        skipped = 0

        for u in DEMO_USERS:
            username_base = f"{u['first_name'].lower()}_{u['last_name'].lower().replace('-', '_')}"
            username = username_base
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1

            email = f"{username}@savanna-demo.internal"

            if User.objects.filter(email=email).exists():
                self.stdout.write(f"  Skipped: {u['first_name']} {u['last_name']} (already exists)")
                skipped += 1
                continue

            user = User.objects.create_user(
                username=username,
                email=email,
                password='SavannaDemo2026!',
                first_name=u['first_name'],
                last_name=u['last_name'],
                company=company,
                system_role=u['role'],
                job_title=u['title'],
            )
            self.stdout.write(self.style.SUCCESS(f"  Created: {user.get_full_name()} ({u['role']}) — {username} / SavannaDemo2026!"))
            created += 1

        self.stdout.write(self.style.SUCCESS(f'\nDone. {created} users created, {skipped} skipped.'))
