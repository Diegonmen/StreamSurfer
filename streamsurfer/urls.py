from django.urls import path
from django.contrib import admin
from main import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.inicio),
    path('peliculas/', views.lista_peliculas),
    path('series/', views.lista_series),
    path('popular_bd/', views.populateBD),
    path('actualizar_bd/', views.actualizarBD)
]
