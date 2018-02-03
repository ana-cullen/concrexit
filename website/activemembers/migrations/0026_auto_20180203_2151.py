# Generated by Django 2.0.2 on 2018-02-03 20:51

from django.db import migrations
import tinymce.models


class Migration(migrations.Migration):

    dependencies = [
        ('activemembers', '0025_auto_20180108_1253'),
    ]

    operations = [
        migrations.AlterField(
            model_name='committee',
            name='description_en',
            field=tinymce.models.HTMLField(verbose_name='Description (EN)'),
        ),
        migrations.AlterField(
            model_name='committee',
            name='description_nl',
            field=tinymce.models.HTMLField(verbose_name='Description (NL)'),
        ),
    ]
