from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cards", "0005_alter_cardtag_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="businesscard",
            name="image",
            field=models.ImageField(blank=True, upload_to="business_cards/%Y/%m/%d/"),
        ),
    ]
