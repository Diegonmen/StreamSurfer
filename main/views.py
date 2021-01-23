from main.models import Genero, Stream, Pelicula, Serie
from main.forms import TituloBusquedaForm, PlataformaBusquedaForm, GeneroBusquedaForm, PuntuacionBusquedaForm
from bs4 import BeautifulSoup
import urllib.request
import lxml
import time
import os
import types
import shutil
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer
from rake_nltk import Metric, Rake
from datetime import datetime
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Avg, Count
from django.conf import settings
from whoosh.index import create_in, open_dir
from whoosh.fields import ID, Schema, TEXT, NUMERIC, KEYWORD
from whoosh.qparser import QueryParser, MultifieldParser, OrGroup

#Extrae los datos de la web justwatch.com
def getDatos():
    #Variables para contar el número de registros que vamos a almacenar
    num_peliculas = 0
    num_series = 0
    num_generos = 0
    num_streams = 0

    #Borramos todas las tablas de la BD
    Stream.objects.all().delete()
    Genero.objects.all().delete()
    Pelicula.objects.all().delete()
    Serie.objects.all().delete()

    #Definimos las propiedades del WebDriver (Es necesario modificar la ruta del ejecutable de chromedriver en cada entorno de ejecución)
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    options.add_argument('--headless')
    options.add_argument('log-level=2')
    driver = webdriver.Chrome(executable_path='C:/Users/soulb/Downloads/chromedriver.exe', options=options)
    scroll_pause_time = 2 #Tiempo de espera tras simular el scrolleado

    lista_enlaces_peliculas = []
    lista_enlaces_series = []

    driver.get("https://www.justwatch.com/es/peliculas")
    time.sleep(3)  #Esperamos 3 segundos para que cargue correctamente la página
    scrollable = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]/div/div/div[2]/div[2]')
    while True:
        #Recuperamos el HTML DOM a partir del driver para que sea cargado correctamente mediante Javascript
        page = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]')
        html = driver.execute_script("return arguments[0].innerHTML;", page) 
        s = BeautifulSoup(html, "lxml")
        peliculas = s.find("div", class_="vue-recycle-scroller").find_all("div", class_="title-list-grid__item")
        #Se almacenan las 250 primeras películas, evitando que se repitan
        if (("https://www.justwatch.com" + peliculas[-1].a['href'] in lista_enlaces_peliculas) or (len(lista_enlaces_peliculas) >= 250)):
            break
        for pelicula in peliculas:
            if (len(lista_enlaces_peliculas) >= 250):
                break
            enlace = "https://www.justwatch.com" + pelicula.a['href']
            if (enlace not in lista_enlaces_peliculas):
                #Abrimos un segundo WebDriver auxiliar para la ficha de la película en cuestión
                auxDriver = webdriver.Chrome(executable_path='C:/Users/soulb/Downloads/chromedriver.exe', options=options)
                auxDriver.get(enlace)
                time.sleep(2)
                s = BeautifulSoup(auxDriver.page_source, "lxml")
                #Tras extraer el HTML con BeautifulSoup, procedemos a extraer los datos
                datos = s.find("div", id="base").find("div",class_="jw-container").find("div", class_="jw-info-box")
                tituloyfecha = datos.find("div", class_="title-block").h1.text.strip()  
                titulo = tituloyfecha[:-6].strip()
                fecha = int(tituloyfecha[-6:].replace("(", "").replace(")", ""))
                if (datos.find("div", class_="title-block").h3):
                    titulo_original = datos.find("div", class_="title-block").h3.string.replace("Título original: ", "").strip()
                else:
                    titulo_original = titulo 
                sinopsis = "No hay ninguna sinopsis disponible"
                datos_sinopsis = datos.find("div", class_="col-sm-push-4").find_all("div", class_=None, recursive=False)
                if (len(datos_sinopsis) == 4):
                    sinopsis = datos_sinopsis[3].find("p", class_="text-wrap-pre-line").span.text.strip()
                if (len(datos_sinopsis) == 5):
                    sinopsis = datos_sinopsis[4].find("p", class_="text-wrap-pre-line").span.text.strip()
                poster = datos.find("div", class_="title-poster--no-radius-bottom").find("picture", class_="title-poster__image").find_all("source")[0]['srcset'].split(",")[0].strip()
                ficha = datos.find("div",class_="detail-infos").find_all("div", class_="clearfix")
                if (len(ficha[0].find_all("div", class_="jw-scoring-listing__rating")) > 1):
                    imdb = ficha[0].find_all("div", class_="jw-scoring-listing__rating")[1].a.text.strip()
                else:
                    imdb = "-"
                generos = []
                lista_generos_aux = ficha[1].find("div", class_="detail-infos__detail--values").find_all("span", recursive=False)
                for genero in lista_generos_aux:
                    generos.append(genero.text.strip().replace(", ", ""))
                duracion = ficha[2].find("div", class_="detail-infos__detail--values").string.strip()
                if (len(ficha) == 5):
                    if (ficha[4].find("div", class_="detail-infos__detail--values").span):
                        director = ficha[4].find("div", class_="detail-infos__detail--values").span.a.string.strip()
                    else:
                        director = "-"
                else:
                    if (ficha[3].find("div", class_="detail-infos__detail--values").span):
                        director = ficha[3].find("div", class_="detail-infos__detail--values").span.a.string.strip()
                    else:
                        director = "-"
                streams = []
                #Almacenamos las opciones de streaming en caso de existir
                if (datos.find_all("div", class_="price-comparison__grid__row price-comparison__grid__row--stream")):
                    servicios = datos.find_all(lambda tag: tag.name == 'div' and tag.get('class') == ['monetizations'])[0].find("div", class_="price-comparison__grid__row price-comparison__grid__row--stream").find_all("div", class_="price-comparison__grid__row__element")
                    for servicio in servicios:
                        plataforma = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a.img['title']
                        link = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a['href']
                        streams.append((plataforma, link))
                lista_enlaces_peliculas.append(enlace)
                auxDriver.close()

                #Almacenamos en la BD
                lista_generos_obj = []
                for genero in generos:
                    genero_obj, creado = Genero.objects.get_or_create(nombre=genero)
                    lista_generos_obj.append(genero_obj)
                    if creado:
                        num_generos = num_generos + 1
                lista_streams_obj = []
                for stream in streams:
                    stream_obj, creado = Stream.objects.get_or_create(plataforma=stream[0], link=stream[1])
                    lista_streams_obj.append(stream_obj)
                    if creado:
                        num_streams = num_streams + 1
                p = Pelicula.objects.create(titulo=titulo, tituloOriginal=titulo_original, fechaEstreno=fecha, imdb=imdb, poster=poster, director=director, duracion=duracion, sinopsis=sinopsis)
                #Añadimos la lista de géneros y streams
                for g in lista_generos_obj:
                    p.generos.add(g)
                for st in lista_streams_obj:
                    p.streams.add(st)
                num_peliculas = num_peliculas + 1

        #Tras extraer todas las películas visibles, se simula un scrolleado para que se carguen las siguientes
        driver.execute_script("arguments[0].scrollIntoView();", scrollable)
        time.sleep(scroll_pause_time)

    driver.get("https://www.justwatch.com/es/series")
    time.sleep(3)  #Esperamos 3 segundos para que cargue correctamente la página
    scrollable = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]/div/div/div[2]/div[2]')
    while True:  
        #Recuperamos el HTML DOM a partir del driver para que sea cargado correctamente mediante Javascript
        page = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]')
        html = driver.execute_script("return arguments[0].innerHTML;", page) 
        s = BeautifulSoup(html, "lxml")
        series = s.find("div", class_="vue-recycle-scroller").find_all("div", class_="title-list-grid__item")
        #Se almacenan las 250 primeras series, evitando que se repitan
        if (("https://www.justwatch.com" + series[-1].a['href'] in lista_enlaces_series) or (len(lista_enlaces_series) >= 250)):
            break
        for serie in series:
            if (len(lista_enlaces_series) >= 250):
                break
            enlace = "https://www.justwatch.com" + serie.a['href']
            if (enlace not in lista_enlaces_series):
                #Abrimos un segundo WebDriver auxiliar para la ficha de la serie en cuestión
                auxDriver = webdriver.Chrome(executable_path='C:/Users/soulb/Downloads/chromedriver.exe', options=options)
                auxDriver.get(enlace)
                time.sleep(2)
                s = BeautifulSoup(auxDriver.page_source, "lxml")
                #Tras extraer el HTML con BeautifulSoup, procedemos a extraer los datos
                datos = s.find("div", id="base").find("div",class_="jw-container").find("div", class_="jw-info-box")
                tituloyfecha = datos.find("div", class_="title-block").h1.text.strip()
                titulo = tituloyfecha[:-6].strip()
                fecha = int(tituloyfecha[-6:].replace("(", "").replace(")", ""))
                if (datos.find("div", class_="title-block").h3):
                    titulo_original = datos.find("div", class_="title-block").h3.string.replace("Título original: ", "").strip()
                else:
                    titulo_original = titulo 
                sinopsis = "No hay ninguna sinopsis disponible"
                datos_sinopsis = datos.find("div", class_="col-sm-push-4").find_all("div", class_=None, recursive=False)
                if (len(datos_sinopsis) == 5):
                    sinopsis = datos_sinopsis[4].find("p", class_="text-wrap-pre-line").span.text.strip()
                if (len(datos_sinopsis) == 6):
                    sinopsis = datos_sinopsis[5].find("p", class_="text-wrap-pre-line").span.text.strip()
                poster = datos.find("div", class_="title-poster--no-radius-bottom").find("picture", class_="title-poster__image").find_all("source")[0]['srcset'].split(",")[0].strip()
                ficha = datos.find("div",class_="detail-infos").find_all("div", class_="clearfix")
                if (len(ficha[0].find_all("div", class_="jw-scoring-listing__rating")) > 1):
                    imdb = ficha[0].find_all("div", class_="jw-scoring-listing__rating")[1].a.text.strip()
                else:
                    imdb = "-"
                temporadas = int(datos.find("p", class_="detail-infos__subheading").text.strip().split(" ")[0])
                generos = []
                lista_generos_aux = ficha[1].find("div", class_="detail-infos__detail--values").find_all("span", recursive=False)
                for genero in lista_generos_aux:
                    generos.append(genero.text.strip().replace(", ", ""))
                streams = []
                #Almacenamos las opciones de streaming en caso de existir
                if (datos.find_all("div", class_="price-comparison__grid__row price-comparison__grid__row--stream")):
                    servicios = datos.find_all(lambda tag: tag.name == 'div' and tag.get('class') == ['monetizations'])[0].find("div", class_="price-comparison__grid__row price-comparison__grid__row--stream").find_all("div", class_="price-comparison__grid__row__element")
                    for servicio in servicios:
                        plataforma = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a.img['title']
                        link = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a['href']
                        streams.append((plataforma, link))
                lista_enlaces_series.append(enlace)
                auxDriver.close()

                #Almacenamos en la BD
                lista_generos_obj = []
                for genero in generos:
                    genero_obj, creado = Genero.objects.get_or_create(nombre=genero)
                    lista_generos_obj.append(genero_obj)
                    if creado:
                        num_generos = num_generos + 1
                lista_streams_obj = []
                for stream in streams:
                    stream_obj, creado = Stream.objects.get_or_create(plataforma=stream[0], link=stream[1])
                    lista_streams_obj.append(stream_obj)
                    if creado:
                        num_streams = num_streams + 1
                show = Serie.objects.create(titulo=titulo, tituloOriginal=titulo_original, fechaEstreno=fecha, imdb=imdb, poster=poster, temporadas=temporadas, sinopsis=sinopsis)
                #Añadimos la lista de géneros y streams
                for g in lista_generos_obj:
                    show.generos.add(g)
                for st in lista_streams_obj:
                    show.streams.add(st)
                num_series = num_series + 1

        #Tras extraer todas las películas visibles, se simula un scrolleado para que se carguen las siguientes
        driver.execute_script("arguments[0].scrollIntoView();", scrollable)
        time.sleep(scroll_pause_time)

    return ((num_peliculas, num_series, num_generos, num_streams))

