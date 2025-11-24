from django.db import models

# Create your models here.

from django.db import models
from core.models import CustomUser
from django.utils import timezone


class DeviceConfig(models.Model):
    """إعدادات الجهاز"""
    device_id = models.CharField(max_length=100, unique=True, db_index=True)
    device_name = models.CharField(max_length=100, default="Basky Device")
    device_ip = models.GenericIPAddressField(null=True, blank=True)
    ws_host = models.CharField(max_length=100, blank=True)
    ws_port = models.IntegerField(default=8080)
    ssid = models.CharField(max_length=100, blank=True)
    signal_strength = models.IntegerField(default=0)  # RSSI
    is_active = models.BooleanField(default=True)
    last_connected = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        ordering = ['-last_connected']
        verbose_name = "Device Configuration"
        verbose_name_plural = "Device Configurations"
    
    def __str__(self):
        return f"{self.device_name} ({self.device_id})"


class DeviceStatus(models.Model):
    """سجل حالات الجهاز"""
    device_id = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=50)  # connected, ready, calibrating, etc.
    message = models.TextField(blank=True)
    mode = models.CharField(max_length=20, default='normal')  # normal, demo
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Device Status"
        verbose_name_plural = "Device Statuses"
    
    def __str__(self):
        return f"{self.device_id} - {self.status} at {self.timestamp}"


class SensorReading(models.Model):
    """قراءات السنسورات"""
    device_id = models.CharField(max_length=100, db_index=True)
    
    # Shoulder
    shoulder_pitch = models.FloatField(default=0)
    shoulder_roll = models.FloatField(default=0)
    shoulder_yaw = models.FloatField(default=0)
    
    # Elbow
    elbow_pitch = models.FloatField(default=0)
    elbow_roll = models.FloatField(default=0)
    elbow_yaw = models.FloatField(default=0)
    
    # Wrist
    wrist_pitch = models.FloatField(default=0)
    wrist_roll = models.FloatField(default=0)
    wrist_yaw = models.FloatField(default=0)
    
    # Hand
    hand_pitch = models.FloatField(default=0)
    hand_roll = models.FloatField(default=0)
    hand_yaw = models.FloatField(default=0)
    
    # Force
    force_value = models.FloatField(default=0)
    
    # Session info
    exercise_type = models.CharField(max_length=50, blank=True)
    difficulty = models.CharField(max_length=20, blank=True)
    session_duration = models.IntegerField(default=0)  # seconds
    mode = models.CharField(max_length=20, default='normal')
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Sensor Reading"
        verbose_name_plural = "Sensor Readings"
        indexes = [
            models.Index(fields=['device_id', '-timestamp']),
            models.Index(fields=['exercise_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.device_id} - {self.exercise_type} at {self.timestamp}"


class Session(models.Model):
    """جلسات العلاج"""
    device = models.ForeignKey(DeviceConfig, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    child_name = models.CharField(max_length=100)
    exercise_type = models.CharField(max_length=50)
    difficulty = models.CharField(max_length=20)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0)  # seconds
    total_readings = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-start_time']
        verbose_name = "Therapy Session"
        verbose_name_plural = "Therapy Sessions"
    
    def __str__(self):
        return f"{self.child_name} - {self.exercise_type} ({self.start_time})"
    
    def end_session(self):
        """إنهاء الجلسة"""
        self.end_time = timezone.now()
        self.duration = int((self.end_time - self.start_time).total_seconds())
        self.is_active = False
        self.save()

