from odoo import _, fields, models
from odoo.exceptions import UserError


class WhatsAppCampaign(models.Model):
    _name = "primetech.whatsapp.campaign"
    _description = "Campagne WhatsApp"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True)
    account_id = fields.Many2one("primetech.whatsapp.account", required=True)
    body = fields.Text(required=True)
    attachment_id = fields.Many2one("ir.attachment")
    partner_ids = fields.Many2many("res.partner", string="Destinataires")
    scheduled_at = fields.Datetime(string="Envoyer le")
    state = fields.Selection([( "draft", "Brouillon"), ("scheduled", "Planifiée"), ("sent", "Mise en file")], default="draft", tracking=True)
    line_ids = fields.One2many("primetech.whatsapp.campaign.line", "campaign_id")

    def action_queue(self):
        for campaign in self:
            if not campaign.partner_ids:
                raise UserError(_("Ajoutez au moins un contact."))
            for partner in campaign.partner_ids:
                phone = self.env["primetech.whatsapp.conversation"].normalize_phone(partner.mobile or partner.phone)
                if not phone:
                    continue
                conversation = self.env["primetech.whatsapp.conversation"].find_or_create(campaign.account_id, phone, partner)
                message = self.env["primetech.whatsapp.message"].create({
                    "conversation_id": conversation.id, "direction": "outgoing", "body": campaign.body,
                    "attachment_id": campaign.attachment_id.id, "message_type": "document" if campaign.attachment_id else "text",
                    "scheduled_at": campaign.scheduled_at or fields.Datetime.now(), "state": "scheduled",
                })
                self.env["primetech.whatsapp.campaign.line"].create({"campaign_id": campaign.id, "partner_id": partner.id, "message_id": message.id})
            campaign.state = "sent"
        return True


class WhatsAppCampaignLine(models.Model):
    _name = "primetech.whatsapp.campaign.line"
    _description = "Destinataire campagne WhatsApp"

    campaign_id = fields.Many2one("primetech.whatsapp.campaign", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", required=True)
    message_id = fields.Many2one("primetech.whatsapp.message", required=True, ondelete="cascade")
    state = fields.Selection(related="message_id.state")