#Carga los datos desde la web en la BD
@login_required(login_url='/actualizar_bd')
def populateBD(request):
    if request.method=='POST':
        if 'Aceptar' in request.POST:      
            num_peliculas, num_series, num_generos, num_streams = getDatos()
            logout(request)
            mensaje="Se han almacenado: " + str(num_peliculas) +" peliculas, " + str(num_series) +" series, " + str(num_generos) +" generos, y " + str(num_streams) +" opciones de streaming."
            return render(request, 'carga_bd.html', {'mensaje':mensaje})
        else:
            return redirect("/")
           
    return render(request, 'confirmacion.html')

#Popula la base de datos siempre que realice la acción un administrador logueado
def actualizarBD(request):
    if request.user.is_authenticated:
        print('Authenticated')
        return(HttpResponseRedirect('/popular_bd'))
    formulario = AuthenticationForm()
    if request.method == 'POST':
        formulario = AuthenticationForm(request.POST)
        usuario = request.POST['username']
        clave = request.POST['password']
        acceso = authenticate(username=usuario, password=clave)
        if acceso is not None:
            if acceso.is_active:
                login(request, acceso)
                return (HttpResponseRedirect('/popular_bd'))
            else:
                return (HttpResponse('<html><body>Error: usuario no activo </body></html>'))
        else:
            return (HttpResponse('<html><body><b>Error: usuario o contrase&ntilde;a incorrectos</b><br><a href=/>Volver a la página principal</a></body></html>'))

    return render(request, 'actualizar_bd.html', {'formulario': formulario})

