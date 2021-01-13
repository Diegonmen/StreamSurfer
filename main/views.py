from main.models import Genero, Stream, Pelicula, Serie
from main.forms import TituloBusquedaForm, PlataformaBusquedaForm, GeneroBusquedaForm
from bs4 import BeautifulSoup
import urllib.request
import lxml
import time
import os
import types
from datetime import datetime
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.db.models import Avg, Count
from django.conf import settings
from whoosh.index import create_in, open_dir
from whoosh.fields import ID, Schema, TEXT, NUMERIC, KEYWORD
from whoosh.qparser import QueryParser, MultifieldParser, OrGroup
import shutil

def getDatos():
    #variables para contar el número de registros que vamos a almacenar
    num_peliculas = 0
    num_series = 0
    num_generos = 0
    num_streams = 0

    #borramos todas las tablas de la BD
    Stream.objects.all().delete()
    Genero.objects.all().delete()
    Pelicula.objects.all().delete()
    Serie.objects.all().delete()

    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    options.add_argument('--headless')
    options.add_argument('log-level=2')
    driver = webdriver.Chrome(executable_path='C:/Users/34622/Documents/chromedriver.exe', options=options)
    scroll_pause_time = 2 # You can set your own pause time. My laptop is a bit slow so I use 1 sec

    lista_enlaces_peliculas = []
    lista_enlaces_series = []

    driver.get("https://www.justwatch.com/es/peliculas")
    time.sleep(3)  # Allow 2 seconds for the web page to open
    scrollable = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]/div/div/div[2]/div[2]')
    while True:
        page = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]')
        html = driver.execute_script("return arguments[0].innerHTML;", page) 
        s = BeautifulSoup(html, "lxml")
        peliculas = s.find("div", class_="vue-recycle-scroller").find_all("div", class_="title-list-grid__item")
        if (("https://www.justwatch.com" + peliculas[-1].a['href'] in lista_enlaces_peliculas) or (len(lista_enlaces_peliculas) >= 250)):
            break
        for pelicula in peliculas:
            if (len(lista_enlaces_peliculas) >= 250):
                break
            enlace = "https://www.justwatch.com" + pelicula.a['href']
            if (enlace not in lista_enlaces_peliculas):
                auxDriver = webdriver.Chrome(executable_path='C:/Users/34622/Documents/chromedriver.exe', options=options)
                auxDriver.get(enlace)
                time.sleep(2)
                s = BeautifulSoup(auxDriver.page_source, "lxml")
                datos = s.find("div", id="base").find("div",class_="jw-container").find("div", class_="jw-info-box")
                tituloyfecha = datos.find("div", class_="title-block").h1.text.strip()  
                titulo = tituloyfecha[:-6].strip()
                fecha = int(tituloyfecha[-6:].replace("(", "").replace(")", ""))
                #si no tiene título original se pone el título
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
                if (datos.find_all("div", class_="price-comparison__grid__row price-comparison__grid__row--stream")):
                    servicios = datos.find_all(lambda tag: tag.name == 'div' and tag.get('class') == ['monetizations'])[0].find("div", class_="price-comparison__grid__row price-comparison__grid__row--stream").find_all("div", class_="price-comparison__grid__row__element")
                    for servicio in servicios:
                        plataforma = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a.img['title']
                        link = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a['href']
                        streams.append((plataforma, link))
                lista_enlaces_peliculas.append(enlace)
                auxDriver.close()

                #almacenamos en la BD
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
                p = Pelicula.objects.create(titulo=titulo, tituloOriginal=titulo_original, fechaEstreno=fecha, imdb=imdb, poster=poster, director=director, duracion=duracion)
                #añadimos la lista de géneros y streams
                for g in lista_generos_obj:
                    p.generos.add(g)
                for st in lista_streams_obj:
                    p.streams.add(st)
                num_peliculas = num_peliculas + 1

        driver.execute_script("arguments[0].scrollIntoView();", scrollable)
        time.sleep(scroll_pause_time)

    driver.get("https://www.justwatch.com/es/series")
    time.sleep(3)  # Allow 2 seconds for the web page to open
    scrollable = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]/div/div/div[2]/div[2]')
    while True:  
        page = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]')
        html = driver.execute_script("return arguments[0].innerHTML;", page) 
        s = BeautifulSoup(html, "lxml")
        series = s.find("div", class_="vue-recycle-scroller").find_all("div", class_="title-list-grid__item")
        if (("https://www.justwatch.com" + series[-1].a['href'] in lista_enlaces_series) or (len(lista_enlaces_series) >= 250)):
            break
        for serie in series:
            if (len(lista_enlaces_series) >= 250):
                break
            enlace = "https://www.justwatch.com" + serie.a['href']
            if (enlace not in lista_enlaces_series):
                auxDriver = webdriver.Chrome(executable_path='C:/Users/34622/Documents/chromedriver.exe', options=options)
                auxDriver.get(enlace)
                time.sleep(2)
                s = BeautifulSoup(auxDriver.page_source, "lxml")
                datos = s.find("div", id="base").find("div",class_="jw-container").find("div", class_="jw-info-box")
                tituloyfecha = datos.find("div", class_="title-block").h1.text.strip()
                titulo = tituloyfecha[:-6].strip()
                fecha = int(tituloyfecha[-6:].replace("(", "").replace(")", ""))
                #si no tiene título original se pone el título
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
                generos = []
                lista_generos_aux = ficha[1].find("div", class_="detail-infos__detail--values").find_all("span", recursive=False)
                for genero in lista_generos_aux:
                    generos.append(genero.text.strip().replace(", ", ""))
                streams = []
                if (datos.find_all("div", class_="price-comparison__grid__row price-comparison__grid__row--stream")):
                    servicios = datos.find_all(lambda tag: tag.name == 'div' and tag.get('class') == ['monetizations'])[0].find("div", class_="price-comparison__grid__row price-comparison__grid__row--stream").find_all("div", class_="price-comparison__grid__row__element")
                    for servicio in servicios:
                        plataforma = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a.img['title']
                        link = servicio.find("div", class_="presentation-type price-comparison__grid__row__element__icon").a['href']
                        streams.append((plataforma, link))
                lista_enlaces_series.append(enlace)
                auxDriver.close()

                #almacenamos en la BD
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
                show = Serie.objects.create(titulo=titulo, tituloOriginal=titulo_original, fechaEstreno=fecha, imdb=imdb, poster=poster, temporadas=temporadas)
                #añadimos la lista de géneros y streams
                for g in lista_generos_obj:
                    show.generos.add(g)
                for st in lista_streams_obj:
                    show.streams.add(st)
                num_series = num_series + 1

        driver.execute_script("arguments[0].scrollIntoView();", scrollable)
        time.sleep(scroll_pause_time)

    return ((num_peliculas, num_series, num_generos, num_streams))

