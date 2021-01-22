from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

class Genero(models.Model):
    nombre = models.CharField(max_length=30, verbose_name='Género')

    def __str__(self):
        return self.nombre

class Stream(models.Model):
    plataforma = models.CharField(max_length=30, verbose_name='Plataforma')
    link = models.TextField(verbose_name='Enlace')

    def __str__(self):
        return self.plataforma, self.link

class Pelicula(models.Model):
    titulo = models.TextField(verbose_name='Título')
    tituloOriginal = models.TextField(verbose_name='Título Original')
    fechaEstreno = models.IntegerField(validators=[MaxValueValidator(2021), MinValueValidator(1900)])
    imdb = models.CharField(max_length=3,verbose_name='IMDB')
    poster = models.TextField(verbose_name='Póster')
    duracion = models.CharField(max_length=8,verbose_name='Duracion')
    director = models.CharField(max_length=30,verbose_name='Director')
    sinopsis = models.TextField(verbose_name='Sinopsis')
    generos = models.ManyToManyField(Genero)
    streams = models.ManyToManyField(Stream)

    def __str__(self):
        return self.titulo

class Serie(models.Model):
    titulo = models.TextField(verbose_name='Título')
    tituloOriginal = models.TextField(verbose_name='Título Original')
    fechaEstreno = models.IntegerField(validators=[MaxValueValidator(2021), MinValueValidator(1900)])
    imdb = models.CharField(max_length=3,verbose_name='IMDB')
    poster = models.TextField(verbose_name='Póster')
    temporadas = models.IntegerField(validators=[MinValueValidator(1)])
    sinopsis = models.TextField(verbose_name='Sinopsis')
    generos = models.ManyToManyField(Genero)
    streams = models.ManyToManyField(Stream)

    def __str__(self):
        return self.titulo