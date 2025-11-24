
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min
from datetime import timedelta
import json
import socket
import subprocess
import asyncio
from asgiref.sync import async_to_sync

from .models import DeviceConfig, DeviceStatus, SensorReading, Session
from .consumers import BaskyDeviceConsumer


# ==============================================
# Device Setup Pages
# ==============================================

@login_required
def device_setup_page(request):
    """صفحة إعداد الجهاز"""
    context = {
        'server_ip': get_server_ip(),
        'ws_port': 8080,
        'devices': DeviceConfig.objects.filter(user=request.user),
    }
    return render(request, 'device_setup.html', context)


@login_required
def device_list_page(request):
    """صفحة قائمة الأجهزة"""
    devices = DeviceConfig.objects.filter(user=request.user)
    connected_devices = BaskyDeviceConsumer.get_connected_devices()
    
    # إضافة حالة الاتصال لكل جهاز
    for device in devices:
        device.is_connected = device.device_id in connected_devices
        if device.is_connected:
            device.connection_info = connected_devices[device.device_id]
    
    context = {
        'devices': devices,
        'total_devices': devices.count(),
        'connected_count': len([d for d in devices if d.is_connected]),
    }
    return render(request, 'device_list.html', context)


@login_required
def device_dashboard(request, device_id):
    """Dashboard للجهاز"""
    device = get_object_or_404(DeviceConfig, device_id=device_id, user=request.user)
    connected_devices = BaskyDeviceConsumer.get_connected_devices()
    
    # معلومات الاتصال
    is_connected = device_id in connected_devices
    connection_info = connected_devices.get(device_id, {})
    
    # آخر قراءات
    latest_readings = SensorReading.objects.filter(
        device_id=device_id
    ).order_by('-timestamp')[:20]
    
    # الجلسات الأخيرة
    recent_sessions = Session.objects.filter(
        device=device
    ).order_by('-start_time')[:10]
    
    # إحصائيات
    stats = {
        'total_sessions': Session.objects.filter(device=device).count(),
        'total_readings': SensorReading.objects.filter(device_id=device_id).count(),
        'avg_session_duration': Session.objects.filter(device=device).aggregate(
            Avg('duration')
        )['duration__avg'] or 0,
    }
    
    context = {
        'device': device,
        'is_connected': is_connected,
        'connection_info': connection_info,
        'latest_readings': latest_readings,
        'recent_sessions': recent_sessions,
        'stats': stats,
    }
    return render(request, 'device_dashboard.html', context)


# ==============================================
# API Endpoints - Device Management
# ==============================================

