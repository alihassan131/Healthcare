from datetime import datetime
from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Doctor, MonitoringSession, Patient
from .permissions import IsAdmin, IsAdminOrDoctor, IsAdminOrSelfDoctor
from .serializers import DoctorSerializer, MonitoringSessionSerializer, PatientSerializer


def is_admin(user):
    return user.is_superuser or user.is_staff


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.select_related('user', 'hospital', 'location')
    serializer_class = DoctorSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        if self.action in ('update', 'partial_update'):
            return [IsAuthenticated(), IsAdminOrSelfDoctor()]
        return [IsAdmin()]


class PatientViewSet(viewsets.ModelViewSet):
    serializer_class = PatientSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Patient.objects.select_related('user', 'doctor', 'hospital', 'location')

        if is_admin(user):
            return qs
        if user.role == 'doctor':
            return qs.filter(doctor__user=user)
        if user.role == 'patient':
            return qs.filter(user=user)
        return qs.none()

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        if self.action == 'destroy':
            return [IsAdmin()]
        return [IsAdminOrDoctor()]

    def perform_create(self, serializer):
        user = self.request.user
        if not is_not_admin(user) and user.role == 'User':
            serializer.save(doctor=user.doctor_profile)
        else:
            serializer.save()


def month_range(month_str):
    if month_str:
        year, month = map(int, month_str.split("-"))
    else:
        today = timezone.localdate()
        year, month = today.year, today.month
    start = timezone.make_aware(datetime(year, month, 1))
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return start, timezone.make_aware(datetime(ny, nm, 1))


class MonitoringSessionViewSet(viewsets.ModelViewSet):
    serializer_class = MonitoringSessionSerializer

    def get_queryset(self):
        user = self.request.user
        qs = MonitoringSession.objects.select_related("patient__user", "doctor__user")
        if is_admin(user):
            return qs
        if user.role == "doctor":
            return qs.filter(doctor__user=user)
        if user.role == "patient":
            return qs.filter(patient__user=user)
        return qs.none()

    def get_permissions(self):
        if self.action in ("list", "retrieve", "compliance"):
            return [IsAuthenticated()]
        if self.action == "destroy":
            return [IsAdmin()]
        return [IsAdminOrDoctor()]

    def perform_create(self, serializer):
        user = self.request.user
        patient = serializer.validated_data["patient"]

        if not is_admin(user) and user.role == "doctor":
            doctor = user.doctor_profile
            if patient.doctor_id != doctor.id:
                raise serializers.ValidationError("This is not your patient.")
            serializer.save(doctor=doctor)
        else:
            if "doctor" not in serializer.validated_data:
                raise serializers.ValidationError({"doctor": "This field is required."})
            serializer.save()

    @action(detail=False, methods=["GET"])
    def compliance(self, request):
        user = request.user
        program = request.query_params.get("program")
        patient_id = request.query_params.get("patient")
        month = request.query_params.get("month")

        if program and program not in ["RPM", "CCM"]:
            return Response(
                {"error": "Program must be RPM or CCM."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if patient_id and not patient_id.isdigit():
            return Response(
                {"error": "Patient ID must be a valid number."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start, end = month_range(month)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid month format. Use YYYY-MM."},
                status=status.HTTP_400_BAD_REQUEST
            )

        programs = [program] if program else ["RPM", "CCM"]
        patients = Patient.objects.all()

        if user.is_superuser or user.is_staff:
            pass
        elif user.role == "doctor":
            patients = patients.filter(doctor__user=user)
        elif user.role == "patient":
            patients = patients.filter(user=user)
        else:
            return Response(
                {"error": "You do not have permission."},
                status=status.HTTP_403_FORBIDDEN
            )

        if patient_id:
            patients = patients.filter(id=patient_id)

        # Response data structure ko dictionary block mein convert kiya taake keys bilkul saaf alag hon
        segmented_results = {"RPM": [], "CCM": []}

        for prog in programs:
            target = settings.MONITORING_TARGET_MINUTES[prog]
            flag = MonitoringSession.PROGRAM_FIELD[prog]
            enrolled_patients = patients.filter(**{flag: True})

            sessions = MonitoringSession.objects.filter(
                program=prog,
                start_time__gte=start,
                start_time__lt=end,
                patient__in=enrolled_patients
            )

            totals = {
                row["patient_id"]: row
                for row in sessions.values("patient_id").annotate(
                    total=Sum("duration_minutes"),
                    count=Count("id")
                )
            }

            doctor_totals = (
                sessions.values(
                    "patient_id",
                    "doctor_id",
                    "doctor__user__first_name",
                    "doctor__user__last_name"
                )
                .annotate(total=Sum("duration_minutes"))
            )

            doctors_by_patient = {}

            for row in doctor_totals:
                pid = row["patient_id"]
                if pid not in doctors_by_patient:
                    doctors_by_patient[pid] = []

                doctors_by_patient[pid].append({
                    "doctor_id": row["doctor_id"],
                    "doctor_name": (
                        f'{row["doctor__user__first_name"]} '
                        f'{row["doctor__user__last_name"]}'
                    ).strip(),
                    "minutes": row["total"] or 0
                })

            for patient in enrolled_patients:
                data = totals.get(patient.id, {})
                total_minutes = data.get("total") or 0
                session_count = data.get("count", 0)
                remaining_minutes = max(target - total_minutes, 0)
                compliant = total_minutes >= target

                item = {
                    "patient_id": patient.id,
                    "patient_name": str(patient),
                    "total_minutes": total_minutes,
                    "target_minutes": target,
                    "remaining_minutes": remaining_minutes,
                    "compliant": compliant,
                    "session_count": session_count,
                    "doctors": doctors_by_patient.get(patient.id, [])
                }
                segmented_results[prog].append(item)

        return Response({
            "month": month,
            "start_date": start,
            "end_date": end,
            "results": segmented_results
        })
