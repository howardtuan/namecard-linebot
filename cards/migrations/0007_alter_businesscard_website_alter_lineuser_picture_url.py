from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cards", "0006_alter_businesscard_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="businesscard",
            name="website",
            field=models.URLField(blank=True, max_length=1000),
        ),
        migrations.AlterField(
            model_name="lineuser",
            name="picture_url",
            field=models.URLField(blank=True, max_length=1000),
        ),
    ]
