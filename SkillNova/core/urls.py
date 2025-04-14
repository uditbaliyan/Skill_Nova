from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('training_list/', views.training_list, name='training_list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('training/<int:pk>/', views.training_detail, name='training_detail'),
    path('training/<int:pk>/projects/', views.training_projects, name='training_projects'),
    path('project/<int:pk>/', views.project_detail, name='project_detail'),
    path('project/<int:pk>/instructions/', views.project_instructions, name='project_instructions'),
    path('project/<int:pk>/assignments/', views.project_assignments, name='project_assignments'),
    path('enroll/', views.enroll, name='enroll'),
    path('create-order/', views.create_order, name='create_order'),
    # path('payment-success/', views.payment_success, name='payment_success'),
    path('certificate/<int:training_id>/', views.generate_certificate, name='generate_certificate'),
]