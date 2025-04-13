from django.urls import path
from .views import ( AppCheckAPIView, DownloadReportAPIView, GeminiReportResponse, MeiAriUserCreateAPIView, ReportBySubDeptOfficeAPIView, SignInAPIView, OTPVerifyAPIView, TNGovtDeptAPIView, TNGovtDeptContactAPIView,
                    TNGovtSubDeptAPIView, SubDeptDetailsAPIView, SubDeptOfficeDetailsAPIView, UpdateTicketStatusAPIView, WorkGroupAPIView, WorkGroupDetailAPIView, WorkGroupListBySubDeptAPIView,
                    WorkGroupMembersAPIView, WorkGroupMembersListAPIView, WorkGroupTicketAPIView, WorkGroupTicketStatusCountAPIView, CreateWorkGroupWithDetailsAPIView,
                    GenerateAndUploadReport) 

urlpatterns = [
    path('check/', AppCheckAPIView.as_view(), name = 'geminiapp-check'),
    path('create-meiari-user/', MeiAriUserCreateAPIView.as_view(), name='create-meiari-user'),
    path("verify-otp/", OTPVerifyAPIView.as_view(), name="verify-otp"),
    path("signin/", SignInAPIView.as_view(), name="signin"),
    path("tngovtdept/", TNGovtDeptAPIView.as_view(), name="tngovtdept"),
    path("tngovtdept-contact/", TNGovtDeptContactAPIView.as_view(), name="tngovtdept-contact"),
    path("tngovtsubdept/", TNGovtSubDeptAPIView.as_view(), name="tngovtsubdept"),
    path("subdeptdetails/", SubDeptDetailsAPIView.as_view(), name="subdeptdetails"),
    path("subdeptofficedetails/", SubDeptOfficeDetailsAPIView.as_view(), name="subdeptofficedetails"),
    path("workgroup/", WorkGroupAPIView.as_view(), name="workgroup"),
    path("workgroupdetails/", WorkGroupDetailAPIView.as_view(), name="workgroup-detail"),
    path("workgroupmembers/", WorkGroupMembersAPIView.as_view(), name="workgroup-members"),
    path('workgroup/<uuid:work_group_id>/members/', WorkGroupMembersListAPIView.as_view(), name='workgroup-members'),
    path("workgroupticket/", WorkGroupTicketAPIView.as_view(), name="workgroup-ticket"),
    path('workgroupticket/<uuid:ticket_id>/', WorkGroupTicketAPIView.as_view(), name='get-workgroup-ticket'),  # For GET (retrieve)
    path('workgroup/<uuid:work_group_id>/ticket-status-count/', WorkGroupTicketStatusCountAPIView.as_view(), name='ticket-status-count'),
    path('create-workgroup-with-details/', CreateWorkGroupWithDetailsAPIView.as_view(), name='create-workgroup-with-details'),
    path('workgroups/', WorkGroupListBySubDeptAPIView.as_view(), name='workgroup-list-by-subdept'),
    path('generate-and-upload-report/', GenerateAndUploadReport.as_view(), name = 'generate-and-upload-report'),
    path('gemini-report-response/', GeminiReportResponse.as_view(), name = 'gemini-report-response'),
    path('report-records/<uuid:sub_dept_office_id>/', ReportBySubDeptOfficeAPIView.as_view(), name='report-by-sub-dept'),
    path("update-status/<uuid:id>/", UpdateTicketStatusAPIView.as_view(), name="update-ticket-status"),
    path("download-report/<uuid:id>/", DownloadReportAPIView.as_view(), name="download-report"),

]