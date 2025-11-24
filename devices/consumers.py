# ==============================================
# 1. consumers.py - WebSocket Consumer
# ==============================================

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaskyDeviceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket Consumer للتواصل مع جهاز ESP32
    """
    
    # قاموس لتخزين جميع الأجهزة المتصلة
    connected_devices = {}
    
    async def connect(self):
        """عند اتصال جهاز جديد"""
        self.device_id = None
        self.device_ip = None
        self.user = self.scope.get('user')
        
        # قبول الاتصال
        await self.accept()
        
        logger.info(f"New WebSocket connection from {self.scope['client']}")
        
        # إرسال رسالة ترحيب
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Welcome to Basky Server!',
            'timestamp': datetime.now().isoformat(),
            'server_version': '1.0.0'
        }))
    
    async def disconnect(self, close_code):
        """عند قطع الاتصال"""
        if self.device_id and self.device_id in self.connected_devices:
            del self.connected_devices[self.device_id]
            logger.info(f"Device {self.device_id} disconnected")
            
            # إشعار المستخدمين بقطع الاتصال
            await self.notify_device_status('offline')
    
    async def receive(self, text_data):
        """استقبال البيانات من الجهاز"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', '')
            
            logger.debug(f"Received: {message_type}")
            
            # توجيه الرسالة حسب النوع
            if message_type == 'status':
                await self.handle_status(data)
            elif message_type == 'sensor_data':
                await self.handle_sensor_data(data)
            elif message_type == 'session_ack':
                await self.handle_session_ack(data)
            elif message_type == 'network_info':
                await self.handle_network_info(data)
            elif message_type == 'wifi_reset_ack':
                await self.handle_wifi_reset_ack(data)
            elif message_type == 'pong':
                await self.handle_pong(data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send_error(str(e))
    
    async def handle_status(self, data):
        """معالجة رسائل الحالة من الجهاز"""
        status = data.get('status', 'unknown')
        message = data.get('message', '')
        mode = data.get('mode', 'normal')
        
        logger.info(f"Device status: {status} - {message}")
        
        # تسجيل الجهاز
        if status == 'connected':
            self.device_id = data.get('device_id', f"device_{id(self)}")
            self.connected_devices[self.device_id] = {
                'consumer': self,
                'status': status,
                'mode': mode,
                'connected_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            }
            
            logger.info(f"Device registered: {self.device_id} (mode: {mode})")
        
        # حفظ في قاعدة البيانات
        await self.save_device_status(status, message, mode)
        
        # إشعار المستخدمين
        await self.notify_device_status(status, message)
    
    async def handle_sensor_data(self, data):
        """معالجة بيانات السنسورات"""
        try:
            # استخراج البيانات
            shoulder = data.get('shoulder', {})
            elbow = data.get('elbow', {})
            wrist = data.get('wrist', {})
            hand = data.get('hand', {})
            force = data.get('force', {})
            
            exercise = data.get('exercise', '')
            difficulty = data.get('difficulty', '')
            session_duration = data.get('session_duration', 0)
            mode = data.get('mode', 'normal')
            
            # تحديث آخر ظهور
            if self.device_id in self.connected_devices:
                self.connected_devices[self.device_id]['last_seen'] = datetime.now().isoformat()
            
            # حفظ في قاعدة البيانات
            await self.save_sensor_data({
                'shoulder': shoulder,
                'elbow': elbow,
                'wrist': wrist,
                'hand': hand,
                'force': force,
                'exercise': exercise,
                'difficulty': difficulty,
                'session_duration': session_duration,
                'mode': mode,
                'timestamp': data.get('timestamp', 0)
            })
            
            # إرسال للـ Dashboard (إذا كان هناك مستخدمين متابعين)
            await self.broadcast_to_dashboard(data)
            
            # معالجة بالـ AI (اختياري)
            # await self.process_with_ai(data)
            
        except Exception as e:
            logger.error(f"Error handling sensor data: {e}")
    
    async def handle_session_ack(self, data):
        """تأكيد بدء الجلسة"""
        status = data.get('status', '')
        logger.info(f"Session acknowledgment: {status}")
        
        await self.send(text_data=json.dumps({
            'type': 'session_confirmed',
            'message': 'Session started successfully',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_network_info(self, data):
        """معلومات الشبكة من الجهاز"""
        logger.info(f"Network info received: {data}")
        
        # حفظ معلومات الشبكة
        if self.device_id:
            self.connected_devices[self.device_id].update({
                'ssid': data.get('ssid', ''),
                'ip': data.get('ip', ''),
                'rssi': data.get('rssi', 0),
                'ws_host': data.get('ws_host', ''),
                'ws_port': data.get('ws_port', 0)
            })
        
        await self.save_network_info(data)
    
    async def handle_wifi_reset_ack(self, data):
        """تأكيد إعادة ضبط WiFi"""
        logger.info("WiFi reset acknowledged")
        
        await self.send(text_data=json.dumps({
            'type': 'wifi_reset_confirmed',
            'message': 'Device will restart shortly',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_pong(self, data):
        """استجابة Ping"""
        if self.device_id in self.connected_devices:
            self.connected_devices[self.device_id]['last_seen'] = datetime.now().isoformat()
    
    # ==============================================
    # أوامر للجهاز
    # ==============================================
    
    async def send_start_session(self, session_data):
        """إرسال أمر بدء جلسة"""
        await self.send(text_data=json.dumps({
            'type': 'start_session',
            'name': session_data.get('child_name', ''),
            'role': session_data.get('user_role', 'Parent'),
            'difficulty': session_data.get('difficulty', 'medium'),
            'exercise': session_data.get('exercise', 'Stretching'),
            'timestamp': datetime.now().isoformat()
        }))
        
        logger.info(f"Start session command sent: {session_data.get('exercise')}")
    
    async def send_stop_session(self):
        """إرسال أمر إيقاف جلسة"""
        await self.send(text_data=json.dumps({
            'type': 'stop_session',
            'timestamp': datetime.now().isoformat()
        }))
        
        logger.info("Stop session command sent")
    
    async def send_calibrate(self):
        """إرسال أمر معايرة"""
        await self.send(text_data=json.dumps({
            'type': 'calibrate',
            'timestamp': datetime.now().isoformat()
        }))
        
        logger.info("Calibrate command sent")
    
    async def send_ai_correction(self, correction_data):
        """إرسال تصحيح من الـ AI"""
        await self.send(text_data=json.dumps({
            'type': 'ai_correction',
            'correction_needed': correction_data.get('needed', False),
            'shoulder': correction_data.get('shoulder', {}),
            'elbow': correction_data.get('elbow', {}),
            'wrist': correction_data.get('wrist', {}),
            'feedback': correction_data.get('feedback', ''),
            'timestamp': datetime.now().isoformat()
        }))
        
        logger.info("AI correction sent")
    
    async def send_motor_control(self, motor_data):
        """إرسال تحكم في الموتورات"""
        await self.send(text_data=json.dumps({
            'type': 'motor_control',
            'shoulder': motor_data.get('shoulder', {}),
            'elbow': motor_data.get('elbow', {}),
            'wrist': motor_data.get('wrist', {}),
            'timestamp': datetime.now().isoformat()
        }))
    
    async def send_get_network_info(self):
        """طلب معلومات الشبكة"""
        await self.send(text_data=json.dumps({
            'type': 'get_network_info',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def send_reset_wifi(self):
        """إعادة ضبط WiFi"""
        await self.send(text_data=json.dumps({
            'type': 'reset_wifi',
            'timestamp': datetime.now().isoformat()
        }))
        
        logger.warning("WiFi reset command sent")
    
    async def send_ping(self):
        """إرسال Ping"""
        await self.send(text_data=json.dumps({
            'type': 'ping',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def send_error(self, error_message):
        """إرسال رسالة خطأ"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        }))
    
    # ==============================================
    # Database Operations
    # ==============================================
    
    @database_sync_to_async
    def save_device_status(self, status, message, mode):
        """حفظ حالة الجهاز في قاعدة البيانات"""
        try:
            from .models import DeviceStatus
            
            DeviceStatus.objects.create(
                device_id=self.device_id,
                status=status,
                message=message,
                mode=mode,
                ip_address=self.scope['client'][0] if self.scope.get('client') else None
            )
        except Exception as e:
            logger.error(f"Error saving device status: {e}")
    
    @database_sync_to_async
    def save_sensor_data(self, data):
        """حفظ بيانات السنسورات"""
        try:
            from .models import SensorReading
            
            SensorReading.objects.create(
                device_id=self.device_id,
                shoulder_pitch=data['shoulder'].get('pitch', 0),
                shoulder_roll=data['shoulder'].get('roll', 0),
                shoulder_yaw=data['shoulder'].get('yaw', 0),
                elbow_pitch=data['elbow'].get('pitch', 0),
                elbow_roll=data['elbow'].get('roll', 0),
                elbow_yaw=data['elbow'].get('yaw', 0),
                wrist_pitch=data['wrist'].get('pitch', 0),
                wrist_roll=data['wrist'].get('roll', 0),
                wrist_yaw=data['wrist'].get('yaw', 0),
                hand_pitch=data['hand'].get('pitch', 0),
                hand_roll=data['hand'].get('roll', 0),
                hand_yaw=data['hand'].get('yaw', 0),
                force_value=data['force'].get('force', 0),
                exercise_type=data.get('exercise', ''),
                difficulty=data.get('difficulty', ''),
                session_duration=data.get('session_duration', 0),
                mode=data.get('mode', 'normal')
            )
        except Exception as e:
            logger.error(f"Error saving sensor data: {e}")
    
    @database_sync_to_async
    def save_network_info(self, data):
        """حفظ معلومات الشبكة"""
        try:
            from .models import DeviceConfig
            
            DeviceConfig.objects.update_or_create(
                device_id=self.device_id,
                defaults={
                    'device_ip': data.get('ip', ''),
                    'ws_host': data.get('ws_host', ''),
                    'ws_port': data.get('ws_port', 8080),
                    'ssid': data.get('ssid', ''),
                    'signal_strength': data.get('rssi', 0),
                    'is_active': data.get('connected', False)
                }
            )
        except Exception as e:
            logger.error(f"Error saving network info: {e}")
    
    async def notify_device_status(self, status, message=''):
        """إشعار المستخدمين بحالة الجهاز"""
        # يمكن إرسال للـ Channel Layer للـ Dashboard
        pass
    
    async def broadcast_to_dashboard(self, data):
        """بث البيانات للـ Dashboard"""
        # يمكن استخدام Channel Layers
        pass
    
    # ==============================================
    # Utility Methods
    # ==============================================
    
    @classmethod
    def get_connected_devices(cls):
        """الحصول على جميع الأجهزة المتصلة"""
        return cls.connected_devices
    
    @classmethod
    async def send_command_to_device(cls, device_id, command_type, command_data):
        """إرسال أمر لجهاز معين"""
        if device_id in cls.connected_devices:
            consumer = cls.connected_devices[device_id]['consumer']
            
            if command_type == 'start_session':
                await consumer.send_start_session(command_data)
            elif command_type == 'stop_session':
                await consumer.send_stop_session()
            elif command_type == 'calibrate':
                await consumer.send_calibrate()
            elif command_type == 'ai_correction':
                await consumer.send_ai_correction(command_data)
            elif command_type == 'motor_control':
                await consumer.send_motor_control(command_data)
            elif command_type == 'get_network_info':
                await consumer.send_get_network_info()
            elif command_type == 'reset_wifi':
                await consumer.send_reset_wifi()
            elif command_type == 'ping':
                await consumer.send_ping()
            
            return True
        return False


