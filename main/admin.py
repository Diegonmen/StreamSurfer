from django.contrib import admin
from main.models import Genero, Stream, Pelicula, Serie

#registramos en el administrador de django los modelos 
admin.site.register(Genero)
admin.site.register(Stream)
admin.site.register(Pelicula)
admin.site.register(Serie)