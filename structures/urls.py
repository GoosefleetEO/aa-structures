from django.conf.urls import url
from . import views


app_name = 'structures'

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^list/$', views.structure_list, name='structure_list'),
    url(r'^list_data/$', views.structure_list_data, name='structure_list_data'),
    url(r'^add_owner/$', views.add_owner, name='add_owner'),
    
    
    url(r'^test/$', views.test, name='test'),
]
