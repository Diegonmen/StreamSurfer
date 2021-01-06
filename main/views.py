from main.models import Genero, Stream, Pelicula, Serie
from bs4 import BeautifulSoup
import urllib.request
import lxml
import time
from datetime import datetime
from selenium import webdriver
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.db.models import Avg, Count
from django.conf import settings

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
            return render(request, 'cargaBD.html', {'mensaje':mensaje})
        else:
            return redirect("/")
           
    return render(request, 'confirmacion.html')

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