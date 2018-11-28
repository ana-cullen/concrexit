# Generated by Django 2.1.3 on 2018-12-19 17:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('education', '0008_auto_20180516_1935'),
    ]

    operations = [
        migrations.AddField(
            model_name='exam',
            name='language',
            field=models.CharField(choices=[('en', 'English'), ('nl', 'Dutch')], max_length=2, null=True),
        ),
        migrations.AddField(
            model_name='summary',
            name='language',
            field=models.CharField(choices=[('en', 'English'), ('nl', 'Dutch')], default='en', max_length=2),
        ),
    ]
