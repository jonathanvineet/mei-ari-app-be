from django.db import models
import uuid
from django.utils import timezone

# Create your models here.
class MeiAriUser(models.Model):
    types_of_roles = ['Inspection_Cell_Officer', 'Inspection_Cell_Head', 'Inspection_Cell_Admin']
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cug_phone_number = models.CharField(max_length=20)
    cug_email_address = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    access_list = models.TextField()
    role = models.CharField(max_length=50, choices=[(role, role) for role in types_of_roles])   
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    dept_id = models.ForeignKey('TNGovtDept', on_delete=models.CASCADE)
    sub_dept_id = models.ForeignKey('TNGovtSubDept', on_delete=models.CASCADE)
    sub_dept_office_id = models.ForeignKey('SubDeptOfficeDetails', on_delete=models.CASCADE)
    groups = models.ManyToManyField('WorkGroup', blank=True, related_name='users')

class MeiAriUserBioData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(MeiAriUser, on_delete=models.CASCADE)
    user_name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    alternative_email_address = models.EmailField()
    access_id = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def generate_access_id(self):
        """Generate an access_id using first 5 characters of first name + DOB (DDMM)."""
        name_part = (self.first_name[:5]).ljust(5, "X")  # Ensure at least 5 characters
        dob_part = self.date_of_birth.strftime("%d%m")  # Extract DDMM from DOB
        return f"{name_part}{dob_part}"

    def save(self, *args, **kwargs):
        """Automatically set access_id before saving the instance."""
        if not self.access_id:  # Generate only if not already set
            self.access_id = self.generate_access_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.access_id}"
    
class OTPTable(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('MeiAriUser', on_delete=models.CASCADE)
    otp = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"OTP {self.otp} for {self.user.email}"
    
    
class TNGovtDept(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department_name = models.CharField(max_length=255)
    level = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

class TNGovtDeptContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department_id = models.ForeignKey(TNGovtDept, on_delete=models.CASCADE)
    cug_minister_email = models.EmailField()
    cug_minister_phone_number = models.CharField(max_length=20)
    minister_name = models.CharField(max_length=255)
    stg_email = models.EmailField()
    stg_phone_number = models.CharField(max_length=20)
    stg_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    
class TNGovtSubDept(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(TNGovtDept, on_delete=models.CASCADE)
    sub_department_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

class SubDeptDetails(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_dept = models.ForeignKey(TNGovtSubDept, on_delete=models.CASCADE)
    sub_dept_office = models.CharField(max_length=255)
    sub_dept_hod = models.CharField(max_length=255)
    sub_dept_cug_email = models.EmailField()
    sub_dept_cug_phone_number = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

class SubDeptOfficeDetails(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_dept = models.ForeignKey(TNGovtSubDept, on_delete=models.CASCADE)
    sub_dept_office_location = models.CharField(max_length=255)
    sub_dept_street_address = models.TextField()
    sub_dept_district = models.CharField(max_length=255)
    sub_dept_taluk = models.CharField(max_length=255)
    sub_dept_access_code = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
class WorkGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_dept_office = models.ForeignKey(SubDeptOfficeDetails, on_delete=models.CASCADE)
    group_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

class WorkGroupDetails(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_group = models.ForeignKey(WorkGroup, on_delete=models.CASCADE)
    group_description = models.TextField()
    group_photo = models.ImageField(upload_to='group_photos/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
class WorkGroupMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_group = models.ForeignKey(WorkGroup, on_delete=models.CASCADE)
    user_id = models.UUIDField()
    role_name = models.CharField(max_length=100)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

class WorkGroupTicket(models.Model):
    type_of_tickets = ["CustomTemplate", "PreBuiltTemplate", "TaskAssign"]
    ticket_status_type = ["Created", "Completed", "Verified", "Signed"]
    ticket_priority_type = ["High", "Medium", "Low"]
    work_group = models.ForeignKey(WorkGroup, on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_code = models.CharField(max_length=100, unique=True)
    ticket_title = models.CharField(max_length=255)
    ticket_description = models.TextField()
    ticket_status = models.CharField(max_length=50,choices=[(status, status) for status in ticket_status_type])
    ticket_type = models.CharField(max_length=50, choices=[(type, type) for type in type_of_tickets])
    ticket_priority = models.CharField(max_length=50,choices=[(priority, priority) for priority in ticket_priority_type])
    ticket_owner_id = models.ForeignKey(MeiAriUser, on_delete=models.CASCADE, null=True, blank=True)
    user_id = models.ManyToManyField(MeiAriUser, blank=True, related_name='tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    
    
TICKET_STATUS_CHOICES = [
    ("Created", "Created"),
    ("Completed", "Completed"),
    ("Verified", "Verified"),
    ("Signed", "Signed"),
]

class ReportRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    department_name = models.CharField(max_length=255)
    sub_department_name = models.CharField(max_length=255)
    sub_dept_office_name = models.ForeignKey('SubDeptOfficeDetails', on_delete=models.CASCADE)  
    access_id = models.CharField(max_length=50)
    file_path = models.CharField(max_length=500)
    ticket_status_type = models.CharField(max_length=20, choices=TICKET_STATUS_CHOICES, default="Created")
    created_at = models.DateTimeField(auto_now_add=True)