# -*- encoding: utf-8 -*-

{
    'name': 'FEL Guatemala',
    'version': '1.2',
    'category': 'Custom',
    'description': """ Campos y funciones base para la facturación electrónica en Guatemala """,
    'author': 'aquíH',
    'website': 'http://aquih.com/',
    'depends': ['l10n_gt_extra'],
    'data': [
        'views/account_view.xml',
        'views/res_company_view.xml',
        'views/partner_view.xml',
        'views/report_invoice.xml',
    ],
    'demo': [],
    'installable': True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
