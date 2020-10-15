# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round

from datetime import datetime
import base64
from lxml import etree
import requests
import re

#from OpenSSL import crypto
#import xmlsig
#from xades import XAdESContext, template, utils, ObjectIdentifier
#from xades.policy import GenericPolicyId, ImpliedPolicy

import logging

class AccountMove(models.Model):
    _inherit = "account.move"

    firma_fel = fields.Char('Firma FEL', copy=False)
    serie_fel = fields.Char('Serie FEL', copy=False)
    numero_fel = fields.Char('Numero FEL', copy=False)
    factura_original_id = fields.Many2one('account.move', string="Factura original FEL", domain="[('type', '=', 'out_invoice')]")
    consignatario_fel = fields.Many2one('res.partner', string="Consignatario o Destinatario FEL")
    comprador_fel = fields.Many2one('res.partner', string="Comprador FEL")
    exportador_fel = fields.Many2one('res.partner', string="Exportador FEL")
    incoterm_fel = fields.Char(string="Incoterm FEL")
    documento_xml_fel = fields.Binary('Documento xml FEL', copy=False)
    documento_xml_fel_name = fields.Char('Nombre doc xml FEL', default='documento_xml_fel.xml', size=32)
    resultado_xml_fel = fields.Binary('Resultado xml FEL', copy=False)
    resultado_xml_fel_name = fields.Char('Resultado doc xml FEL', default='resultado_xml_fel.xml', size=32)
    certificador_fel = fields.Char('Certificador FEL', copy=False)

    def descuento_lineas(self,factura,invoice_line_ids):
        precio_total_descuento = 0
        precio_total_positivo = 0

        for linea in invoice_line_ids:
            if linea.price_unit > 0:
                precio_total_positivo += linea.price_total
            elif linea.price_unit < 0:
                precio_total_descuento += linea.price_total
                linea.price_unit = 0

        posicion = 0
        for linea in invoice_line_ids:
            if invoice_line_ids[posicion].price_unit > 0:
                descuento = ((precio_total_descuento / precio_total_positivo)*100)*-1
                factura.write({ 'invoice_line_ids': [[1, factura.invoice_line_ids[posicion].id, { 'discount': descuento }]] })
            posicion += 1
        return True

    def dte_documento(self):
        self.ensure_one()
        factura = self
        if factura.type in ['out_invoice', 'out_refund', 'in_invoice'] and not factura.firma_fel and factura.amount_total != 0:
            attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")

            NSMAP = {
                "ds": "http://www.w3.org/2000/09/xmldsig#",
                "dte": "http://www.sat.gob.gt/dte/fel/0.2.0",
            }

            NSMAP_REF = {
                "cno": "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0",
            }

            NSMAP_ABONO = {
                "cfc": "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0",
            }

            NSMAP_EXP = {
                "cex": "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0",
            }

            NSMAP_FE = {
                "cfe": "http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0",
            }

            DTE_NS = "{http://www.sat.gob.gt/dte/fel/0.2.0}"
            DS_NS = "{http://www.w3.org/2000/09/xmldsig#}"
            CNO_NS = "{http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0}"
            CFE_NS = "{http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0}"
            CEX_NS = "{http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0}"
            CFC_NS = "{http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0}"

            GTDocumento = etree.Element(DTE_NS+"GTDocumento", {}, Version="0.1", nsmap=NSMAP)
            SAT = etree.SubElement(GTDocumento, DTE_NS+"SAT", ClaseDocumento="dte")
            DTE = etree.SubElement(SAT, DTE_NS+"DTE", ID="DatosCertificados")
            DatosEmision = etree.SubElement(DTE, DTE_NS+"DatosEmision", ID="DatosEmision")

            tipo_documento_fel = factura.journal_id.tipo_documento_fel
            if tipo_documento_fel in ['FACT', 'FACM'] and factura.type == 'out_refund':
                tipo_documento_fel = 'NCRE'

            moneda = "GTQ"
            if factura.currency_id.id != factura.company_id.currency_id.id:
                moneda = "USD"

            fecha = factura.invoice_date.strftime('%Y-%m-%d')
            hora = "00:00:00-06:00"
            fecha_hora = fecha+'T'+hora
            DatosGenerales = etree.SubElement(DatosEmision, DTE_NS+"DatosGenerales", CodigoMoneda=moneda, FechaHoraEmision=fecha_hora, Tipo=tipo_documento_fel)
            if factura.tipo_gasto == 'importacion':
                DatosGenerales.attrib['Exp'] = "SI"

            Emisor = etree.SubElement(DatosEmision, DTE_NS+"Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=str(factura.journal_id.codigo_establecimiento), CorreoEmisor=factura.company_id.email or '', NITEmisor=factura.company_id.vat.replace('-',''), NombreComercial=factura.journal_id.direccion.name, NombreEmisor=factura.company_id.name)
            DireccionEmisor = etree.SubElement(Emisor, DTE_NS+"DireccionEmisor")
            Direccion = etree.SubElement(DireccionEmisor, DTE_NS+"Direccion")
            Direccion.text = factura.journal_id.direccion.street or 'Ciudad'
            CodigoPostal = etree.SubElement(DireccionEmisor, DTE_NS+"CodigoPostal")
            CodigoPostal.text = factura.journal_id.direccion.zip or '01001'
            Municipio = etree.SubElement(DireccionEmisor, DTE_NS+"Municipio")
            Municipio.text = factura.journal_id.direccion.city or 'Guatemala'
            Departamento = etree.SubElement(DireccionEmisor, DTE_NS+"Departamento")
            Departamento.text = factura.journal_id.direccion.state_id.name if factura.journal_id.direccion.state_id else ''
            Pais = etree.SubElement(DireccionEmisor, DTE_NS+"Pais")
            Pais.text = factura.journal_id.direccion.country_id.code or 'GT'

            nit_receptor = 'CF'
            if factura.partner_id.vat:
                nit_receptor = factura.partner_id.vat.replace('-','')
            if tipo_documento_fel == "FESP" and factura.partner_id.cui:
                nit_receptor = factura.partner_id.cui
            Receptor = etree.SubElement(DatosEmision, DTE_NS+"Receptor", IDReceptor=nit_receptor, NombreReceptor=factura.partner_id.name)
            if factura.partner_id.nombre_facturacion_fel:
                Receptor.attrib['NombreReceptor'] = factura.partner_id.nombre_facturacion_fel
            if factura.partner_id.email:
                Receptor.attrib['CorreoReceptor'] = factura.partner_id.email
            if tipo_documento_fel == "FESP" and factura.partner_id.cui:
                Receptor.attrib['TipoEspecial'] = "CUI"

            DireccionReceptor = etree.SubElement(Receptor, DTE_NS+"DireccionReceptor")
            Direccion = etree.SubElement(DireccionReceptor, DTE_NS+"Direccion")
            Direccion.text = (factura.partner_id.street or '') + ' ' + (factura.partner_id.street2 or '')
            CodigoPostal = etree.SubElement(DireccionReceptor, DTE_NS+"CodigoPostal")
            CodigoPostal.text = factura.partner_id.zip or '01001'
            Municipio = etree.SubElement(DireccionReceptor, DTE_NS+"Municipio")
            Municipio.text = factura.partner_id.city or 'Guatemala'
            Departamento = etree.SubElement(DireccionReceptor, DTE_NS+"Departamento")
            Departamento.text = factura.partner_id.state_id.name if factura.partner_id.state_id else ''
            Pais = etree.SubElement(DireccionReceptor, DTE_NS+"Pais")
            Pais.text = factura.partner_id.country_id.code or 'GT'

            if tipo_documento_fel not in ['NDEB', 'NCRE', 'RECI', 'NABN', 'FESP']:
                ElementoFrases = etree.fromstring(factura.company_id.frases_fel)
                if factura.tipo_gasto == 'importacion':
                    Frase = etree.SubElement(ElementoFrases, DTE_NS+"Frase", CodigoEscenario="1", TipoFrase="4")
                DatosEmision.append(ElementoFrases)

            Items = etree.SubElement(DatosEmision, DTE_NS+"Items")

            linea_num = 0
            gran_subtotal = 0
            gran_total = 0
            gran_total_impuestos = 0
            cantidad_impuestos = 0
            self.descuento_lineas(factura,factura.invoice_line_ids)

            for linea in factura.invoice_line_ids:

                if linea.quantity * linea.price_unit == 0:
                    continue

                linea_num += 1

                tipo_producto = "B"
                if linea.product_id.type == 'service':
                    tipo_producto = "S"
                precio_unitario = linea.price_unit * (100-linea.discount) / 100
                precio_sin_descuento = linea.price_unit
                descuento = precio_sin_descuento * linea.quantity - precio_unitario * linea.quantity
                precio_unitario_base = linea.price_subtotal / linea.quantity
                total_linea = precio_unitario * linea.quantity
                total_linea_base = precio_unitario_base * linea.quantity
                total_impuestos = total_linea - total_linea_base
                cantidad_impuestos += len(linea.tax_ids)

                Item = etree.SubElement(Items, DTE_NS+"Item", BienOServicio=tipo_producto, NumeroLinea=str(linea_num))
                Cantidad = etree.SubElement(Item, DTE_NS+"Cantidad")
                Cantidad.text = str(linea.quantity)
                UnidadMedida = etree.SubElement(Item, DTE_NS+"UnidadMedida")
                UnidadMedida.text = linea.product_uom_id.name[0:3] if linea.product_uom_id else 'UNI'
                Descripcion = etree.SubElement(Item, DTE_NS+"Descripcion")
                Descripcion.text = linea.name
                PrecioUnitario = etree.SubElement(Item, DTE_NS+"PrecioUnitario")
                PrecioUnitario.text = '{:.6f}'.format(precio_sin_descuento)
                Precio = etree.SubElement(Item, DTE_NS+"Precio")
                Precio.text = '{:.6f}'.format(precio_sin_descuento * linea.quantity)
                Descuento = etree.SubElement(Item, DTE_NS+"Descuento")
                Descuento.text = '{:.6f}'.format(descuento)
                if len(linea.tax_ids) > 0:
                    Impuestos = etree.SubElement(Item, DTE_NS+"Impuestos")
                    Impuesto = etree.SubElement(Impuestos, DTE_NS+"Impuesto")
                    NombreCorto = etree.SubElement(Impuesto, DTE_NS+"NombreCorto")
                    NombreCorto.text = "IVA"
                    CodigoUnidadGravable = etree.SubElement(Impuesto, DTE_NS+"CodigoUnidadGravable")
                    CodigoUnidadGravable.text = "1"
                    if factura.tipo_gasto == 'importacion' or ( tipo_documento_fel in ['NDEB', 'NCRE'] and factura.factura_original_id and factura.factura_original_id.tipo_gasto == 'importacion' ):
                        CodigoUnidadGravable.text = "2"
                    MontoGravable = etree.SubElement(Impuesto, DTE_NS+"MontoGravable")
                    MontoGravable.text = '{:.6f}'.format(total_linea_base)
                    MontoImpuesto = etree.SubElement(Impuesto, DTE_NS+"MontoImpuesto")
                    MontoImpuesto.text = '{:.6f}'.format(total_impuestos)
                Total = etree.SubElement(Item, DTE_NS+"Total")
                Total.text = '{:.2f}'.format(total_linea)

                gran_total += factura.currency_id.round(total_linea)
                gran_subtotal += factura.currency_id.round(total_linea_base)
                gran_total_impuestos += factura.currency_id.round(total_impuestos)

            Totales = etree.SubElement(DatosEmision, DTE_NS+"Totales")
            if cantidad_impuestos > 0:
                TotalImpuestos = etree.SubElement(Totales, DTE_NS+"TotalImpuestos")
                TotalImpuesto = etree.SubElement(TotalImpuestos, DTE_NS+"TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto='{:.2f}'.format(factura.currency_id.round(gran_total_impuestos)))
            GranTotal = etree.SubElement(Totales, DTE_NS+"GranTotal")
            GranTotal.text = '{:.2f}'.format(factura.currency_id.round(gran_total))

            if factura.company_id.adenda_fel:
                Adenda = etree.SubElement(SAT, DTE_NS+"Adenda")
                exec(factura.company_id.adenda_fel, {'etree': etree, 'Adenda': Adenda, 'factura': factura})

            # En todos estos casos, es necesario enviar complementos
            if tipo_documento_fel in ['NDEB', 'NCRE'] or tipo_documento_fel in ['FCAM'] or (tipo_documento_fel in ['FACT', 'FCAM'] and factura.tipo_gasto == 'importacion') or tipo_documento_fel in ['FESP']:
                Complementos = etree.SubElement(DatosEmision, DTE_NS+"Complementos")

                if tipo_documento_fel in ['NDEB', 'NCRE']:
                    Complemento = etree.SubElement(Complementos, DTE_NS+"Complemento", IDComplemento="ReferenciasNota", NombreComplemento="Nota de Credito" if tipo_documento_fel == 'NCRE' else "Nota de Debito", URIComplemento="http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0")
                    if factura.factura_original_id.numero_fel:
                        ReferenciasNota = etree.SubElement(Complemento, CNO_NS+"ReferenciasNota", FechaEmisionDocumentoOrigen=str(factura.factura_original_id.invoice_date), MotivoAjuste="-", NumeroAutorizacionDocumentoOrigen=factura.factura_original_id.firma_fel, NumeroDocumentoOrigen=factura.factura_original_id.numero_fel, SerieDocumentoOrigen=factura.factura_original_id.serie_fel, Version="0.0", nsmap=NSMAP_REF)
                    else:
                        ReferenciasNota = etree.SubElement(Complemento, CNO_NS+"ReferenciasNota", RegimenAntiguo="Antiguo", FechaEmisionDocumentoOrigen=str(factura.factura_original_id.invoice_date), MotivoAjuste="-", NumeroAutorizacionDocumentoOrigen=factura.factura_original_id.firma_fel, NumeroDocumentoOrigen=factura.factura_original_id.ref.split("-")[1], SerieDocumentoOrigen=factura.factura_original_id.ref.split("-")[0], Version="0.0", nsmap=NSMAP_REF)

                if tipo_documento_fel in ['FCAM']:
                    Complemento = etree.SubElement(Complementos, DTE_NS+"Complemento", IDComplemento="FCAM", NombreComplemento="AbonosFacturaCambiaria", URIComplemento="http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0")
                    AbonosFacturaCambiaria = etree.SubElement(Complemento, CFC_NS+"AbonosFacturaCambiaria", Version="1", nsmap=NSMAP_ABONO)
                    Abono = etree.SubElement(AbonosFacturaCambiaria, CFC_NS+"Abono")
                    NumeroAbono = etree.SubElement(Abono, CFC_NS+"NumeroAbono")
                    NumeroAbono.text = "1"
                    FechaVencimiento = etree.SubElement(Abono, CFC_NS+"FechaVencimiento")
                    FFechaVencimiento.text = str(factura.date_due)
                    MontoAbono = etree.SubElement(Abono, CFC_NS+"MontoAbono")
                    MontoAbono.text = '{:.2f}'.format(factura.currency_id.round(gran_total))

                if tipo_documento_fel in ['FACT', 'FCAM'] and factura.tipo_gasto == 'importacion':
                    Complemento = etree.SubElement(Complementos, DTE_NS+"Complemento", IDComplemento="text", NombreComplemento="text", URIComplemento="http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0")
                    Exportacion = etree.SubElement(Complemento, CEX_NS+"Exportacion", Version="1", nsmap=NSMAP_EXP)
                    NombreConsignatarioODestinatario = etree.SubElement(Exportacion, CEX_NS+"NombreConsignatarioODestinatario")
                    NombreConsignatarioODestinatario.text = factura.consignatario_fel.name if factura.consignatario_fel else "-"
                    DireccionConsignatarioODestinatario = etree.SubElement(Exportacion, CEX_NS+"DireccionConsignatarioODestinatario")
                    DireccionConsignatarioODestinatario.text = factura.consignatario_fel.street or "-" if factura.consignatario_fel else "-"
                    CodigoConsignatarioODestinatario = etree.SubElement(Exportacion, CEX_NS+"CodigoConsignatarioODestinatario")
                    CodigoConsignatarioODestinatario.text = factura.consignatario_fel.ref or "-" if factura.consignatario_fel else "-"
                    NombreComprador = etree.SubElement(Exportacion, CEX_NS+"NombreComprador")
                    NombreComprador.text = factura.comprador_fel.name if factura.comprador_fel else "-"
                    DireccionComprador = etree.SubElement(Exportacion, CEX_NS+"DireccionComprador")
                    DireccionComprador.text = factura.comprador_fel.street or "-" if factura.comprador_fel else "-"
                    CodigoComprador = etree.SubElement(Exportacion, CEX_NS+"CodigoComprador")
                    CodigoComprador.text = factura.comprador_fel.ref or "-" if factura.comprador_fel else "-"
                    INCOTERM = etree.SubElement(Exportacion, CEX_NS+"INCOTERM")
                    INCOTERM.text = factura.incoterm_fel or "-"
                    NombreExportador = etree.SubElement(Exportacion, CEX_NS+"NombreExportador")
                    NombreExportador.text = factura.exportador_fel.name if factura.exportador_fel else "-"
                    CodigoExportador = etree.SubElement(Exportacion, CEX_NS+"CodigoExportador")
                    CodigoExportador.text = factura.exportador_fel.ref or "-" if factura.exportador_fel else "-"

                if tipo_documento_fel in ['FESP']:
                    total_isr = abs(factura.amount_tax)

                    total_iva_retencion = 0
                    for impuesto in factura.amount_by_group:
                        if impuesto[1] > 0:
                            total_iva_retencion += impuesto[1]

                    Complemento = etree.SubElement(Complementos, DTE_NS+"Complemento", IDComplemento="FacturaEspecial", NombreComplemento="FacturaEspecial", URIComplemento="http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0")
                    RetencionesFacturaEspecial = etree.SubElement(Complemento, CFE_NS+"RetencionesFacturaEspecial", Version="1", nsmap=NSMAP_FE)
                    RetencionISR = etree.SubElement(RetencionesFacturaEspecial, CFE_NS+"RetencionISR")
                    RetencionISR.text = str(total_isr)
                    RetencionIVA = etree.SubElement(RetencionesFacturaEspecial, CFE_NS+"RetencionIVA")
                    RetencionIVA.text = str(total_iva_retencion)
                    TotalMenosRetenciones = etree.SubElement(RetencionesFacturaEspecial, CFE_NS+"TotalMenosRetenciones")
                    TotalMenosRetenciones.text = str(factura.amount_total)

            # signature = xmlsig.template.create(
            #     xmlsig.constants.TransformInclC14N,
            #     xmlsig.constants.TransformRsaSha256,
            #     "Signature"
            # )
            # signature_id = utils.get_unique_id()
            # ref_datos = xmlsig.template.add_reference(
            #     signature, xmlsig.constants.TransformSha256, uri="#DatosEmision"
            # )
            # xmlsig.template.add_transform(ref_datos, xmlsig.constants.TransformEnveloped)
            # ref_prop = xmlsig.template.add_reference(
            #     signature, xmlsig.constants.TransformSha256, uri_type="http://uri.etsi.org/01903#SignedProperties", uri="#" + signature_id
            # )
            # xmlsig.template.add_transform(ref_prop, xmlsig.constants.TransformInclC14N)
            # ki = xmlsig.template.ensure_key_info(signature)
            # data = xmlsig.template.add_x509_data(ki)
            # xmlsig.template.x509_data_add_certificate(data)
            # xmlsig.template.x509_data_add_subject_name(data)
            # serial = xmlsig.template.x509_data_add_issuer_serial(data)
            # xmlsig.template.x509_issuer_serial_add_issuer_name(serial)
            # xmlsig.template.x509_issuer_serial_add_serial_number(serial)
            # qualifying = template.create_qualifying_properties(
            #     signature, name=utils.get_unique_id()
            # )
            # props = template.create_signed_properties(
            #     qualifying, name=signature_id, datetime=fecha_hora
            # )
            #
            # GTDocumento.append(signature)
            # ctx = XAdESContext()
            # with open(path.join("/home/odoo/megaprint_leplan", "51043491-6747a80bb6a554ae.pfx"), "rb") as key_file:
            #     ctx.load_pkcs12(crypto.load_pkcs12(key_file.read(), "Planeta123$"))
            # ctx.sign(signature)
            # ctx.verify(signature)
            # DatosEmision.remove(SingatureTemp)

            # xml_con_firma = etree.tostring(GTDocumento, encoding="utf-8").decode("utf-8")

            return GTDocumento

    def dte_anulacion(self):
        self.ensure_one()
        factura = self

        NSMAP = {
            "ds": "http://www.w3.org/2000/09/xmldsig#",
            "dte": "http://www.sat.gob.gt/dte/fel/0.1.0",
        }

        DTE_NS = "{http://www.sat.gob.gt/dte/fel/0.1.0}"
        DS_NS = "{http://www.w3.org/2000/09/xmldsig#}"

        if factura.firma_fel:

            tipo_documento_fel = factura.journal_id.tipo_documento_fel
            if tipo_documento_fel in ['FACT', 'FACM'] and factura.type == 'out_refund':
                tipo_documento_fel = 'NCRE'

            nit_receptor = 'CF'
            if factura.partner_id.vat:
                nit_receptor = factura.partner_id.vat.replace('-','')
            if tipo_documento_fel == "FESP" and factura.partner_id.cui:
                nit_receptor = factura.partner_id.cui

            fecha = fields.Date.from_string(factura.invoice_date).strftime('%Y-%m-%d')
            hora = "00:00:00-06:00"
            fecha_hora = fecha+'T'+hora

            fecha_hoy_hora = fields.Date.context_today(factura).strftime('%Y-%m-%dT%H:%M:%S')

            GTAnulacionDocumento = etree.Element(DTE_NS+"GTAnulacionDocumento", {}, Version="0.1", nsmap=NSMAP)
            SAT = etree.SubElement(GTAnulacionDocumento, DTE_NS+"SAT")
            AnulacionDTE = etree.SubElement(SAT, DTE_NS+"AnulacionDTE", ID="DatosCertificados")
            DatosGenerales = etree.SubElement(AnulacionDTE, DTE_NS+"DatosGenerales", ID="DatosAnulacion", NumeroDocumentoAAnular=factura.firma_fel, NITEmisor=factura.company_id.vat.replace("-",""), IDReceptor=nit_receptor, FechaEmisionDocumentoAnular=fecha_hora, FechaHoraAnulacion=fecha_hoy_hora, MotivoAnulacion=factura.narration or "Error")

            return GTAnulacionDocumento

class AccountJournal(models.Model):
    _inherit = "account.journal"

    tipo_documento_fel = fields.Selection([('FACT', 'FACT'), ('FCAM', 'FCAM'), ('FPEQ', 'FPEQ'), ('FCAP', 'FCAP'), ('FESP', 'FESP'), ('NABN', 'NABN'), ('RDON', 'RDON'), ('RECI', 'RECI'), ('NDEB', 'NDEB'), ('NCRE', 'NCRE')], 'Tipo de Documento FEL', copy=False)

class ResCompany(models.Model):
    _inherit = "res.company"

    frases_fel = fields.Text('Frases FEL')
    adenda_fel = fields.Text('Adenda FEL')