#Muestra el número de películas y series que hay en la BD
def inicio(request):
    num_peliculas=Pelicula.objects.all().count()
    num_series=Serie.objects.all().count()
    return render(request,'index.html', {'num_peliculas':num_peliculas, 'num_series':num_series})

#Muestra un listado con los datos de las películas (título, título original, director, duracion, géneros, fecha de estreno y opciones de streaming)
def lista_peliculas(request):
    peliculas=Pelicula.objects.all()
    return render(request,'lista_peliculas.html', {'peliculas':peliculas})

#Muestra detalles de una pelicula
def detalles_pelicula(request, id_pelicula):
    pelicula = get_object_or_404(Pelicula, pk=id_pelicula)
    peliculas_rc = recomendarPeliculas(id_pelicula)
    peliculas_recomendadas = []
    for p in peliculas_rc:
        pelicula_aux = Pelicula.objects.get(titulo = p)
        peliculas_recomendadas.append(pelicula_aux)
    return render(request,'detalles_pelicula.html',{'pelicula':pelicula, 'peliculas_recomendadas': peliculas_recomendadas})

#Muestra un listado con los datos de las series (título, título original, temporadas, géneros, fecha de estreno y opciones de streaming)
def lista_series(request):
    series=Serie.objects.all()
    return render(request,'lista_series.html', {'series':series})

