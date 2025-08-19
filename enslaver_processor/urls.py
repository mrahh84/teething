from django.urls import path
from . import views

app_name = 'enslaver_processor'

urlpatterns = [
    path('', views.index, name='index'),
    path('run-loop/', views.run_loop, name='run_loop'),
    path('status/', views.get_status, name='status'),
]
