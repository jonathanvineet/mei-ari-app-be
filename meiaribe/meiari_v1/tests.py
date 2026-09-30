import tempfile
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .authentication import UserTokenAuthentication
from .models import OTPTable, ReportRecord, WorkGroupTicket


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    AWS_STORAGE_BUCKET_NAME='',
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class FullFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def post(self, url, data):
        return self.client.post(f'/api/v1/{url}', data, format='json')

    def get(self, url):
        return self.client.get(f'/api/v1/{url}')

    def create_org(self):
        self.assertEqual(self.post('tngovtdept/', {'department_name': 'Health', 'level': 'State'}).status_code, 201)
        dept_id = self.get('tngovtdept/').data['data'][0]['id']
        self.assertEqual(self.post('tngovtsubdept/', {'department': dept_id, 'sub_department_name': 'Hospitals'}).status_code, 201)
        sub_dept_id = self.get('tngovtsubdept/').data['data'][0]['id']
        self.assertEqual(self.post('subdeptofficedetails/', {
            'sub_dept': sub_dept_id, 'sub_dept_office_location': 'Chennai', 'sub_dept_street_address': '1 Main Rd',
            'sub_dept_district': 'Chennai', 'sub_dept_taluk': 'Egmore', 'sub_dept_access_code': 'CHN001',
        }).status_code, 201)
        office_id = self.get('subdeptofficedetails/').data['data'][0]['id']
        return dept_id, sub_dept_id, office_id

    def create_user(self, dept_id, sub_dept_id, office_id, email='officer@tn.gov.in', first_name='Kavitha'):
        return self.post('create-meiari-user/', {
            'cug_phone_number': '9999999999', 'cug_email_address': email, 'password': 'secret123',
            'role': 'Inspection_Cell_Officer', 'dept_id': dept_id, 'sub_dept_id': sub_dept_id,
            'sub_dept_office_id': office_id,
            'bio_data': {'user_name': 'kavi', 'first_name': first_name, 'last_name': 'R',
                         'date_of_birth': '1990-05-17', 'alternative_email_address': 'k@example.com'},
        })

    @mock.patch('meiari_v1.views.get_gemini_response', return_value='Inspection report text')
    def test_full_flow(self, _gemini):
        dept_id, sub_dept_id, office_id = self.create_org()

        # Sign up -> OTP email
        res = self.create_user(dept_id, sub_dept_id, office_id)
        self.assertEqual(res.status_code, 201, res.data)
        user_id = str(res.data['data']['user_id'])
        self.assertTrue(res.data['data']['otp_sent'])
        self.assertEqual(len(mail.outbox), 1)
        otp = OTPTable.objects.get(user_id=user_id).otp
        self.assertIn(otp, mail.outbox[0].body)

        # Verify OTP
        self.assertEqual(self.post('verify-otp/', {'user_id': user_id, 'otp': '0000' if otp != '0000' else '1111'}).status_code, 400)
        res = self.post('verify-otp/', {'user_id': user_id, 'otp': otp})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['data']['access_id'], 'Kavit1705')

        # Sign in
        self.assertEqual(self.post('signin/', {'email': 'officer@tn.gov.in', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.post('signin/', {'email': 'nobody@tn.gov.in', 'password': 'x'}).status_code, 401)
        res = self.post('signin/', {'email': 'officer@tn.gov.in', 'password': 'secret123'})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(str(res.data['data']['sub_dept_office_name']), office_id)
        request = mock.Mock(headers={'Authorization': f"Bearer {res.data['token']}"})
        user, _ = UserTokenAuthentication().authenticate(request)
        self.assertEqual(str(user.id), user_id)

        # Work groups, members, tickets
        res = self.post('create-workgroup-with-details/', {'sub_dept_office': office_id, 'group_name': 'Team A', 'group_description': 'Desc'})
        self.assertEqual(res.status_code, 201, res.data)
        group_id = str(res.data['data']['work_group'])
        self.assertEqual(self.client.get('/api/v1/workgroups/', {'sub_dept_office': office_id}).data['data'][0]['group_name'], 'Team A')
        self.assertEqual(self.post('workgroupmembers/', {'work_group': group_id, 'user_id': user_id, 'role_name': 'Lead'}).status_code, 201)
        self.assertEqual(len(self.get(f'workgroup/{group_id}/members/').data['data']), 1)

        for title in ('T1', 'T2'):
            res = self.post('workgroupticket/', {'work_group': group_id, 'ticket_title': title, 'ticket_description': 'd',
                                                 'ticket_priority': 'High', 'ticket_type': 'TaskAssign', 'ticket_owner_id': user_id})
            self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(WorkGroupTicket.objects.values('ticket_code').distinct().count(), 2)
        ticket = WorkGroupTicket.objects.first()
        self.assertEqual(self.get(f'workgroupticket/{ticket.id}/').data['data']['ticket_title'], ticket.ticket_title)
        self.assertEqual(len(self.get(f'workgroupticket/{group_id}/').data['data']), 2)
        self.assertEqual(self.get(f'workgroup/{group_id}/ticket-status-count/').data['data']['Created'], 2)

        # Report: generate -> list -> update status -> download
        res = self.post('generate-and-upload-report/', {
            'location': {'city': 'Chennai', 'latitude': 13.08, 'longitude': 80.27},
            'departmentName': 'Health', 'subDepartmentName': 'Hospitals', 'accessId': 'Kavit1705',
            'subDeptOfficeName': office_id, 'findings': 'Clean wards',
        })
        self.assertEqual(res.status_code, 201, res.data)
        report_id = res.data['report_id']
        self.assertEqual(len(self.get(f'report-records/{office_id}/').data['data']), 1)
        self.assertEqual(self.get(f'update-status/{report_id}/?status=Verified').status_code, 200)
        self.assertEqual(ReportRecord.objects.get(id=report_id).ticket_status_type, 'Verified')
        res = self.get(f'download-report/{report_id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content.decode(), 'Inspection report text')

    def test_duplicate_access_id_and_resend_otp(self):
        dept_id, sub_dept_id, office_id = self.create_org()
        self.assertEqual(self.create_user(dept_id, sub_dept_id, office_id, 'a@tn.gov.in').status_code, 201)
        res = self.create_user(dept_id, sub_dept_id, office_id, 'b@tn.gov.in')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(self.create_user(dept_id, sub_dept_id, office_id, 'b@tn.gov.in').status_code, 400)

        res = self.post('resend-otp/', {'email': 'b@tn.gov.in'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(OTPTable.objects.filter(user__cug_email_address='b@tn.gov.in').count(), 1)

    def test_report_missing_fields(self):
        self.assertEqual(self.post('generate-and-upload-report/', {'departmentName': 'Health'}).status_code, 400)


class UiSupportTests(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command('seed_demo', stdout=open('/dev/null', 'w'))
        self.client = APIClient()

    def test_web_app_served(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'web/app.js')

    def test_filters_users_and_ticket_patch(self):
        from .models import SubDeptOfficeDetails, TNGovtDept, TNGovtSubDept
        dept = TNGovtDept.objects.get(department_name='School Education')
        subs = self.client.get(f'/api/v1/tngovtsubdept/?department={dept.id}').data['data']
        self.assertEqual([s['sub_department_name'] for s in subs], ['Directorate of School Education'])
        sub = TNGovtSubDept.objects.get(sub_department_name='Directorate of Public Health')
        self.assertEqual(len(self.client.get(f'/api/v1/subdeptofficedetails/?sub_dept={sub.id}').data['data']), 2)

        office = SubDeptOfficeDetails.objects.get(sub_dept_access_code='PHC-CHN-EGM')
        users = self.client.get(f'/api/v1/users/?sub_dept_office={office.id}').data['data']
        self.assertEqual(sorted(u['name'] for u in users), ['Kavitha Raman', 'Meena Sundaram', 'Senthil Kumar'])
        self.assertNotIn('password', users[0])

        group = WorkGroupTicket.objects.first().work_group
        members = self.client.get(f'/api/v1/workgroup/{group.id}/members/').data['data']
        self.assertTrue(all(m['name'] for m in members))

        ticket = WorkGroupTicket.objects.filter(ticket_status='Created').first()
        res = self.client.patch(f'/api/v1/workgroupticket/{ticket.id}/', {'ticket_status': 'Completed'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.ticket_status, 'Completed')
        self.assertEqual(self.client.patch(f'/api/v1/workgroupticket/{ticket.id}/', {'ticket_status': 'Nope'}, format='json').status_code, 400)