#Muestra detalles de una serie
def detalles_serie(request, id_serie):
    serie = get_object_or_404(Serie, pk=id_serie)
    series_rc = recomendarSeries(id_serie)
    series_recomendadas = []
    for s in series_rc:
        serie_aux = Serie.objects.get(titulo = s)
        series_recomendadas.append(serie_aux)
    return render(request,'detalles_serie.html',{'serie':serie, 'series_recomendadas': series_recomendadas})

#Definición del Schema de Whoosh para películas
def schemaPelicula():
    schem = Schema(idPelicula=ID(stored=True, unique=True), titulo=TEXT(
        stored=True), tituloOriginal=TEXT(stored=True), imdb=TEXT(stored=True),
        fechaEstreno=TEXT(stored=True), poster=TEXT(stored=True), duracion=TEXT(stored=True),
        director=TEXT(stored=True), generos=KEYWORD(stored=True,commas=True),
        plataformas=KEYWORD(stored=True,commas=True), links=KEYWORD(stored=True,commas=True))
    return schem

#Definición del Schema de Whoosh para series
def schemaSerie():
    schem = Schema(idSerie=ID(stored=True, unique=True), titulo=TEXT(
        stored=True), tituloOriginal=TEXT(stored=True), imdb=TEXT(stored=True),
        fechaEstreno=TEXT(stored=True), poster=TEXT(stored=True), temporadas=TEXT(stored=True),
        generos=KEYWORD(stored=True,commas=True), plataformas=KEYWORD(stored=True,commas=True),
        links=KEYWORD(stored=True,commas=True))
    return schem

