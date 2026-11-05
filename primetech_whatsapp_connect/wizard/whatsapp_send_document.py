import base64

from odoo import _, fields, models
from odoo.exceptions import UserError


class WhatsAppSendDocument(models.TransientModel):
    _name = "primetech.whatsapp.send.document"
    _description = "Envoyer un document par WhatsApp"

    conversation_id = fields.Many2one("primetech.whatsapp.conversation", required=True)
    document_model = fields.Selection([( "sale.order", "Devis / commande"), ("account.move", "Facture"), ("stock.picking", "Bon de livraison")], required=True, default="sale.order")
    document_id = fields.Reference(selection="_document_models", required=True, string="Document")
    body = fields.Text(string="Message")
    scheduled_at = fields.Datetime(string="Planifier l'envoi")

    def _document_models(self):
        return [("sale.order", "Devis / commande"), ("account.move", "Facture"), ("stock.picking", "Bon de livraison")]

    def action_send(self):
        self.ensure_one()
        document = self.document_id
        if not document or document._name != self.document_model:
            raise UserError(_("Sélectionnez un document du type choisi."))
        report_xmlid = {
            "sale.order": "sale.action_report_saleorder",
            "account.move": "account.account_invoices",
            "stock.picking": "stock.action_report_delivery",
        }[self.document_model]
        report = self.env.ref(report_xmlid)
        pdf, _format = report._render_qweb_pdf(report, document.ids)
        attachment = self.env["ir.attachment"].create({
            "name": "%s.pdf" % document.display_name,
            "type": "binary", "datas": base64.b64encode(pdf), "mimetype": "application/pdf",
            "res_model": document._name, "res_id": document.id,
        })
        message = self.env["primetech.whatsapp.message"].create({
            "conversation_id": self.conversation_id.id, "direction": "outgoing", "message_type": "document",
            "body": self.body, "attachment_id": attachment.id, "related_document": "%s,%s" % (document._name, document.id),
            "scheduled_at": self.scheduled_at, "state": "scheduled" if self.scheduled_at else "draft",
        })
        if not self.scheduled_at:
            message.action_send_now()
        return {"type": "ir.actions.act_window_close"}
