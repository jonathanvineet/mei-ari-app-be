from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from meiari_v1.methods import encrypt_password
from meiari_v1.models import (
    MeiAriUser, MeiAriUserBioData, SubDeptOfficeDetails, TNGovtDept, TNGovtSubDept, WorkGroup,
    WorkGroupDetails, WorkGroupMember, WorkGroupTicket,
)

DEMO_PASSWORD = 'MeiAri@123'

ORG = [
    ('Health and Family Welfare', 'State', 'Directorate of Public Health', [
        ('Primary Health Centre, Egmore', '12 Pantheon Road, Egmore', 'Chennai', 'Egmore', 'PHC-CHN-EGM'),
        ('Primary Health Centre, Tambaram', '4 GST Road, Tambaram', 'Chengalpattu', 'Tambaram', 'PHC-CGL-TBM'),
    ]),
    ('School Education', 'State', 'Directorate of School Education', [
        ('Government Higher Secondary School, Madurai East', '21 Anna Nagar Main Road', 'Madurai', 'Madurai East', 'GHSS-MDU-EST'),
    ]),
]

USERS = [
    ('officer@demo.tn.gov.in', 'Inspection_Cell_Officer', 'Kavitha', 'Raman', date(1990, 5, 17)),
    ('head@demo.tn.gov.in', 'Inspection_Cell_Head', 'Senthil', 'Kumar', date(1982, 11, 3)),
    ('admin@demo.tn.gov.in', 'Inspection_Cell_Admin', 'Meena', 'Sundaram', date(1978, 2, 24)),
]


class Command(BaseCommand):
    help = "Create a sample organisation, demo users (one per role), a work group and tickets. Safe to re-run."

    @transaction.atomic
    def handle(self, *args, **options):
        offices = []
        for dept_name, level, sub_name, office_rows in ORG:
            dept, _ = TNGovtDept.objects.get_or_create(department_name=dept_name, defaults={'level': level})
            sub, _ = TNGovtSubDept.objects.get_or_create(department=dept, sub_department_name=sub_name)
            for location, street, district, taluk, code in office_rows:
                office, _ = SubDeptOfficeDetails.objects.get_or_create(
                    sub_dept_access_code=code,
                    defaults={'sub_dept': sub, 'sub_dept_office_location': location, 'sub_dept_street_address': street,
                              'sub_dept_district': district, 'sub_dept_taluk': taluk},
                )
                offices.append((dept, sub, office))

        dept, sub, office = offices[0]
        users = []
        for email, role, first, last, dob in USERS:
            user = MeiAriUser.objects.filter(cug_email_address=email).first()
            if not user:
                user = MeiAriUser.objects.create(
                    cug_email_address=email, cug_phone_number='9444000000', password=encrypt_password(DEMO_PASSWORD),
                    role=role, dept_id=dept, sub_dept_id=sub, sub_dept_office_id=office,
                )
                MeiAriUserBioData.objects.create(
                    user=user, user_name=first.lower(), first_name=first, last_name=last, date_of_birth=dob,
                    alternative_email_address=email,
                )
            users.append(user)

        group, created = WorkGroup.objects.get_or_create(sub_dept_office=office, group_name='Monsoon readiness team')
        if created:
            WorkGroupDetails.objects.create(work_group=group, group_description='Checks drainage, drug stock and cold chain before the north-east monsoon.')
            for user, role_name in zip(users, ['Field inspector', 'Team lead', 'Coordinator']):
                WorkGroupMember.objects.create(work_group=group, user_id=user.id, role_name=role_name)
            for title, desc, priority, ticket_status in [
                ('Inspect vaccine cold chain', 'Check fridge temperature logs for the last 30 days.', 'High', 'Created'),
                ('Verify ORS and paracetamol stock', 'Compare pharmacy register with physical stock.', 'Medium', 'Completed'),
                ('Clear storm drain near OPD block', 'Confirm the municipal work order has been completed.', 'Low', 'Verified'),
            ]:
                WorkGroupTicket.objects.create(
                    work_group=group, ticket_title=title, ticket_description=desc, ticket_priority=priority,
                    ticket_status=ticket_status, ticket_type='TaskAssign', ticket_owner_id=users[0],
                )

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Sign in with {', '.join(u[0] for u in USERS)} / password {DEMO_PASSWORD}"
        ))