#Carga la base de datos de Whoosh extrayendo los datos de la web justwatch.com
def getWhooshInfo():
    pelicula_directory = './' + 'Pelicula'
    serie_directory = './' + 'Serie'

    #Eliminamos el directorio del índice, si existe
    if os.path.exists(pelicula_directory):
        shutil.rmtree(pelicula_directory)
    os.mkdir(pelicula_directory)
    if os.path.exists(serie_directory):
        shutil.rmtree(serie_directory)
    os.mkdir(serie_directory)

    ix1 = create_in(pelicula_directory, schema=schemaPelicula())
    ix2 = create_in(serie_directory, schema=schemaSerie())

    writer1 = ix1.writer()
    writer2 = ix2.writer()

    count_peliculas = 0
    count_series = 0
    lista_enlaces_peliculas = []
    lista_enlaces_series = []

    #Definimos las propiedades del WebDriver (Es necesario modificar la ruta del ejecutable de chromedriver en cada entorno de ejecución)
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    options.add_argument('--headless')
    options.add_argument('log-level=2')
    driver = webdriver.Chrome(executable_path='C:/Users/soulb/Downloads/chromedriver.exe', options=options)
    scroll_pause_time = 2 #Tiempo de espera tras simular el scrolleado

    driver.get("https://www.justwatch.com/es/peliculas")
    time.sleep(3)  #Esperamos 3 segundos para que cargue correctamente la página
    scrollable = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]/div/div/div[2]/div[2]')
    while True:
        #Recuperamos el HTML DOM a partir del driver para que sea cargado correctamente mediante Javascript
        page = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]')
        html = driver.execute_script("return arguments[0].innerHTML;", page) 
        s = BeautifulSoup(html, "lxml")
        peliculas = s.find("div", class_="vue-recycle-scroller").find_all("div", class_="title-list-grid__item")
        #Se almacenan las 250 primeras películas, evitando que se repitan
        if (("https://www.justwatch.com" + peliculas[-1].a['href'] in lista_enlaces_peliculas) or (len(lista_enlaces_peliculas) >= 250)):
            break
        for pelicula in peliculas:
            if (len(lista_enlaces_peliculas) >= 250):
                break
            enlace = "https://www.justwatch.com" + pelicula.a['href']
            if (enlace not in lista_enlaces_peliculas):
                #Abrimos un segundo WebDriver auxiliar para la ficha de la película en cuestión
                auxDriver = webdriver.Chrome(executable_path='C:/Users/soulb/Downloads/chromedriver.exe', options=options)
                auxDriver.get(enlace)
                time.sleep(2)
                s = BeautifulSoup(auxDriver.page_source, "lxml")
                #Tras extraer el HTML con BeautifulSoup, procedemos a extraer los datos
                datos = s.find("div", id="base").find("div",class_="jw-container").find("div", class_="jw-info-box")
                tituloyfecha = datos.find("div", class_="title-block").h1.text.strip()  
                titulo = tituloyfecha[:-6].strip()
                fecha = int(tituloyfecha[-6:].replace("(", "").replace(")", ""))
                if (datos.find("div", class_="title-block").h3):
                    titulo_original = datos.find("div", class_="title-block").h3.string.replace("Título original: ", "").strip()
                else:
                    titulo_original = titulo 
                poster = datos.find("div", class_="title-poster--no-radius-bottom").find("picture", class_="title-poster__image").find_all("source")[0]['srcset'].split(",")[0].strip()
                ficha = datos.find("div",class_="detail-infos").find_all("div", class_="clearfix")
                if (len(ficha[0].find_all("div", class_="jw-scoring-listing__rating")) > 1):
                    imdb = ficha[0].find_all("div", class_="jw-scoring-listing__rating")[1].a.text.strip()
                else:
                    imdb = "-"
                generos = ""
                lista_generos_aux = ficha[1].find("div", class_="detail-infos__detail--values").find_all("span", recursive=False)
                for genero in lista_generos_aux:
                    generos += genero.text.strip()
                duracion = ficha[2].find("div", class_="detail-infos__detail--values").string.strip()
                if (len(ficha) == 5):
                    if (ficha[4].find("div", class_="detail-infos__detail--values").span):
                        director = ficha[4].find("div", class_="detail-infos__detail--values").span.a.string.strip()
                    else:
                        director = "-"
                else:
                    if (ficha[3].find("div", class_="detail-infos__detail--values").span):
                        director = ficha[3].find("div", class_="detail-infos__detail--values").span.a.string.strip()
                    else:
                        director = "-"
                plataformas = ""
                links = ""
                #Almacenamos las opciones de streaming en caso de existir
                if (datos.find_all("div", class_="price-comparison__grid__row price-comparison__grid__row--stream")):
                    servicios = datos.find_all(lambda tag: tag.name == 'div' and tag.get('class') == ['monetizations'])[0].find("div", class_="price-comparison__grid__row price-comparison__grid__row--stream").find_all("div", class_="price-comparison__grid__row__element")
                    for servicio in servicios:
                        plataforma = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a.img['title']
                        link = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a['href']
                        plataformas += plataforma + ", "
                        links += link + ", "
                if(len(plataformas) > 0):
                    plataformas = plataformas[:-2].strip()
                    links = links[:-2].strip()

                lista_enlaces_peliculas.append(enlace)
                auxDriver.close()

                #Guardamos en base de datos una nueva instancia del Schema
                writer1.add_document(idPelicula=str(count_peliculas), titulo=str(titulo), tituloOriginal=str(titulo_original), imdb=str(imdb), fechaEstreno=str(fecha),
                    poster=str(poster), duracion=str(duracion), director=str(director), generos=str(generos), plataformas=str(plataformas), links=str(links))
                count_peliculas += 1

        #Tras extraer todas las películas visibles, se simula un scrolleado para que se carguen las siguientes
        driver.execute_script("arguments[0].scrollIntoView();", scrollable)
        time.sleep(scroll_pause_time)

    driver.get("https://www.justwatch.com/es/series")
    time.sleep(3)  # Allow 2 seconds for the web page to open
    scrollable = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]/div/div/div[2]/div[2]')
    while True:  
        #Recuperamos el HTML DOM a partir del driver para que sea cargado correctamente mediante Javascript
        page = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]')
        html = driver.execute_script("return arguments[0].innerHTML;", page) 
        s = BeautifulSoup(html, "lxml")
        series = s.find("div", class_="vue-recycle-scroller").find_all("div", class_="title-list-grid__item")
        #Se almacenan las 250 primeras series, evitando que se repitan
        if (("https://www.justwatch.com" + series[-1].a['href'] in lista_enlaces_series) or (len(lista_enlaces_series) >= 250)):
            break
        for serie in series:
            if (len(lista_enlaces_series) >= 250):
                break
            enlace = "https://www.justwatch.com" + serie.a['href']
            if (enlace not in lista_enlaces_series):
                #Abrimos un segundo WebDriver auxiliar para la ficha de la serie en cuestión
                auxDriver = webdriver.Chrome(executable_path='C:/Users/soulb/Downloads/chromedriver.exe', options=options)
                auxDriver.get(enlace)
                time.sleep(2)
                s = BeautifulSoup(auxDriver.page_source, "lxml")
                #Tras extraer el HTML con BeautifulSoup, procedemos a extraer los datos
                datos = s.find("div", id="base").find("div",class_="jw-container").find("div", class_="jw-info-box")
                tituloyfecha = datos.find("div", class_="title-block").h1.text.strip()
                titulo = tituloyfecha[:-6].strip()
                fecha = int(tituloyfecha[-6:].replace("(", "").replace(")", ""))
                if (datos.find("div", class_="title-block").h3):
                    titulo_original = datos.find("div", class_="title-block").h3.string.replace("Título original: ", "").strip()
                else:
                    titulo_original = titulo 
                poster = datos.find("div", class_="title-poster--no-radius-bottom").find("picture", class_="title-poster__image").find_all("source")[0]['srcset'].split(",")[0].strip()
                ficha = datos.find("div",class_="detail-infos").find_all("div", class_="clearfix")
                if (len(ficha[0].find_all("div", class_="jw-scoring-listing__rating")) > 1):
                    imdb = ficha[0].find_all("div", class_="jw-scoring-listing__rating")[1].a.text.strip()
                else:
                    imdb = "-"
                temporadas = int(datos.find("p", class_="detail-infos__subheading").text.strip().split(" ")[0])
                generos = ""
                lista_generos_aux = ficha[1].find("div", class_="detail-infos__detail--values").find_all("span", recursive=False)
                for genero in lista_generos_aux:
                    generos += genero.text.strip()
                plataformas = ""
                links = ""
                #Almacenamos las opciones de streaming en caso de existir
                if (datos.find_all("div", class_="price-comparison__grid__row price-comparison__grid__row--stream")):
                    servicios = datos.find_all(lambda tag: tag.name == 'div' and tag.get('class') == ['monetizations'])[0].find("div", class_="price-comparison__grid__row price-comparison__grid__row--stream").find_all("div", class_="price-comparison__grid__row__element")
                    for servicio in servicios:
                        plataforma = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a.img['title']
                        link = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a['href']
                        plataformas += plataforma + ", "
                        links += link + ", "
                if(len(plataformas) > 0):
                    plataformas = plataformas[:-2].strip()
                    links = links[:-2].strip()

                lista_enlaces_series.append(enlace)
                auxDriver.close()

                #Guardamos en base de datos una nueva instancia del Schema
                writer2.add_document(idSerie=str(count_peliculas), titulo=str(titulo), tituloOriginal=str(titulo_original), imdb=str(imdb), fechaEstreno=str(fecha),
                    poster=str(poster), temporadas=str(temporadas), generos=str(generos), plataformas=str(plataformas), links=str(links))
                count_series += 1

        #Tras extraer todas las películas visibles, se simula un scrolleado para que se carguen las siguientes
        driver.execute_script("arguments[0].scrollIntoView();", scrollable)
        time.sleep(scroll_pause_time)

    writer1.commit()
    writer2.commit()