@csrf_exempt
@login_required
def test_device_connection(request):
    """اختبار اتصال الجهاز"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            device_ip = data.get('device_ip')
            
            # محاولة ping
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', device_ip],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0:
                return JsonResponse({
                    'success': True,
                    'message': f'✓ الجهاز متصل! ({device_ip})',
                    'device_ip': device_ip,
                    'latency': extract_ping_time(result.stdout)
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': '✗ لا يمكن الوصول للجهاز. تأكد من الاتصال بنفس الشبكة.'
                })
        except subprocess.TimeoutExpired:
            return JsonResponse({
                'success': False,
                'message': '✗ انتهى وقت الانتظار. الجهاز غير متصل.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'✗ خطأ: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
@login_required
def save_device_config(request):
    """حفظ إعدادات الجهاز"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            device_name = data.get('device_name', 'Basky Device')
            device_ip = data.get('device_ip')
            ws_port = data.get('ws_port', 8080)
            
            # إنشاء device_id فريد
            device_id = f"basky_{device_ip.replace('.', '_')}"
            
            # حفظ أو تحديث
            device, created = DeviceConfig.objects.update_or_create(
                device_id=device_id,
                defaults={
                    'user': request.user,
                    'device_name': device_name,
                    'device_ip': device_ip,
                    'ws_host': get_server_ip(),
                    'ws_port': ws_port,
                    'is_active': True
                }
            )
            
            action = 'تم إضافة' if created else 'تم تحديث'
            
            return JsonResponse({
                'success': True,
                'message': f'{action} الجهاز بنجاح!',
                'device_id': device_id,
                'device_name': device_name
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطأ في الحفظ: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
@login_required
def delete_device(request, device_id):
    """حذف جهاز"""
    if request.method == 'POST':
        try:
            device = get_object_or_404(DeviceConfig, device_id=device_id, user=request.user)
            device_name = device.device_name
            device.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'تم حذف {device_name} بنجاح'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطأ في الحذف: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


# ==============================================
# API Endpoints - Device Control
# ==============================================

@csrf_exempt
@login_required
def start_session_api(request, device_id):
    """بدء جلسة علاج"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            device = get_object_or_404(DeviceConfig, device_id=device_id, user=request.user)
            
            # إنشاء جلسة جديدة
            session = Session.objects.create(
                device=device,
                user=request.user,
                child_name=data.get('child_name', 'طفل'),
                exercise_type=data.get('exercise', 'Stretching'),
                difficulty=data.get('difficulty', 'medium'),
                is_active=True
            )
            
            # إرسال الأمر للجهاز
            session_data = {
                'child_name': session.child_name,
                'user_role': data.get('user_role', 'Parent'),
                'difficulty': session.difficulty,
                'exercise': session.exercise_type
            }
            
            success = async_to_sync(BaskyDeviceConsumer.send_command_to_device)(
                device_id, 'start_session', session_data
            )
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'تم بدء الجلسة بنجاح!',
                    'session_id': session.id
                })
            else:
                session.delete()
                return JsonResponse({
                    'success': False,
                    'message': 'الجهاز غير متصل'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطأ: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
@login_required
def stop_session_api(request, device_id):
    """إيقاف جلسة علاج"""
    if request.method == 'POST':
        try:
            # إيقاف الجلسة النشطة
            sessions = Session.objects.filter(
                device__device_id=device_id,
                is_active=True
            )
            
            for session in sessions:
                session.end_session()
            
            # إرسال الأمر للجهاز
            success = async_to_sync(BaskyDeviceConsumer.send_command_to_device)(
                device_id, 'stop_session', {}
            )
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'تم إيقاف الجلسة بنجاح!'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'الجهاز غير متصل'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطأ: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
@login_required
def calibrate_device_api(request, device_id):
    """معايرة الجهاز"""
    if request.method == 'POST':
        try:
            success = async_to_sync(BaskyDeviceConsumer.send_command_to_device)(
                device_id, 'calibrate', {}
            )
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'تم إرسال أمر المعايرة'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'الجهاز غير متصل'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطأ: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
@login_required
def send_ai_correction_api(request, device_id):
    """إرسال تصحيح من الـ AI"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            correction_data = {
                'needed': data.get('needed', False),
                'shoulder': data.get('shoulder', {}),
                'elbow': data.get('elbow', {}),
                'wrist': data.get('wrist', {}),
                'feedback': data.get('feedback', '')
            }
            
            success = async_to_sync(BaskyDeviceConsumer.send_command_to_device)(
                device_id, 'ai_correction', correction_data
            )
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'تم إرسال التصحيح'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'الجهاز غير متصل'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطأ: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
@login_required
def get_network_info_api(request, device_id):
    """طلب معلومات الشبكة"""
    if request.method == 'POST':
        try:
            success = async_to_sync(BaskyDeviceConsumer.send_command_to_device)(
                device_id, 'get_network_info', {}
            )
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'تم إرسال الطلب'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'الجهاز غير متصل'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطأ: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
@login_required
def reset_wifi_api(request, device_id):
    """إعادة ضبط WiFi"""
    if request.method == 'POST':
        try:
            success = async_to_sync(BaskyDeviceConsumer.send_command_to_device)(
                device_id, 'reset_wifi', {}
            )
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'تم إرسال أمر إعادة الضبط. الجهاز سيعيد التشغيل.'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'الجهاز غير متصل'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'خطأ: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
@login_required
def ping_device_api(request, device_id):
    """Ping الجهاز"""
    if request.method == 'POST':
        try:
            success = async_to_sync(BaskyDeviceConsumer.send_command_to_device)(
                device_id, 'ping', {}
            )
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'Ping sent'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Device offline'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


# ==============================================
# API Endpoints - Data & Statistics
# ==============================================

@login_required
def get_device_status_api(request, device_id):
    """الحصول على حالة الجهاز"""
    try:
        device = get_object_or_404(DeviceConfig, device_id=device_id, user=request.user)
        connected_devices = BaskyDeviceConsumer.get_connected_devices()
        
        is_connected = device_id in connected_devices
        connection_info = connected_devices.get(device_id, {})
        
        # آخر حالة
        last_status = DeviceStatus.objects.filter(
            device_id=device_id
        ).first()
        
        return JsonResponse({
            'success': True,
            'device_id': device_id,
            'device_name': device.device_name,
            'is_connected': is_connected,
            'connection_info': connection_info,
            'last_status': {
                'status': last_status.status if last_status else 'unknown',
                'message': last_status.message if last_status else '',
                'timestamp': last_status.timestamp.isoformat() if last_status else None
            } if last_status else None
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطأ: {str(e)}'
        })


@login_required
def get_latest_readings_api(request, device_id):
    """الحصول على آخر القراءات"""
    try:
        limit = int(request.GET.get('limit', 20))
        
        readings = SensorReading.objects.filter(
            device_id=device_id
        ).order_by('-timestamp')[:limit]
        
        data = [{
            'timestamp': r.timestamp.isoformat(),
            'shoulder': {
                'pitch': r.shoulder_pitch,
                'roll': r.shoulder_roll,
                'yaw': r.shoulder_yaw
            },
            'elbow': {
                'pitch': r.elbow_pitch,
                'roll': r.elbow_roll,
                'yaw': r.elbow_yaw
            },
            'wrist': {
                'pitch': r.wrist_pitch,
                'roll': r.wrist_roll,
                'yaw': r.wrist_yaw
            },
            'force': r.force_value,
            'exercise': r.exercise_type,
            'mode': r.mode
        } for r in readings]
        
        return JsonResponse({
            'success': True,
            'count': len(data),
            'readings': data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطأ: {str(e)}'
        })


@login_required
def get_session_stats_api(request, device_id):
    """الحصول على إحصائيات الجلسات"""
    try:
        device = get_object_or_404(DeviceConfig, device_id=device_id, user=request.user)
        
        # إحصائيات عامة
        total_sessions = Session.objects.filter(device=device).count()
        
        completed_sessions = Session.objects.filter(
            device=device,
            is_active=False
        )
        
        avg_duration = completed_sessions.aggregate(Avg('duration'))['duration__avg'] or 0
        max_duration = completed_sessions.aggregate(Max('duration'))['duration__max'] or 0
        
        # إحصائيات حسب نوع التمرين
        exercise_stats = completed_sessions.values('exercise_type').annotate(
            count=Count('id'),
            avg_duration=Avg('duration')
        )
        
        # إحصائيات حسب الصعوبة
        difficulty_stats = completed_sessions.values('difficulty').annotate(
            count=Count('id'),
            avg_duration=Avg('duration')
        )
        
        return JsonResponse({
            'success': True,
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions.count(),
            'avg_duration': round(avg_duration, 2),
            'max_duration': max_duration,
            'exercise_stats': list(exercise_stats),
            'difficulty_stats': list(difficulty_stats)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطأ: {str(e)}'
        })


# ==============================================
# Utility Functions
# ==============================================

def get_server_ip():
    """الحصول على IP الخاص بالسيرفر"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def extract_ping_time(ping_output):
    """استخراج وقت الـ ping من النتيجة"""
    try:
        import re
        match = re.search(r'time=(\d+\.?\d*)', ping_output)
        if match:
            return float(match.group(1))
    except:
        pass
    return None