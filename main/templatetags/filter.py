from django import template

register = template.Library()

@register.filter(name='splitStreams')
def splitStreams(value):
  aux = value.strip('[]').replace("(", "").split('), ')
  result = []
  for elem in aux:
    result.append(elem.replace(")", "").replace("'", "").replace('"', ''))
  return result

@register.filter(name='split')
def split(value, key):
  return value.split(key)