#carga los datos desde la web en la BD
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

#muestra el número de películas y series que hay en la BD
def inicio(request):
    num_peliculas=Pelicula.objects.all().count()
    num_series=Serie.objects.all().count()
    return render(request,'index.html', {'num_peliculas':num_peliculas, 'num_series':num_series})

#muestra un listado con los datos de las películas (título, título original, director, duracion, géneros, fecha de estreno y opciones de streaming)
def lista_peliculas(request):
    peliculas=Pelicula.objects.all()
    return render(request,'lista_peliculas.html', {'peliculas':peliculas, 'STATIC_URL': settings.STATIC_URL})

#muestra un listado con los datos de las series (título, título original, temporadas, géneros, fecha de estreno y opciones de streaming)
def lista_series(request):
    series=Serie.objects.all()
    return render(request,'lista_series.html', {'series':series, 'STATIC_URL': settings.STATIC_URL})

def schemaPelicula():
    schem = Schema(idPelicula=ID(stored=True, unique=True), titulo=TEXT(
        stored=True), tituloOriginal=TEXT(stored=True), imdb=TEXT(stored=True),
        fechaEstreno=TEXT(stored=True), poster=TEXT(stored=True), duracion=TEXT(stored=True),
        director=TEXT(stored=True), generos=KEYWORD(stored=True,commas=True),
        plataformas=KEYWORD(stored=True,commas=True), links=KEYWORD(stored=True,commas=True))
    return schem

def schemaSerie():
    schem = Schema(idSerie=ID(stored=True, unique=True), titulo=TEXT(
        stored=True), tituloOriginal=TEXT(stored=True), imdb=TEXT(stored=True),
        fechaEstreno=TEXT(stored=True), poster=TEXT(stored=True), temporadas=TEXT(stored=True),
        generos=KEYWORD(stored=True,commas=True), plataformas=KEYWORD(stored=True,commas=True),
        links=KEYWORD(stored=True,commas=True))
    return schem

