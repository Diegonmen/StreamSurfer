from django import forms

PLATAFORMAS = [
    ('Netflix', 'Netflix'),
    ('Rakuten TV', 'Rakuten TV'),
    ('Amazon Prime Video', 'Amazon Prime Video'),
    ('Atres Player', 'Atres Player'),
    ('HBO', 'HBO'),
    ('Movistar Plus', 'Movistar Plus'),
    ('Disney Plus', 'Disney Plus'),
    ('Filmin', 'Filmin'),
    ('Apple TV Plus', 'Apple TV Plus'),
    ('Crunchyroll', 'Crunchyroll')]

GENEROS = [
    ('Acción & Aventura', 'Acción & Aventura'),
    ('Animación', 'Animación'),
    ('Comedia', 'Comedia'),
    ('Crimen', 'Crimen'),
    ('Documental', 'Documental'),
    ('Drama', 'Drama'),
    ('Fantasía', 'Fantasía'),
    ('Historia', 'Historia'),
    ('Terror', 'Terror'),
    ('Familia', 'Familia'),
    ('Música', 'Música'),
    ('Misterio & Suspense', 'Misterio & Suspense'),
    ('Romance', 'Romance'),
    ('Ciencia Ficción', 'Ciencia Ficción'),
    ('Deporte', 'Deporte'),
    ('Guerra', 'Guerra'),
    ('Western', 'Western'),
    ('Reality TV', 'Reality TV'),
    ('Made in Europe', 'Made in Europe')]

class TituloBusquedaForm(forms.Form):
    titulo = forms.CharField(label="Título de la pelicula o serie", widget=forms.TextInput, required=True)

class PlataformaBusquedaForm(forms.Form):
    plataformas = forms.CharField(label="Plataforma de streaming", widget=forms.RadioSelect(choices=PLATAFORMAS), required=True)

class GeneroBusquedaForm(forms.Form):
    generos = forms.CharField(label="Géneros", widget=forms.RadioSelect(choices=GENEROS), required=True)