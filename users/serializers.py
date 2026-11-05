from rest_framework import serializers
from .models import User, Doctor, Patient, MonitoringSession

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name','phone', 'role', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)  

class DoctorSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Doctor
        fields = ['id', 'user', 'hospital', 'location','specialization']  

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = User.Role.DOCTOR
        user = UserSerializer().create(user_data)
        return Doctor.objects.create(user=user, **validated_data)  

    def update(self, instance, validated_data):          
        validated_data.pop('user', None)
        return super().update(instance, validated_data)        

class PatientSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    class Meta:
        model = Patient
        fields = ['id', 'user', 'doctor', 'hospital', 'location', 'date_of_birth', 'is_rpm', 'is_ccm']

    def create  (self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = User.Role.PATIENT
        user = UserSerializer().create(user_data)
        return Patient.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('user', None)
        return super().update(instance, validated_data)    

    def validate(self, data):
        hospital = data.get('hospital') or (self.instance.hospital if self.instance else None)
        location = data.get('location')
        if location and hospital and location.hospital_id != hospital.id:
            raise serializers.ValidationError(
                "Location is hospital se related nahi hai."
            )
        return data


class MonitoringSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringSession
        fields = [
            "id", "patient", "doctor", "program",
            "start_time", "end_time", "duration_minutes", "notes",
        ]
        read_only_fields = ["duration_minutes"]
        extra_kwargs = {"doctor": {"required": False}} 

    def validate(self, attrs):
        patient = attrs.get("patient") or getattr(self.instance, "patient", None)
        program = attrs.get("program") or getattr(self.instance, "program", None)
        start = attrs.get("start_time") or getattr(self.instance, "start_time", None)
        end = attrs.get("end_time") or getattr(self.instance, "end_time", None)

        if start and end and end <= start:
            raise serializers.ValidationError("end_time must be after start_time.")

        if patient and program:
            flag = MonitoringSession.PROGRAM_FIELD[program]
            if not getattr(patient, flag, False):
                raise serializers.ValidationError(
                    f"This patient is not enrolled in {program}."
                )
        return attrs        










