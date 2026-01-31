{
    'name': 'Hamarpea Surgery Coordination',
    'version': '18.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Manage surgical cases from consultation to completion',
    'description': """
Surgery Case Management
=======================
Track patient journey through surgery with:
- Medical clearance workflow
- Financial/insurance tracking
- Surgical center commission management
- Multi-stage pipeline
    """,
    'author': 'Hamarpea',
    'website': 'https://www.hamarpea.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'crm',
        'calendar',
        'mail',
        'contacts',
        'hr',
        'hamarpea-odoo-contacts',  # For insurance fields
        'partner_contact_personal_information_page',  # For birthdate
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/surgery_stage_data.xml',
        'views/surgery_stage_views.xml',
        'views/surgery_medical_item_views.xml',
        'views/surgery_drug_restriction_views.xml',
        'views/res_partner_views.xml',
        'views/hr_employee_views.xml',
        'views/surgery_case_views.xml',
        'views/sale_order_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
