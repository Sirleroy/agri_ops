from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0011_add_fvf_fields_to_farm'),
    ]

    operations = [
        migrations.AddField(
            model_name='farmimportlog',
            name='auto_corrected',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
