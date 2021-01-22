from django.urls import path
from django.contrib import admin
from main import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.inicio),
    path('peliculas/', views.lista_peliculas),
    path('peliculas/<int:id_pelicula>',views.detalles_pelicula),
    path('series/', views.lista_series),
    path('series/<int:id_serie>',views.detalles_serie),
    path('popular_bd/', views.populateBD),
    path('actualizar_bd/', views.actualizarBD),
    path('popular_whoosh/', views.populateWhoosh),
    path('actualizar_whoosh/', views.actualizarWhoosh),
    path('busqueda_titulo/', views.buscarPorTitulo),
    path('busqueda_plataforma/', views.buscarPorPlataforma),
    path('busqueda_genero/', views.buscarPorGenero),
    path('busqueda_puntuacion/', views.buscarPorPuntuacion)
]
