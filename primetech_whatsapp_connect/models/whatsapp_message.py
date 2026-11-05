from datetime import datetime

from odoo import _, api, fields, models


class WhatsAppMessage(models.Model):
    _name = "primetech.whatsapp.message"
    _description = "Message WhatsApp"
    _order = "date asc, id asc"

    conversation_id = fields.Many2one("primetech.whatsapp.conversation", required=True, ondelete="cascade", index=True)
    account_id = fields.Many2one(related="conversation_id.account_id", store=True)
    partner_id = fields.Many2one(related="conversation_id.partner_id", store=True)
    direction = fields.Selection([( "incoming", "Reçu"), ("outgoing", "Envoyé")], required=True, default="outgoing")
    message_type = fields.Selection([( "text", "Texte"), ("document", "Document"), ("image", "Image"), ("other", "Autre")], default="text", required=True)
    body = fields.Text(string="Message")
    attachment_id = fields.Many2one("ir.attachment", string="Pièce jointe", ondelete="set null")
    external_id = fields.Char(string="ID WhatsApp", copy=False, index=True)
    state = fields.Selection([( "draft", "Brouillon"), ("scheduled", "Planifié"), ("sent", "Envoyé"), ("received", "Reçu"), ("failed", "Échec")], default="draft", required=True, index=True)
    scheduled_at = fields.Datetime(string="Envoyer le", index=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    error_message = fields.Text(readonly=True)
    related_document = fields.Reference(selection="_related_document_models", string="Document Odoo")

    @api.model
    def _related_document_models(self):
        return [("sale.order", "Devis / commande client"), ("account.move", "Facture"), ("stock.picking", "Bon de livraison")]

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        for message in messages:
            message.conversation_id.last_message_at = message.date
        return messages

    def action_send_now(self):
        for message in self:
            message._send()
        return True

    def action_schedule(self):
        self.write({"state": "scheduled"})
        return True

    def _send(self):
        for message in self:
            try:
                if message.attachment_id:
                    result = message.account_id.send_attachment(message.conversation_id.phone, message.attachment_id, message.body)
                else:
                    result = message.account_id.send_text(message.conversation_id.phone, message.body or "")
                message.write({
                    "state": "sent", "date": fields.Datetime.now(),
                    "external_id": (result.get("messages") or [{}])[0].get("id"), "error_message": False,
                })
            except Exception as exc:  # Retain the failure on the message and continue the queue.
                message.write({"state": "failed", "error_message": str(exc)})
        return True

    @api.model
    def _cron_send_scheduled_messages(self):
        messages = self.search([("state", "=", "scheduled"), ("scheduled_at", "<=", fields.Datetime.now())], limit=100)
        messages._send()

    @api.model
    def receive_from_webhook(self, account, phone, payload):
        conversation = self.env["primetech.whatsapp.conversation"].find_or_create(account, phone)
        message_type = payload.get("type", "other")
        content = payload.get(message_type, {})
        body = content.get("body") if message_type == "text" else content.get("caption") or _("Média reçu (%s)") % message_type
        attachment = False
        media_id = content.get("id")
        if media_id:
            try:
                attachment = account.download_media(media_id)
            except Exception:
                # Preserve the received message even if Meta's temporary media
                # URL can no longer be downloaded.
                attachment = False
        return self.create({
            "conversation_id": conversation.id, "direction": "incoming", "message_type": message_type if message_type in ("text", "document", "image") else "other",
            "body": body, "attachment_id": attachment.id, "external_id": payload.get("id"), "state": "received", "date": datetime.fromtimestamp(int(payload["timestamp"])) if payload.get("timestamp") else fields.Datetime.now(),
        })