#Carga los datos desde la web en Whoosh
@login_required(login_url='/actualizar_whoosh')
def populateWhoosh(request):
    if request.method=='POST':
        if 'Aceptar' in request.POST:
            getWhooshInfo()      
            logout(request)
            return render(request, 'carga_whoosh.html')
        else:
            return redirect("/")
           
    return render(request, 'confirmacion.html')

#Popula la base de datos de Whoosh siempre que realice la acción un administrador logueado
def actualizarWhoosh(request):
    if request.user.is_authenticated:
        print('Authenticated')
        return(HttpResponseRedirect('/popular_whoosh'))
    formulario = AuthenticationForm()
    if request.method == 'POST':
        formulario = AuthenticationForm(request.POST)
        usuario = request.POST['username']
        clave = request.POST['password']
        acceso = authenticate(username=usuario, password=clave)
        if acceso is not None:
            if acceso.is_active:
                login(request, acceso)
                return (HttpResponseRedirect('/popular_whoosh'))
            else:
                return (HttpResponse('<html><body>Error: usuario no activo </body></html>'))
        else:
            return (HttpResponse('<html><body><b>Error: usuario o contrase&ntilde;a incorrectos</b><br><a href=/>Volver a la página principal</a></body></html>'))

    return render(request, 'actualizar_whoosh.html', {'formulario': formulario})

