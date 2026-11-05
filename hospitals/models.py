from django.db import models

class Hospital(models.Model):
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Location(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('hospital','name')

    def __str__(self):
        return f"{self.hospital.name} - {self.name}"





