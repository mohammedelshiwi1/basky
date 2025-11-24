
from django.urls import path
from . import views

app_name = 'basky'

urlpatterns = [
    # ==============================================
    # Pages
    # ==============================================
    path('device-setup/', views.device_setup_page, name='device_setup'),
    path('devices/', views.device_list_page, name='device_list'),
    path('device/<str:device_id>/', views.device_dashboard, name='device_dashboard'),
    
    # ==============================================
    # Device Management API
    # ==============================================
    path('api/test-connection/', views.test_device_connection, name='test_connection'),
    path('api/save-device/', views.save_device_config, name='save_device'),
    path('api/delete-device/<str:device_id>/', views.delete_device, name='delete_device'),
    
    # ==============================================
    # Device Control API
    # ==============================================
    path('api/device/<str:device_id>/start-session/', views.start_session_api, name='start_session'),
    path('api/device/<str:device_id>/stop-session/', views.stop_session_api, name='stop_session'),
    path('api/device/<str:device_id>/calibrate/', views.calibrate_device_api, name='calibrate'),
    path('api/device/<str:device_id>/ai-correction/', views.send_ai_correction_api, name='ai_correction'),
    path('api/device/<str:device_id>/network-info/', views.get_network_info_api, name='network_info'),
    path('api/device/<str:device_id>/reset-wifi/', views.reset_wifi_api, name='reset_wifi'),
    path('api/device/<str:device_id>/ping/', views.ping_device_api, name='ping_device'),
    
    # ==============================================
    # Data & Statistics API
    # ==============================================
    path('api/device/<str:device_id>/status/', views.get_device_status_api, name='device_status'),
    path('api/device/<str:device_id>/readings/', views.get_latest_readings_api, name='latest_readings'),
    path('api/device/<str:device_id>/stats/', views.get_session_stats_api, name='session_stats'),
]