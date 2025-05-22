# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.release import version_info

class ResCompany(models.Model):
    _inherit = "res.company"

    certificador_fel = fields.Selection([], 'Certificador FEL')
    afiliacion_iva_fel = fields.Selection([('GEN', 'GEN'), ('PEQ', 'PEQ'), ('EXE', 'EXE')], 'Afiliación IVA FEL', default='GEN')
    tipo_personeria_fel = fields.Char('Tipo Personeria FEL')
    frases_fel = fields.Text('Frases FEL', help="Puede usar la función frase(tipo=1, escenario=1) para agregar frases a la compañía.")
    adenda_fel = fields.Text('Adenda FEL')

