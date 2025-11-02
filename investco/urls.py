from django.urls import path
from . import views

app_name = 'investco'

urlpatterns = [
    path('', views.home, name='home'),
    path('portfolios/', views.portfolio_list, name='portfolio_list'),
    path('portfolios/<int:portfolio_id>/', views.portfolio_detail, name='portfolio_detail'),
    path('add-value/<int:investment_id>/', views.add_investment_value, name='add_investment_value'),

    # Performance Reports
    path('portfolios/<int:portfolio_id>/performance/', views.portfolio_performance, name='portfolio_performance'),
    path('investments/<int:investment_id>/performance/', views.investment_performance, name='investment_performance'),
    path('compare/', views.comparative_performance, name='comparative_performance'),
    path('portfolios/<int:portfolio_id>/time-periods/', views.time_period_report, name='time_period_report'),
    path('portfolios/<int:portfolio_id>/asset-allocation/', views.asset_allocation_report, name='asset_allocation_report'),

    # Statements
    path('investments/<int:investment_id>/statements/', views.investment_statements, name='investment_statements'),
    path('statements/<int:statement_id>/', views.statement_detail, name='statement_detail'),
]