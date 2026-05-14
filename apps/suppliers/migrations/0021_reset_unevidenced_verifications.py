# Resets Compliance Readiness sign-offs that predate the deforestation engine.
#
# Verification used to be a free checkbox, so a farm could be `is_eudr_verified`
# with no satellite evidence behind it. From now on a sign-off must rest on a
# clear, current, non-stale DeforestationCheck. This one-time pass un-verifies any
# farm whose evidence does not currently support the sign-off. Remediation path:
# run `manage.py run_deforestation_checks`, then a manager re-signs off the farm.

from django.db import migrations


def reset_unevidenced_verifications(apps, schema_editor):
    Farm = apps.get_model('suppliers', 'Farm')

    for farm in Farm.objects.filter(is_eudr_verified=True):
        latest = farm.deforestation_checks.order_by('-created_at').first()

        evidenced = (
            latest is not None
            and latest.risk_status == 'clear'
            and latest.geometry_hash_at_assessment == farm.geometry_hash
        )

        if farm.land_cleared_after_cutoff is True:
            disqualified = True
        elif farm.land_cleared_after_cutoff is False:
            disqualified = False
        else:
            disqualified = bool(latest and latest.risk_status == 'flagged')

        if not evidenced or disqualified:
            farm.is_eudr_verified = False
            farm.verified_by = None
            farm.verified_date = None
            farm.verification_expiry = None
            farm.save(update_fields=[
                'is_eudr_verified', 'verified_by',
                'verified_date', 'verification_expiry',
            ])


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0020_farm_land_cleared_after_cutoff_reason_and_more'),
    ]

    operations = [
        # Forward-only correctness pass — prior verification state cannot be restored.
        migrations.RunPython(
            reset_unevidenced_verifications,
            migrations.RunPython.noop,
        ),
    ]
