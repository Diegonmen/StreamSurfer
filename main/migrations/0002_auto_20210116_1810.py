# Generated by Django 3.1.5 on 2021-01-16 17:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='pelicula',
            name='sinopsis',
            field=models.TextField(default='No hay ninguna sinopsis disponible', verbose_name='Sinopsis'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='serie',
            name='sinopsis',
            field=models.TextField(default='No hay ninguna sinopsis disponible', verbose_name='Sinopsis'),
            preserve_default=False,
        ),
    ]