def getWhooshInfo():
    pelicula_directory = './' + 'Pelicula'
    serie_directory = './' + 'Serie'

    #eliminamos el directorio del índice, si existe
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

    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    options.add_argument('--headless')
    options.add_argument('log-level=2')
    driver = webdriver.Chrome(executable_path='C:/Users/soulb/Downloads/chromedriver.exe', options=options)
    scroll_pause_time = 2 # You can set your own pause time. My laptop is a bit slow so I use 1 sec

    driver.get("https://www.justwatch.com/es/peliculas")
    time.sleep(3)  # Allow 2 seconds for the web page to open
    scrollable = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]/div/div/div[2]/div[2]')
    while True:
        page = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]')
        html = driver.execute_script("return arguments[0].innerHTML;", page) 
        s = BeautifulSoup(html, "lxml")
        peliculas = s.find("div", class_="vue-recycle-scroller").find_all("div", class_="title-list-grid__item")
        if (("https://www.justwatch.com" + peliculas[-1].a['href'] in lista_enlaces_peliculas) or (len(lista_enlaces_peliculas) >= 250)):
            break
        for pelicula in peliculas:
            if (len(lista_enlaces_peliculas) >= 250):
                break
            enlace = "https://www.justwatch.com" + pelicula.a['href']
            if (enlace not in lista_enlaces_peliculas):
                auxDriver = webdriver.Chrome(executable_path='C:/Users/soulb/Downloads/chromedriver.exe', options=options)
                auxDriver.get(enlace)
                time.sleep(2)
                s = BeautifulSoup(auxDriver.page_source, "lxml")
                datos = s.find("div", id="base").find("div",class_="jw-container").find("div", class_="jw-info-box")
                tituloyfecha = datos.find("div", class_="title-block").h1.text.strip()  
                titulo = tituloyfecha[:-6].strip()
                fecha = int(tituloyfecha[-6:].replace("(", "").replace(")", ""))
                #si no tiene título original se pone el título
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

                writer1.add_document(idPelicula=str(count_peliculas), titulo=str(titulo), tituloOriginal=str(titulo_original), imdb=str(imdb), fechaEstreno=str(fecha),
                    poster=str(poster), duracion=str(duracion), director=str(director), generos=str(generos), plataformas=str(plataformas), links=str(links))
                count_peliculas += 1

        driver.execute_script("arguments[0].scrollIntoView();", scrollable)
        time.sleep(scroll_pause_time)

    driver.get("https://www.justwatch.com/es/series")
    time.sleep(3)  # Allow 2 seconds for the web page to open
    scrollable = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]/div/div/div[2]/div[2]')
    while True:  
        page = driver.find_element_by_xpath('/html/body/ion-app/div[1]/div[1]/div/div[3]/ion-tab/ion-content/div[3]')
        html = driver.execute_script("return arguments[0].innerHTML;", page) 
        s = BeautifulSoup(html, "lxml")
        series = s.find("div", class_="vue-recycle-scroller").find_all("div", class_="title-list-grid__item")
        if (("https://www.justwatch.com" + series[-1].a['href'] in lista_enlaces_series) or (len(lista_enlaces_series) >= 250)):
            break
        for serie in series:
            if (len(lista_enlaces_series) >= 250):
                break
            enlace = "https://www.justwatch.com" + serie.a['href']
            if (enlace not in lista_enlaces_series):
                auxDriver = webdriver.Chrome(executable_path='C:/Users/soulb/Downloads/chromedriver.exe', options=options)
                auxDriver.get(enlace)
                time.sleep(2)
                s = BeautifulSoup(auxDriver.page_source, "lxml")
                datos = s.find("div", id="base").find("div",class_="jw-container").find("div", class_="jw-info-box")
                tituloyfecha = datos.find("div", class_="title-block").h1.text.strip()
                titulo = tituloyfecha[:-6].strip()
                fecha = int(tituloyfecha[-6:].replace("(", "").replace(")", ""))
                #si no tiene título original se pone el título
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

                writer2.add_document(idSerie=str(count_peliculas), titulo=str(titulo), tituloOriginal=str(titulo_original), imdb=str(imdb), fechaEstreno=str(fecha),
                    poster=str(poster), temporadas=str(temporadas), generos=str(generos), plataformas=str(plataformas), links=str(links))
                count_series += 1

        driver.execute_script("arguments[0].scrollIntoView();", scrollable)
        time.sleep(scroll_pause_time)

    writer1.commit()
    writer2.commit()

#carga los datos desde la web en Whoosh
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

