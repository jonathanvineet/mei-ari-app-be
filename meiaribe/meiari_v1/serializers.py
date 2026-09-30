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
    bio_data = MeiAriUserBioDataSerializer(source='meiariuserbiodata', write_only=True)

    class Meta:
        model = MeiAriUser
        fields = [
            'cug_phone_number', 'cug_email_address', 'password',
            'role', 'bio_data', 'dept_id', 'sub_dept_id', 'sub_dept_office_id',
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def validate(self, attrs):
        dept = attrs.get('dept_id')
        sub_dept = attrs.get('sub_dept_id')
        if dept and sub_dept and sub_dept.department_id != dept.id:
            raise serializers.ValidationError({'sub_dept_id': 'Sub department does not belong to the selected department.'})
        office = attrs.get('sub_dept_office_id')
        if office and sub_dept and office.sub_dept_id != sub_dept.id:
            raise serializers.ValidationError({'sub_dept_office_id': 'Office does not belong to the selected sub department.'})
        return attrs

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
        fields = ['id', 'department', 'sub_department_name']
        
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
        fields = ['id', 'user_id', 'role_name', 'joined_at', 'name', 'email', 'role']

    def _user(self, obj):
        cache = self.context.setdefault('users', {})
        if obj.user_id not in cache:
            cache[obj.user_id] = MeiAriUser.objects.filter(id=obj.user_id).prefetch_related('meiariuserbiodata_set').first()
        return cache[obj.user_id]

    def get_name(self, obj):
        user = self._user(obj)
        bio = user.meiariuserbiodata_set.first() if user else None
        return f"{bio.first_name} {bio.last_name}".strip() if bio else None

    def get_email(self, obj):
        user = self._user(obj)
        return user.cug_email_address if user else None

    def get_role(self, obj):
        user = self._user(obj)
        return user.role if user else None

    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
        
class WorkGroupTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroupTicket
        fields = ['id', 'ticket_code', 'work_group', 'ticket_title', 'ticket_description', 'ticket_status', 'ticket_priority', 'ticket_type', 'ticket_owner_id', 'created_at']
        read_only_fields = ['id', 'ticket_code', 'created_at']
        extra_kwargs = {'ticket_status': {'default': 'Created'}}
        
class WorkGroupTicketDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroupTicket
        fields = ['id', 'work_group', 'ticket_title', 'ticket_description', 'ticket_status', 'ticket_priority', 'ticket_type']
        
class ReportRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportRecord
        fields = '__all__'

class MeiAriUserListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    access_id = serializers.SerializerMethodField()

    class Meta:
        model = MeiAriUser
        fields = ['id', 'name', 'cug_email_address', 'cug_phone_number', 'role', 'access_id', 'sub_dept_office_id']

    def _bio(self, obj):
        return obj.meiariuserbiodata_set.first()

    def get_name(self, obj):
        bio = self._bio(obj)
        return f"{bio.first_name} {bio.last_name}".strip() if bio else None

    def get_access_id(self, obj):
        bio = self._bio(obj)
        return bio.access_id if bio else None