#Búsqueda de series y películas por su título
def buscarPorTitulo(request):
    if request.method == 'POST':
        form = TituloBusquedaForm(request.POST, request.FILES)
        if form.is_valid():
            titulo = form.cleaned_data['titulo']
            ix = open_dir('./Pelicula')
            searcher = ix.searcher()
            query = MultifieldParser(
                ["titulo","tituloOriginal"], ix.schema).parse(titulo)
            results = searcher.search(query)
            results_peliculas = list(results)
            peliculas = []
            series = []
            for pelicula in results_peliculas:
                aux = Pelicula.objects.filter(titulo=pelicula.fields()['titulo'])
                if (len(aux) > 0):
                    peliculas.append(aux[0])
            ixA = open_dir("./Serie")
            searcher = ixA.searcher()
            query = MultifieldParser(
                ["titulo","tituloOriginal"], ixA.schema).parse(titulo)
            results = searcher.search(query)
            results_series = list(results)
            for serie in results_series:
                aux = Serie.objects.filter(titulo=serie.fields()['titulo'])
                if (len(aux) > 0):
                    series.append(aux[0])
            return render(request, 'busqueda_titulo.html', {'peliculas': peliculas, 'series': series})
    form = TituloBusquedaForm()
    return render(request, 'busqueda_titulo.html', {'form': form})

#Búsqueda de títulos según la plataforma de streaming en que están disponibles
def buscarPorPlataforma(request):
    if request.method == 'POST':
        form = PlataformaBusquedaForm(request.POST, request.FILES)
        if form.is_valid():
            plataformas = form.cleaned_data['plataformas']
            ix = open_dir('./Pelicula')
            searcher = ix.searcher()
            query = QueryParser(
                "plataformas", ix.schema).parse("'" + plataformas + "'")
            results = searcher.search(query, limit=250)
            results_peliculas = list(results)
            peliculas = []
            series = []
            for pelicula in results_peliculas:
                aux = Pelicula.objects.filter(titulo=pelicula.fields()['titulo'])
                if (len(aux) > 0):
                    peliculas.append(aux[0])
            ixA = open_dir("./Serie")
            searcher = ixA.searcher()
            query = QueryParser(
                "plataformas", ixA.schema).parse("'" + plataformas + "'")
            results = searcher.search(query, limit=250)
            results_series = list(results)
            for serie in results_series:
                aux = Serie.objects.filter(titulo=serie.fields()['titulo'])
                if (len(aux) > 0):
                    series.append(aux[0])
            return render(request, 'busqueda_plataforma.html', {'peliculas': peliculas, 'series': series})
    form = TituloBusquedaForm()
    return render(request, 'busqueda_plataforma.html', {'form': form})

#Busqueda de títulos según el género al que pertenecen
def buscarPorGenero(request):
    if request.method == 'POST':
        form = GeneroBusquedaForm(request.POST, request.FILES)
        if form.is_valid():
            plataformas_peliculas = []
            plataformas_series = []
            links_peliculas = []
            links_series = []
            generos = form.cleaned_data['generos']
            ix = open_dir('./Pelicula')
            searcher = ix.searcher()
            query = QueryParser(
                "generos", ix.schema).parse("'" + generos + "'")
            results = searcher.search(query, limit=250)
            results_peliculas = list(results)
            peliculas = []
            series = []
            for pelicula in results_peliculas:
                aux = Pelicula.objects.filter(titulo=pelicula.fields()['titulo'])
                if (len(aux) > 0):
                    peliculas.append(aux[0])
            ixA = open_dir("./Serie")
            searcher = ixA.searcher()
            query = QueryParser(
                "generos", ixA.schema).parse("'" + generos + "'")
            results = searcher.search(query, limit=250)
            results_series = list(results)
            for serie in results_series:
                aux = Serie.objects.filter(titulo=serie.fields()['titulo'])
                if (len(aux) > 0):
                    series.append(aux[0])
            return render(request, 'busqueda_genero.html', {'peliculas': peliculas, 'series': series})
    form = TituloBusquedaForm()
    return render(request, 'busqueda_genero.html', {'form': form})

#Busqueda de títulos con una puntuación igual o mayor que la proporcionada
def buscarPorPuntuacion(request):
    formulario = PuntuacionBusquedaForm()
    peliculas = []
    series = []
    plataformas_peliculas = []
    plataformas_series = []
    links_peliculas = []
    links_series = []

    if request.method == 'POST':
        formulario = PuntuacionBusquedaForm(request.POST)
        if formulario.is_valid():
            for pelicula in Pelicula.objects.all():
                if (pelicula.imdb != "-"):
                    if(pelicula.imdb >= formulario.cleaned_data['puntuacion']):
                        test = pelicula.generos
                        peliculas.append(pelicula)
            for serie in Serie.objects.all():
                if (serie.imdb != "-"):
                    if(serie.imdb >= formulario.cleaned_data['puntuacion']):
                        series.append(serie)

    return render(request, 'busqueda_puntuacion.html', {'formulario': formulario, 'peliculas': peliculas, 'series': series})

