"""
Migration: expand Farmer model

- Replaces `name` with `first_name` + `last_name` (data migration splits on first space)
- Adds: gender, crops, consent_given, consent_date, bank_name, account_number
"""
from django.db import migrations, models


def split_name_forward(apps, schema_editor):
    Farmer = apps.get_model('suppliers', 'Farmer')
    for farmer in Farmer.objects.all():
        parts = (farmer.name or '').strip().split(' ', 1)
        farmer.first_name = parts[0]
        farmer.last_name = parts[1] if len(parts) > 1 else ''
        farmer.save(update_fields=['first_name', 'last_name'])


def split_name_reverse(apps, schema_editor):
    Farmer = apps.get_model('suppliers', 'Farmer')
    for farmer in Farmer.objects.all():
        farmer.name = f"{farmer.first_name} {farmer.last_name}".strip()
        farmer.save(update_fields=['name'])


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0007_farmer_farm_farmer'),
    ]

    operations = [
        # 1. Add first_name + last_name (blank during migration)
        migrations.AddField(
            model_name='farmer',
            name='first_name',
            field=models.CharField(default='', max_length=150),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='farmer',
            name='last_name',
            field=models.CharField(blank=True, max_length=150),
        ),

        # 2. Populate from existing name field
        migrations.RunPython(split_name_forward, split_name_reverse),

        # 3. Remove old name field
        migrations.RemoveField(
            model_name='farmer',
            name='name',
        ),

        # 4. New fields
        migrations.AddField(
            model_name='farmer',
            name='gender',
            field=models.CharField(
                blank=True, max_length=1,
                choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
            ),
        ),
        migrations.AddField(
            model_name='farmer',
            name='crops',
            field=models.CharField(
                blank=True, max_length=255,
                help_text='Comma-separated list of crops/livestock',
            ),
        ),
        migrations.AddField(
            model_name='farmer',
            name='consent_given',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='farmer',
            name='consent_date',
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='farmer',
            name='bank_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='farmer',
            name='account_number',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
