from rest_framework import serializers, status, viewsets
from .models import Doctor, Patient,MonitoringSession
from .serializers import DoctorSerializer, PatientSerializer,MonitoringSessionSerializer
from rest_framework.permissions import IsAuthenticated
from .permissions import IsAdmin, IsAdminOrDoctor, IsAdminOrSelfDoctor
from datetime import datetime
from django.db.models import Count, Sum
from django.conf import settings
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.decorators import action




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
        if not is_admin(user) and user.role == 'doctor':
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

        if patient_id and not patient_id.isdigit():
            return Response({"detail": "patient must be a number"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            start, end = month_range(request.query_params.get("month"))
        except ValueError:
            return Response({"detail": "month must look like 2026-10"},
                            status=status.HTTP_400_BAD_REQUEST)

        programs = [program] if program in ("RPM", "CCM") else ["RPM", "CCM"]
        results = []

        
        ccm_target = settings.MONITORING_TARGET_MINUTES["CCM"]
        ccm_totals = {
            r["patient_id"]: r
            for r in MonitoringSession.objects.filter(
                program="CCM", start_time__gte=start, start_time__lt=end,
            ).values("patient_id").annotate(total=Sum("duration_minutes"), count=Count("id"))
        }

        for prog in programs:
            target = settings.MONITORING_TARGET_MINUTES[prog]
            flag = MonitoringSession.PROGRAM_FIELD[prog]

            
            patients = Patient.objects.select_related("user").filter(**{flag: True})
            if is_admin(user):
                pass
            elif user.role == "doctor":
                patients = patients.filter(doctor__user=user)
            elif user.role == "patient":
                patients = patients.filter(user=user)
            else:
                patients = patients.none()
            if patient_id:
                patients = patients.filter(id=patient_id)

            sessions = MonitoringSession.objects.filter(
                program=prog, start_time__gte=start, start_time__lt=end,
                patient__in=patients,
            )

            totals = {
                r["patient_id"]: r
                for r in sessions.values("patient_id")
                .annotate(total=Sum("duration_minutes"), count=Count("id"))
            }

            per_doctor = {}
            rows = (sessions
                    .values("patient_id", "doctor_id", "doctor__user__username")
                    .annotate(minutes=Sum("duration_minutes")))
            for r in rows:
                per_doctor.setdefault(r["patient_id"], []).append({
                    "doctor_id": r["doctor_id"],
                    "doctor": r["doctor__user__username"],
                    "minutes": r["minutes"],
                })

            for p in patients:
                row = totals.get(p.id, {})
                total = row.get("total") or 0
                item = {
                    "patient_id": p.id,
                    "patient": p.user.get_full_name() or p.user.username,
                    "program": prog,
                    "month": start.strftime("%Y-%m"),
                    "total_minutes": total,
                    "target_minutes": target,
                    "remaining_minutes": max(target - total, 0),
                    "compliant": total >= target,
                    "sessions": row.get("count", 0),
                    "doctors": per_doctor.get(p.id, []),
                }

                
                if prog == "RPM" and item["compliant"]:
                    c = ccm_totals.get(p.id, {})
                    own = c.get("total") or 0
                    extra = max(total - target, 0) 
                    c_total = own + extra
                    item["ccm"] = {
                        "enrolled": p.is_ccm,
                        "own_minutes": own,                   
                        "carried_over_from_rpm": extra,       
                        "total_minutes": c_total,
                        "target_minutes": ccm_target,
                        "remaining_minutes": max(ccm_target - c_total, 0),
                        "compliant": c_total >= ccm_target,
                        "sessions": c.get("count", 0),
                    }

                results.append(item)

        return Response(results)