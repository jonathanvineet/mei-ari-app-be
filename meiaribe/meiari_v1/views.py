import json
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import MeiAriUserListSerializer, MeiAriUserSerializer, OTPVerifySerializer, ReportRecordSerializer, SubDeptDetailsDetailSerializer, SubDeptDetailsSerializer, SubDeptOfficeDetailsDetailSerializer, SubDeptOfficeDetailsSerializer, TNGovtDeptContactDetailSerializer, TNGovtDeptContactSerializer, TNGovtDeptDetailSerializer, TNGovtDeptSerializer, TNGovtSubDeptDetailSerializer, TNGovtSubDeptSerializer, WorkGroupDetailSerializer, WorkGroupDetailsDetailSerializer, WorkGroupDetailsSerializer, WorkGroupMemberDetailSerializer, WorkGroupMemberListSerializer, WorkGroupMemberSerializer, WorkGroupSerializer, WorkGroupTicketSerializer
from .models import MeiAriUser, MeiAriUserBioData, OTPTable, ReportRecord, SubDeptDetails, SubDeptOfficeDetails, TNGovtDept, TNGovtDeptContact, TNGovtSubDept, WorkGroup, WorkGroupDetails, WorkGroupMember, WorkGroupTicket
from .methods import encrypt_password, EmailService, generate_filename, get_gemini_response, users_encode_token, ReportStorage
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from rest_framework.parsers import JSONParser
from datetime import timedelta
import traceback

OTP_VALIDITY = timedelta(minutes=10)


def send_otp_safely(user):
    """Send an OTP email; report failure instead of raising so callers can respond cleanly."""
    try:
        EmailService().send_otp_email(user)
        return True
    except Exception:
        traceback.print_exc()
        return False


def build_report_prompt(json_data):
    return (
        "You are writing an official inspection report for a Tamil Nadu government Inspection Cell. "
        "Use only the facts in the data below; do not invent names, numbers or findings. "
        "Write in clear, formal English using Markdown with these sections: "
        "a one-line title (# heading), Summary, Details of inspection (office, location, date, inspector), "
        "Observations, Issues found (with severity), Recommended actions (with who should act), and Conclusion. "
        "If a section has no information, say so briefly.\n\n"
        f"Inspection data (JSON):\n{json.dumps(json_data, indent=2)}"
    )

# Create your views here.
class AppCheckAPIView(APIView):
    """
    API view to check the health of the app.
    """
    def get(self, request, *args, **kwargs):
        """
        Handle GET requests to check the health of the app.
        """
        # Perform any necessary checks here
        # For example, check database connectivity, external services, etc.

        # Return a success response
        return Response({"status": "ok"}, status=status.HTTP_200_OK)    
    
