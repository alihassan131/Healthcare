from django.db import models
from django.contrib.auth.models import AbstractUser
from hospitals.models import Hospital,Location

class User(AbstractUser):
    class Role(models.TextChoices):
        DOCTOR = 'doctor', 'Doctor'
        PATIENT = 'patient','Patient'

    role = models.CharField(max_length=15, choices=Role.choices, null=True, blank=True)  
    phone = models.CharField(max_length=20, blank=True)

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='doctors')
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctors'
    )
    specialization = models.CharField(max_length=100)

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"
class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='patients')

    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='patients')
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='patients'
    )
    date_of_birth = models.DateField(null=True, blank=True)            

    is_rpm = models.BooleanField(default=False, verbose_name='RPM')
    is_ccm = models.BooleanField(default=False, verbose_name='CCM')

    def __str__(self):
        return self.user.get_full_name() or self.user.username

class MonitoringSession(models.Model):
    PROGRAM_CHOICES = [("RPM", "RPM"), ("CCM", "CCM")]

    PROGRAM_FIELD = {"RPM": "is_rpm", "CCM": "is_ccm"}

    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="monitoring_sessions"
    )
    doctor = models.ForeignKey(
        Doctor, on_delete=models.PROTECT, related_name="monitoring_sessions"
    )
    program = models.CharField(max_length=3, choices=PROGRAM_CHOICES)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(editable=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_time"]
        indexes = [models.Index(fields=["patient", "program", "start_time"])]

    def save(self, *args, **kwargs):
        delta = self.end_time - self.start_time
        self.duration_minutes = int(delta.total_seconds() // 60)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient_id} - {self.program} - {self.duration_minutes} min"