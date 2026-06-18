{
    'name': 'FEL Guatemala',
    'version': '1.22',
    'category': 'Custom',
    'description': """ Campos y funciones base para la facturación electrónica en Guatemala """,
    'author': 'aquíH',
    'website': 'http://www.aquih.com/',
    'depends': ['l10n_gt_extra'],
    'data': [
        'views/account_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/report_invoice.xml',
    ],
    'demo': [],
    'installable': True,
    'license': 'Other OSI approved licence',
}
