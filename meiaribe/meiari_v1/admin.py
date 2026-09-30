from django.contrib import admin

from .models import (
    MeiAriUser, MeiAriUserBioData, OTPTable, ReportRecord, SubDeptDetails, SubDeptOfficeDetails,
    TNGovtDept, TNGovtDeptContact, TNGovtSubDept, WorkGroup, WorkGroupDetails, WorkGroupMember,
    WorkGroupTicket,
)

# Register your models here.
for model in (
    MeiAriUser, MeiAriUserBioData, OTPTable, ReportRecord, SubDeptDetails, SubDeptOfficeDetails,
    TNGovtDept, TNGovtDeptContact, TNGovtSubDept, WorkGroup, WorkGroupDetails, WorkGroupMember,
    WorkGroupTicket,
):
    admin.site.register(model)