def recomendarPeliculas(id_pelicula):
    pelicula = get_object_or_404(Pelicula, pk=id_pelicula)
    peliculas = Pelicula.objects.all()

    #Se crean los valores de la columna de titulos
    movies_titles = []
    for movie in peliculas:
        if str(movie.titulo) != str(pelicula.titulo):
            movies_titles.append(movie.titulo)
    movies_titles.append(pelicula.titulo)

    #Se crean los valores de la columna de valores
    values = []
    for movie in peliculas:
        movie_values = []
        generos = ''
        if str(movie.titulo) != str(pelicula.titulo):
            for genero in movie.generos.all():
                generos += ', ' + genero.nombre
            movie_values.append(generos[2:])
            values.append(movie_values)
    movie_values = []
    generos = ''
    for genero in pelicula.generos.all():
        generos += ', ' + genero.nombre
    movie_values.append(generos[2:])
    values.append(movie_values)

    #Se crea la tabla
    d = {'titulo': movies_titles, 'valores': values}
    df = pd.DataFrame(data=d, index=movies_titles)
    df = df[['titulo', 'valores']]
    df.head()
    df['key_words'] = ''
    for index, row in df.iterrows():
        valor = row['valores']
        r = Rake()
        r.extract_keywords_from_text(valor[0])
        key_words_dict_scores = r.get_word_degrees()
        row['key_words'] = str(list(key_words_dict_scores.keys()))
    df.drop(columns=['valores'], inplace=True)
    count = CountVectorizer()
    count_matrix = count.fit_transform(df['key_words'])
    cosine_sim = cosine_similarity(count_matrix, count_matrix)
    recommended_movies = []
    indices = pd.Series(df.index)
    idx = indices[indices == pelicula.titulo].index[0]
    score_series = pd.Series(cosine_sim[idx]).sort_values(ascending=False)
    top_3_indexes = list(score_series.iloc[1:4].index)
    for i in top_3_indexes:
        recommended_movies.append(list(df.index)[i])
    if str(pelicula.titulo) in recommended_movies:
        recommended_movies.remove(str(pelicula.titulo))
        recommended_movies.append(list(df.index)[score_series.iloc[4:5].index[0]])

    return recommended_movies

def recomendarSeries(id_serie):
    serie = get_object_or_404(Serie, pk=id_serie)
    series = Serie.objects.all()

    #Se crean los valores de la columna de titulos
    shows_titles = []
    for show in series:
        if str(show.titulo) != str(serie.titulo):
            shows_titles.append(show.titulo)
    shows_titles.append(serie.titulo)

    #Se crean los valores de la columna de valores
    values = []
    for show in series:
        show_values = []
        generos = ''
        if str(show.titulo) != str(serie.titulo):
            for genero in show.generos.all():
                generos += ', ' + genero.nombre
            show_values.append(generos[2:])
            values.append(show_values)
    shows_values = []
    generos = ''
    for genero in serie.generos.all():
        generos += ', ' + genero.nombre
    shows_values.append(generos[2:])
    values.append(shows_values)

    #Se crea la tabla
    d = {'titulo': shows_titles, 'valores': values}
    df = pd.DataFrame(data=d, index=shows_titles)
    df = df[['titulo', 'valores']]
    df.head()
    df['key_words'] = ''
    for index, row in df.iterrows():
        valor = row['valores']
        r = Rake()
        r.extract_keywords_from_text(valor[0])
        key_words_dict_scores = r.get_word_degrees()
        row['key_words'] = str(list(key_words_dict_scores.keys()))
    df.drop(columns=['valores'], inplace=True)
    count = CountVectorizer()
    count_matrix = count.fit_transform(df['key_words'])
    cosine_sim = cosine_similarity(count_matrix, count_matrix)
    recommended_shows = []
    indices = pd.Series(df.index)
    idx = indices[indices == serie.titulo].index[0]
    score_series = pd.Series(cosine_sim[idx]).sort_values(ascending=False)
    top_3_indexes = list(score_series.iloc[1:4].index)
    for i in top_3_indexes:
        recommended_shows.append(list(df.index)[i])
    if str(serie.titulo) in recommended_shows:
        recommended_shows.remove(str(serie.titulo))
        recommended_shows.append(list(df.index)[score_series.iloc[4:5].index[0]])

    return recommended_shows