def buscarPorTitulo(request):
    if request.method == 'POST':
        form = TituloBusquedaForm(request.POST, request.FILES)
        if form.is_valid():
            titulo = form.cleaned_data['titulo']
            ix = open_dir('./Pelicula')
            searcher = ix.searcher()
            query = MultifieldParser(
                ["titulo","tituloOriginal"], ix.schema, group=OrGroup).parse(titulo)
            results = searcher.search(query)
            peliculas = list(results)
            for pelicula in peliculas:
                plataformas_pelicula = pelicula.fields()['plataformas'].strip('][').replace("'", "").split(', ')
                links_pelicula = pelicula.fields()['links'].strip('][').replace("'", "").split(', ')
                zip_iterator_pelicula = zip(plataformas_pelicula, links_pelicula)
                streams_pelicula = dict(zip_iterator_pelicula)
                pelicula.a = types.SimpleNamespace()
                setattr(pelicula.a, 'streamsPelicula', streams_pelicula)
            ixA = open_dir("./Serie")
            searcher = ixA.searcher()
            query = MultifieldParser(
                ["titulo","tituloOriginal"], ixA.schema, group=OrGroup).parse(titulo)
            results = searcher.search(query)
            series = list(results)
            for serie in series:
                plataformas_serie = serie.fields()['plataformas'].strip('][').replace("'", "").split(', ')
                links_serie = serie.fields()['links'].strip('][').replace("'", "").split(', ')
                zip_iterator_serie = zip(plataformas_serie, links_serie)
                streams_serie = dict(zip_iterator_serie)
                serie.a = types.SimpleNamespace()
                setattr(serie.a, 'streamsSerie', streams_serie)
            return render(request, 'busqueda_titulo.html', {'peliculas': peliculas, 'series': series})
    form = TituloBusquedaForm()
    return render(request, 'busqueda_titulo.html', {'form': form})

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
            peliculas = list(results)
            for pelicula in peliculas:
                plataformas_pelicula = pelicula.fields()['plataformas'].strip('][').replace("'", "").split(', ')
                links_pelicula = pelicula.fields()['links'].strip('][').replace("'", "").split(', ')
                zip_iterator_pelicula = zip(plataformas_pelicula, links_pelicula)
                streams_pelicula = dict(zip_iterator_pelicula)
                pelicula.a = types.SimpleNamespace()
                setattr(pelicula.a, 'streamsPelicula', streams_pelicula)
            ixA = open_dir("./Serie")
            searcher = ixA.searcher()
            query = QueryParser(
                "plataformas", ixA.schema).parse("'" + plataformas + "'")
            results = searcher.search(query, limit=250)
            series = list(results)
            for serie in series:
                plataformas_serie = serie.fields()['plataformas'].strip('][').replace("'", "").split(', ')
                links_serie = serie.fields()['links'].strip('][').replace("'", "").split(', ')
                zip_iterator_serie = zip(plataformas_serie, links_serie)
                streams_serie = dict(zip_iterator_serie)
                serie.a = types.SimpleNamespace()
                setattr(serie.a, 'streamsSerie', streams_serie)
            return render(request, 'busqueda_plataforma.html', {'peliculas': peliculas, 'series': series})
    form = TituloBusquedaForm()
    return render(request, 'busqueda_plataforma.html', {'form': form})

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
            peliculas = list(results)
            for pelicula in peliculas:
                test1 = pelicula.fields()['plataformas']
                test2 = pelicula.fields()['links']
                plataformas_pelicula = pelicula.fields()['plataformas'].strip('][').replace("'", "").split(', ')
                links_pelicula = pelicula.fields()['links'].strip('][').replace("'", "").split(', ')
                zip_iterator_pelicula = zip(plataformas_pelicula, links_pelicula)
                streams_pelicula = dict(zip_iterator_pelicula)
                pelicula.a = types.SimpleNamespace()
                setattr(pelicula.a, 'streamsPelicula', streams_pelicula)
            ixA = open_dir("./Serie")
            searcher = ixA.searcher()
            query = QueryParser(
                "generos", ixA.schema).parse("'" + generos + "'")
            results = searcher.search(query, limit=250)
            series = list(results)
            for serie in series:
                plataformas_serie = serie.fields()['plataformas'].strip('][').replace("'", "").split(', ')
                links_serie = serie.fields()['links'].strip('][').replace("'", "").split(', ')
                zip_iterator_serie = zip(plataformas_serie, links_serie)
                streams_serie = dict(zip_iterator_serie)
                serie.a = types.SimpleNamespace()
                setattr(serie.a, 'streamsSerie', streams_serie)
            return render(request, 'busqueda_genero.html', {'peliculas': peliculas, 'series': series})
    form = TituloBusquedaForm()
    return render(request, 'busqueda_genero.html', {'form': form})