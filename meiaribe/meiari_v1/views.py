import json
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import MeiAriUserSerializer, OTPVerifySerializer, ReportRecordSerializer, SubDeptDetailsDetailSerializer, SubDeptDetailsSerializer, SubDeptOfficeDetailsDetailSerializer, SubDeptOfficeDetailsSerializer, TNGovtDeptContactDetailSerializer, TNGovtDeptContactSerializer, TNGovtDeptDetailSerializer, TNGovtDeptSerializer, TNGovtSubDeptDetailSerializer, TNGovtSubDeptSerializer, WorkGroupDetailSerializer, WorkGroupDetailsDetailSerializer, WorkGroupDetailsSerializer, WorkGroupMemberDetailSerializer, WorkGroupMemberListSerializer, WorkGroupMemberSerializer, WorkGroupSerializer, WorkGroupTicketSerializer
from .models import MeiAriUser, MeiAriUserBioData, OTPTable, ReportRecord, SubDeptDetails, SubDeptOfficeDetails, TNGovtDept, TNGovtDeptContact, TNGovtSubDept, WorkGroup, WorkGroupDetails, WorkGroupMember, WorkGroupTicket
from .methods import encrypt_password, EmailService, generate_filename, get_gemini_response, users_encode_token, decode_token
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
import requests
import boto3
from datetime import datetime
import traceback

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
        serializer = MeiAriUserSerializer(data=request.data)
        raw_password = request.data.get('password')
        encrypted_password = encrypt_password(raw_password)
        request.data['password'] = encrypted_password
        if serializer.is_valid():
            user = serializer.save()
            # email_service = EmailService()
            # email_service.send_otp_email(user)
            return Response({'data': { 'user_id' : user.id }, 'message':""}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class OTPVerifyAPIView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = OTPVerifySerializer(data=request.data)

        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            otp = serializer.validated_data['otp']

            # Get the OTP record for the user
            otp_record = get_object_or_404(OTPTable, user_id=user_id, otp=otp)

            # Get the user's bio data to retrieve the access_id
            user_bio_data = get_object_or_404(MeiAriUserBioData, user_id=user_id)

            # Delete the OTP record as it's now used
            otp_record.delete()
            
            return Response({'data': {'access_id': user_bio_data.access_id}, 'message': "OTP verified successfully"}, status=status.HTTP_200_OK)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
class SignInAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            email = data.get("email")
            password = data.get("password")

            # Check if the user exists
            user = get_object_or_404(MeiAriUser, cug_email_address=email)
            print("User found:", user)
            # Verify password (assuming it's hashed)
            if user.password != encrypt_password(password):
                print(user.password, encrypt_password(password))
                return Response({"message": "Invalid password"}, status=status.HTTP_401_UNAUTHORIZED)
            print("User password verified successfully")
            # Generate JWT token
            token = users_encode_token(user.cug_phone_number, user.role)
            refresh = RefreshToken.for_user(user)
            print("Token:", token)
            print("Refresh Token:", refresh.access_token)
            # Retrieve user bio data to get `access_id`
            user_bio = MeiAriUserBioData.objects.filter(user=user).first()
            access_id = user_bio.access_id if user_bio else None
            print("Access ID:", access_id)
            
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
        
    def get(self, request, ticket_id):
        try:
            workgroup_ticket = WorkGroupTicket.objects.get(work_group=ticket_id)
            print("Ticket found:", workgroup_ticket)
            serializer = WorkGroupTicketSerializer(workgroup_ticket)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except WorkGroupTicket.DoesNotExist:
            return Response({"error": "WorkGroupTicket not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
        print("Queryset:", queryset)

        for status_type in status_types:
            ticket_counts[status_type] = queryset.filter(ticket_status=status_type).count()
        print("Ticket counts:", ticket_counts)
        return Response({"data": ticket_counts}, status=status.HTTP_200_OK)
    
class CreateWorkGroupWithDetailsAPIView(APIView):
    def post(self, request, *args, **kwargs):
        # Serialize WorkGroup
        work_group_serializer = WorkGroupSerializer(data={
            "sub_dept_office": request.data.get("sub_dept_office"),
            "group_name": request.data.get("group_name"),
            "is_active": request.data.get("is_active", True)
        })
        print("WorkGroup data:", work_group_serializer.initial_data)
        if work_group_serializer.is_valid():
            work_group = work_group_serializer.save()
            print("WorkGroup created:", work_group)
            # Serialize WorkGroupDetails
            work_group_details_serializer = WorkGroupDetailsSerializer(data={
                "work_group": work_group.id,
                "group_description": request.data.get("group_description"),
                # "group_photo": request.FILES.get("group_photo")
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
                    "group_name": group.group_name,
                    "group_description": details.group_description
                })
            except WorkGroupDetails.DoesNotExist:
                continue  # Skip groups with no details

        return Response({"data": response_data}, status=status.HTTP_200_OK)


class GenerateAndUploadReport(APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        print("Request Data:", request.data)
        try:
            # Step 1: Call GeminiReportResponse API
            gemini_url = "http://192.168.107.231:8000/api/v1/gemini-report-response/"
            gemini_payload = request.data

            gemini_response = requests.post(gemini_url, json=gemini_payload)

            if gemini_response.status_code != 200:
                return Response(
                    {"error": "Failed to generate report", "details": gemini_response.json()},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            summary_report_text = gemini_response.json().get("data", {}).get("summary_report", "")
            if not summary_report_text:
                return Response(
                    {"error": "Generated report is empty."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            location = gemini_payload["location"]
            department_name = gemini_payload["departmentName"]
            sub_department_name = gemini_payload["subDepartmentName"]
            access_id = gemini_payload["accessId"]
            
            sub_dept_office_id = gemini_payload["subDeptOfficeName"]
            try:
                sub_dept_office_instance = SubDeptOfficeDetails.objects.get(id=sub_dept_office_id)
            except SubDeptOfficeDetails.DoesNotExist:
                return Response({"error": "SubDeptOfficeDetails not found."}, status=404)

            # Step 2: Upload report to S3
            folder_name = "samplefolder"
            file_name = generate_filename("generated_report")
            file_path = f"{folder_name}/{department_name}/{sub_department_name}/{sub_dept_office_id}/{file_name}.txt"

            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )

            s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_path,
                Body=summary_report_text,
                ContentType="text/plain"
            )

            # ✅ Step 3: Save to DB
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
                {"message": f"Report successfully generated, uploaded, and saved to DB.", "report_id": report.id},
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
            
            # Debug: Log incoming request
            print("Received JSON:", json.dumps(json_data, indent=2))

            if not json_data:
                return Response({"error": "Empty JSON payload"}, status=status.HTTP_400_BAD_REQUEST)

            prompt = f"Create a Detailed report using the content: {json.dumps(json_data)}"
            summary_report = get_gemini_response(prompt)

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
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )

            s3_object = s3_client.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file_path)
            file_content = s3_object['Body'].read().decode('utf-8')

            response = HttpResponse(file_content, content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="{file_path.split("/")[-1]}"'
            return response

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