class MeiAriUserCreateAPIView(APIView):
    def post(self, request):
        data = request.data.copy()
        raw_password = data.get('password')
        if not raw_password:
            return Response({'error': {'password': ['This field is required.']}}, status=status.HTTP_400_BAD_REQUEST)
        data['password'] = encrypt_password(raw_password)
        serializer = MeiAriUserSerializer(data=data)
        if serializer.is_valid():
            with transaction.atomic():
                user = serializer.save()
            otp_sent = send_otp_safely(user)
            message = "User created. OTP sent to email." if otp_sent else "User created, but the OTP email could not be sent. Use resend-otp."
            return Response({'data': { 'user_id' : user.id, 'otp_sent': otp_sent }, 'message': message}, status=status.HTTP_201_CREATED)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class OTPVerifyAPIView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = OTPVerifySerializer(data=request.data)

        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            otp = serializer.validated_data['otp']

            # Get the OTP record for the user
            otp_record = OTPTable.objects.filter(user_id=user_id, otp=otp).order_by('-created_at').first()
            if not otp_record:
                return Response({'error': "That code doesn't match. Check the email or send a new code."}, status=status.HTTP_400_BAD_REQUEST)
            if timezone.now() - otp_record.created_at > OTP_VALIDITY:
                otp_record.delete()
                return Response({'error': "OTP has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            # Get the user's bio data to retrieve the access_id
            user_bio_data = get_object_or_404(MeiAriUserBioData, user_id=user_id)

            # Delete the OTP record as it's now used
            otp_record.delete()
            
            return Response({'data': {'access_id': user_bio_data.access_id}, 'message': "OTP verified successfully"}, status=status.HTTP_200_OK)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class ResendOTPAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')
        user_id = request.data.get('user_id')
        if not email and not user_id:
            return Response({'error': "email or user_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = MeiAriUser.objects.filter(**({'cug_email_address': email} if email else {'id': user_id})).first()
        except Exception:
            user = None
        if not user:
            return Response({'error': "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if not send_otp_safely(user):
            return Response({'error': "Could not send OTP email."}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'data': {'user_id': user.id}, 'message': "OTP sent to email."}, status=status.HTTP_200_OK)

class SignInAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return Response({"message": "email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the user exists and verify password (stored hashed)
            user = MeiAriUser.objects.filter(cug_email_address=email).first()
            if not user or user.password != encrypt_password(password):
                return Response({"message": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)

            # Retrieve user bio data to get `access_id`
            user_bio = MeiAriUserBioData.objects.filter(user=user).first()
            access_id = user_bio.access_id if user_bio else None
            if user_bio and not user_bio.active:
                return Response({"message": "User account is inactive"}, status=status.HTTP_403_FORBIDDEN)

            # Generate JWT token
            token = users_encode_token(str(user.id), user.role)
            refresh = RefreshToken.for_user(user)
            
            dept_name = user.dept_id.department_name if user and user.dept_id else None
            sub_dept_name = user.sub_dept_id.sub_department_name if user and user.sub_dept_id else None
            sub_dept_office_name = user.sub_dept_office_id.id if user and user.sub_dept_office_id else None

            return Response({
                "token": str(token),
                "access": str(refresh.access_token),
                "data": {
                    "user_id": str(user.id),
                    "email": user.cug_email_address,
                    "access_id": str(access_id) if access_id else None,
                    "is_active": user_bio.active if user_bio else None,
                    "role" : user.role,
                    "department_name": dept_name,
                    "sub_department_name": sub_dept_name,
                    "sub_dept_office_name": sub_dept_office_name,
                },
                "message": "User logged in successfully"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TNGovtDeptAPIView(APIView):
    def post (self, request):
        try:
            data = request.data
            tngovtdeptSerializer = TNGovtDeptSerializer(data=data)
            if tngovtdeptSerializer.is_valid():
                tngovtdeptSerializer.save()
                return Response({"message": "Department created successfully"}, status=status.HTTP_201_CREATED)
            return Response({"error": tngovtdeptSerializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def get(self, request):
        try:
            tngovtdept = TNGovtDept.objects.all()
            serializer = TNGovtDeptDetailSerializer(tngovtdept, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class TNGovtDeptContactAPIView(APIView):
    def post (self, request):
        try:
            data = request.data
            tngovtdeptSerializer = TNGovtDeptContactSerializer(data=data)
            if tngovtdeptSerializer.is_valid():
                tngovtdeptSerializer.save()
                return Response({"message": "Department created successfully"}, status=status.HTTP_201_CREATED)
            return Response({"error": tngovtdeptSerializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def get(self, request):
        try:
            tngovtdept = TNGovtDeptContact.objects.all()
            serializer = TNGovtDeptContactDetailSerializer(tngovtdept, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class TNGovtSubDeptAPIView(APIView):
    def post (self, request):
        try:
            data = request.data
            tngovtdeptSerializer = TNGovtSubDeptSerializer(data=data)
            if tngovtdeptSerializer.is_valid():
                tngovtdeptSerializer.save()
                return Response({"message": "Sub Department created successfully"}, status=status.HTTP_201_CREATED)
            return Response({"error": tngovtdeptSerializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            tngovtdept = TNGovtSubDept.objects.all()
            if request.query_params.get('department'):
                tngovtdept = tngovtdept.filter(department_id=request.query_params['department'])
            serializer = TNGovtSubDeptDetailSerializer(tngovtdept, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class SubDeptDetailsAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            sub_dept_serializer = SubDeptDetailsSerializer(data=data)
            if sub_dept_serializer.is_valid():
                sub_dept_serializer.save()
                return Response({"message": "Sub Department Details created successfully"}, status=status.HTTP_201_CREATED)
            return Response({"error": sub_dept_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            sub_dept_details = SubDeptDetails.objects.all()
            serializer = SubDeptDetailsDetailSerializer(sub_dept_details, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class SubDeptOfficeDetailsAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            sub_dept_office_serializer = SubDeptOfficeDetailsSerializer(data=data)
            if sub_dept_office_serializer.is_valid():
                sub_dept_office_serializer.save()
                return Response({"message": "Sub Department Office Details created successfully"}, status=status.HTTP_201_CREATED)
            return Response({"error": sub_dept_office_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            sub_dept_office_details = SubDeptOfficeDetails.objects.all()
            if request.query_params.get('sub_dept'):
                sub_dept_office_details = sub_dept_office_details.filter(sub_dept_id=request.query_params['sub_dept'])
            serializer = SubDeptOfficeDetailsDetailSerializer(sub_dept_office_details, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class WorkGroupAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            workgroup_serializer = WorkGroupSerializer(data=data)
            if workgroup_serializer.is_valid():
                workgroup_serializer.save()
                return Response({"message": "Work Group created successfully"}, status=status.HTTP_201_CREATED)
            return Response({"error": workgroup_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            workgroups = WorkGroup.objects.all()
            serializer = WorkGroupDetailSerializer(workgroups, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class WorkGroupDetailAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            workgroup_serializer = WorkGroupDetailsSerializer(data=data)
            if workgroup_serializer.is_valid():
                workgroup_serializer.save()
                return Response({"message": "Work Group created successfully"}, status=status.HTTP_201_CREATED)
            return Response({"error": workgroup_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def get(self, request):
        try:
            workgroups = WorkGroupDetails.objects.all()
            serializer = WorkGroupDetailsDetailSerializer(workgroups, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class WorkGroupMembersAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            workgroup_serializer = WorkGroupMemberSerializer(data=data)
            if workgroup_serializer.is_valid():
                workgroup_serializer.save()
                return Response({"message": "Group Member created successfully"}, status=status.HTTP_201_CREATED)
            return Response({"error": workgroup_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            workgroups = WorkGroupMember.objects.all()
            serializer = WorkGroupMemberDetailSerializer(workgroups, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class WorkGroupMembersListAPIView(APIView):
    def get(self, request, work_group_id):
        try:
            members = WorkGroupMember.objects.filter(work_group_id=work_group_id)
            serializer = WorkGroupMemberListSerializer(members, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except WorkGroupMember.DoesNotExist:
            return Response({"error": "WorkGroupMember not found"}, status=status.HTTP_404_NOT_FOUND)
        except WorkGroup.DoesNotExist:
            return Response({"error": "WorkGroup not found"}, status=status.HTTP_404_NOT_FOUND)
        
class WorkGroupTicketAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            workgroup_ticket_serializer = WorkGroupTicketSerializer(data=data)
            if workgroup_ticket_serializer.is_valid():
                workgroup_ticket_serializer.save()
                return Response({"message": "Work Group Ticket created successfully"}, status=status.HTTP_201_CREATED)
            return Response({"error": workgroup_ticket_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)       
        
    def get(self, request, ticket_id=None):
        """
        GET /workgroupticket/<ticket_id>/          -> that ticket
        GET /workgroupticket/<work_group_id>/      -> list of the work group's tickets
        GET /workgroupticket/?work_group=<id>      -> list of the work group's tickets
        """
        try:
            if ticket_id is not None:
                workgroup_ticket = WorkGroupTicket.objects.filter(id=ticket_id).first()
                if workgroup_ticket:
                    serializer = WorkGroupTicketSerializer(workgroup_ticket)
                    return Response({"data": serializer.data}, status=status.HTTP_200_OK)
                work_group_id = ticket_id
            else:
                work_group_id = request.query_params.get("work_group")

            tickets = WorkGroupTicket.objects.all()
            if work_group_id:
                if not WorkGroup.objects.filter(id=work_group_id).exists():
                    return Response({"error": "WorkGroupTicket not found"}, status=status.HTTP_404_NOT_FOUND)
                tickets = tickets.filter(work_group_id=work_group_id)
            serializer = WorkGroupTicketSerializer(tickets.order_by('-created_at'), many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, ticket_id=None):
        ticket = WorkGroupTicket.objects.filter(id=ticket_id).first() if ticket_id else None
        if not ticket:
            return Response({"error": "WorkGroupTicket not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = WorkGroupTicketSerializer(ticket, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"data": serializer.data, "message": "Ticket updated"}, status=status.HTTP_200_OK)
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
class WorkGroupTicketStatusCountAPIView(APIView):
    def get(self, request, work_group_id):
        try:
            # Optional: check if work_group exists
            work_group = WorkGroup.objects.get(id=work_group_id)
        except WorkGroup.DoesNotExist:
            return Response({"error": "WorkGroup not found."}, status=status.HTTP_404_NOT_FOUND)

        status_types = ["Created", "Completed", "Verified", "Signed"]

        # Initialize count dictionary
        ticket_counts = {status: 0 for status in status_types}

        # Get queryset for the given work group
        queryset = WorkGroupTicket.objects.filter(work_group=work_group)

        for status_type in status_types:
            ticket_counts[status_type] = queryset.filter(ticket_status=status_type).count()
        return Response({"data": ticket_counts}, status=status.HTTP_200_OK)
    
class CreateWorkGroupWithDetailsAPIView(APIView):
    def post(self, request, *args, **kwargs):
        # Serialize WorkGroup
        work_group_serializer = WorkGroupSerializer(data={
            "sub_dept_office": request.data.get("sub_dept_office"),
            "group_name": request.data.get("group_name"),
            "is_active": request.data.get("is_active", True)
        })
        if work_group_serializer.is_valid():
            work_group = work_group_serializer.save()
            # Serialize WorkGroupDetails
            work_group_details_serializer = WorkGroupDetailsSerializer(data={
                "work_group": work_group.id,
                "group_description": request.data.get("group_description"),
            })

            if work_group_details_serializer.is_valid():
                work_group_details_serializer.save()
                return Response({'data': work_group_details_serializer.data, 'message': "WorkGroup and WorkGroupDetails created successfully"}, status=status.HTTP_201_CREATED)

            # Clean up WorkGroup if details creation fails
            work_group.delete()
            return Response({"error": work_group_details_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        # If WorkGroup serialization fails})

        return Response({"error": work_group_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class WorkGroupListBySubDeptAPIView(APIView):
    def get(self, request, *args, **kwargs):
        sub_dept_office_id = request.query_params.get('sub_dept_office')

        if not sub_dept_office_id:
            return Response({"error": "sub_dept_office parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Get all work groups for that sub_dept_office
        work_groups = WorkGroup.objects.filter(sub_dept_office=sub_dept_office_id, is_active=True)
        
        response_data = []

        for group in work_groups:
            try:
                details = WorkGroupDetails.objects.get(work_group=group)
                response_data.append({
                    "id": group.id,
                    "group_name": group.group_name,
                    "group_description": details.group_description
                })
            except WorkGroupDetails.DoesNotExist:
                continue  # Skip groups with no details

        return Response({"data": response_data}, status=status.HTTP_200_OK)


class GenerateAndUploadReport(APIView):
    parser_classes = [JSONParser]
    required_fields = ["location", "departmentName", "subDepartmentName", "accessId", "subDeptOfficeName"]

    def post(self, request):
        try:
            gemini_payload = request.data
            missing = [field for field in self.required_fields if field not in gemini_payload]
            location = gemini_payload.get("location")
            if not isinstance(location, dict) or not all(k in location for k in ("city", "latitude", "longitude")):
                missing.append("location.city/latitude/longitude")
            if missing:
                return Response({"error": f"Missing fields: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)

            department_name = gemini_payload["departmentName"]
            sub_department_name = gemini_payload["subDepartmentName"]
            access_id = gemini_payload["accessId"]
            
            sub_dept_office_id = gemini_payload["subDeptOfficeName"]
            sub_dept_office_instance = SubDeptOfficeDetails.objects.filter(id=sub_dept_office_id).first()
            if not sub_dept_office_instance:
                return Response({"error": "SubDeptOfficeDetails not found."}, status=status.HTTP_404_NOT_FOUND)

            # Step 1: Generate the report with Gemini
            summary_report_text = get_gemini_response(build_report_prompt(gemini_payload))
            if not summary_report_text:
                return Response(
                    {"error": "Generated report is empty."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Step 2: Upload report to S3 (or local storage when S3 is not configured)
            file_name = generate_filename("generated_report")
            file_path = f"{settings.REPORTS_FOLDER}/{department_name}/{sub_department_name}/{sub_dept_office_id}/{file_name}.txt"
            ReportStorage().save(file_path, summary_report_text)

            # Step 3: Save to DB
            report = ReportRecord.objects.create(
                city=location["city"],
                latitude=location["latitude"],
                longitude=location["longitude"],
                department_name=department_name,
                sub_department_name=sub_department_name,
                sub_dept_office_name=sub_dept_office_instance,
                access_id=access_id,
                file_path=file_path,
                ticket_status_type="Created"  # Initial status
            )

            return Response(
                {"message": f"Report successfully generated, uploaded, and saved to DB.", "report_id": report.id,
                 "data": {"report_id": report.id, "summary_report": summary_report_text}},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            traceback.print_exc()
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class GeminiReportResponse(APIView):
    parser_classes = [JSONParser] 
    def post(self, request):
        try:
            json_data = request.data
            
            if not json_data:
                return Response({"error": "Empty JSON payload"}, status=status.HTTP_400_BAD_REQUEST)

            summary_report = get_gemini_response(build_report_prompt(json_data))

            return Response({"data":{"summary_report": summary_report}}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
        
class ReportBySubDeptOfficeAPIView(APIView):
    def get(self, request, sub_dept_office_id):
        try:
            sub_dept_office = SubDeptOfficeDetails.objects.get(id=sub_dept_office_id)
        except SubDeptOfficeDetails.DoesNotExist:
            return Response({"error": "SubDeptOfficeDetails not found."}, status=status.HTTP_404_NOT_FOUND)
        
        records = ReportRecord.objects.filter(sub_dept_office_name=sub_dept_office)
        serializer = ReportRecordSerializer(records, many=True)
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)
    
class UpdateTicketStatusAPIView(APIView):
    def get(self, request, id):
        new_status = request.query_params.get("status")
        allowed_statuses = [choice[0] for choice in ReportRecord._meta.get_field("ticket_status_type").choices]

        if not new_status or new_status not in allowed_statuses:
            return Response(
                {"error": f"Invalid or missing status. Allowed values: {allowed_statuses}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            report = ReportRecord.objects.get(id=id)
        except ReportRecord.DoesNotExist:
            return Response({"error": "ReportRecord not found."}, status=status.HTTP_404_NOT_FOUND)

        report.ticket_status_type = new_status
        report.save()

        return Response(
            {"message": f"Ticket status updated to {new_status}"},
            status=status.HTTP_200_OK
        )
        
class DownloadReportAPIView(APIView):
    def get(self, request, id):
        try:
            report = ReportRecord.objects.get(id=id)
        except ReportRecord.DoesNotExist:
            return Response({"error": "ReportRecord not found."}, status=status.HTTP_404_NOT_FOUND)

        file_path = report.file_path  # Example: "samplefolder/xyz.txt"

        try:
            file_content = ReportStorage().read(file_path)

            response = HttpResponse(file_content, content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="{file_path.split("/")[-1]}"'
            return response

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MeiAriUserListAPIView(APIView):
    def get(self, request):
        users = MeiAriUser.objects.prefetch_related('meiariuserbiodata_set').order_by('created_at')
        if request.query_params.get('sub_dept_office'):
            users = users.filter(sub_dept_office_id=request.query_params['sub_dept_office'])
        return Response({"data": MeiAriUserListSerializer(users, many=True).data}, status=status.HTTP_200_OK)
