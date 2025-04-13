from rest_framework import serializers
from .models import MeiAriUser, MeiAriUserBioData, ReportRecord, SubDeptDetails, SubDeptOfficeDetails, TNGovtDept, TNGovtDeptContact, TNGovtSubDept, WorkGroup, WorkGroupDetails, WorkGroupMember, WorkGroupTicket

class MeiAriUserBioDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeiAriUserBioData
        fields = [
            'user_name', 'active', 'first_name', 'last_name',
            'date_of_birth', 'alternative_email_address'
        ]

class MeiAriUserSerializer(serializers.ModelSerializer):
    bio_data = MeiAriUserBioDataSerializer(source='meiariuserbiodata', read_only=False)

    class Meta:
        model = MeiAriUser
        fields = [
            'cug_phone_number', 'cug_email_address', 'password',
            'role', 'bio_data', 'dept_id', 'sub_dept_id', 'sub_dept_office_id',
        ]

    def create(self, validated_data):
        bio_data = validated_data.pop('meiariuserbiodata')
        user = MeiAriUser.objects.create(**validated_data)
        MeiAriUserBioData.objects.create(user=user, **bio_data)
        return user

    def update(self, instance, validated_data):
        bio_data = validated_data.pop('meiariuserbiodata', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if bio_data:
            bio_instance = instance.meiariuserbiodata
            for attr, value in bio_data.items():
                setattr(bio_instance, attr, value)
            bio_instance.save()

        return instance
    
class OTPVerifySerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    otp = serializers.CharField(max_length=4)
    

class TNGovtDeptSerializer(serializers.ModelSerializer):
    class Meta:
        model = TNGovtDept
        fields = ['department_name', 'level']
        
class TNGovtDeptDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TNGovtDept
        fields = ['id', 'department_name', 'level']
        
class TNGovtDeptContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = TNGovtDeptContact
        fields = ['department_id', 'cug_minister_email', 'cug_minister_phone_number', 'minister_name', 
                  'stg_email', 'stg_phone_number', 'stg_name']
        
class TNGovtDeptContactDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TNGovtDeptContact
        fields = ['id', 'department_id', 'cug_minister_email', 'cug_minister_phone_number', 'minister_name', 
                  'stg_email', 'stg_phone_number', 'stg_name']
        
class TNGovtSubDeptSerializer(serializers.ModelSerializer):
    class Meta:
        model = TNGovtSubDept
        fields = ['department', 'sub_department_name']
        
class TNGovtSubDeptDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TNGovtSubDept
        fields = ['id', 'sub_department_name']
        
class SubDeptDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubDeptDetails
        fields = ['sub_dept', 'sub_dept_office', 'sub_dept_hod', 'sub_dept_cug_email', 'sub_dept_cug_phone_number']
        
class SubDeptDetailsDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubDeptDetails
        fields = ['id', 'sub_dept', 'sub_dept_office', 'sub_dept_hod', 'sub_dept_cug_email', 'sub_dept_cug_phone_number']
        
class SubDeptOfficeDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubDeptOfficeDetails
        fields = ['sub_dept', 'sub_dept_office_location', 'sub_dept_street_address', 'sub_dept_district', 'sub_dept_taluk', 'sub_dept_access_code']
        
class SubDeptOfficeDetailsDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubDeptOfficeDetails
        fields = ['id', 'sub_dept', 'sub_dept_office_location', 'sub_dept_street_address', 'sub_dept_district', 'sub_dept_taluk', 'sub_dept_access_code']
        
class WorkGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroup
        fields = [ 'sub_dept_office', 'group_name', 'is_active']
        
class WorkGroupDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroup
        fields = ['id', 'sub_dept_office', 'group_name', 'is_active']
        
class WorkGroupDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroupDetails
        fields = ['work_group', 'group_description']
        
class WorkGroupDetailsDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroupDetails
        fields = ['id', 'work_group', 'group_description']
        
class WorkGroupMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroupMember
        fields = ['work_group', 'user_id', 'role_name']
        
class WorkGroupMemberDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroupMember
        fields = ['id', 'work_group', 'user_id', 'role_name']
        
class WorkGroupMemberListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroupMember
        fields = ['user_id', 'role_name', 'joined_at']
        
class WorkGroupTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroupTicket
        fields = ['work_group', 'ticket_title', 'ticket_description', 'ticket_status', 'ticket_priority', 'ticket_type', 'ticket_owner_id']
        
class WorkGroupTicketDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroupTicket
        fields = ['id', 'work_group', 'ticket_title', 'ticket_description', 'ticket_status', 'ticket_priority', 'ticket_type']
        
class ReportRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportRecord
        fields = ['city', 'latitude', 'longitude', 'department_name', 'sub_department_name', 'sub_dept_office_name', 'access_id', 'file_path', 'ticket_status_type']
        
class ReportRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportRecord
        fields = '__all__'