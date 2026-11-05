from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WhatsAppConversation(models.Model):
    _name = "primetech.whatsapp.conversation"
    _description = "Conversation WhatsApp"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "last_message_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    account_id = fields.Many2one("primetech.whatsapp.account", required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", tracking=True)
    phone = fields.Char(required=True, index=True, help="Format international sans le signe +.")
    message_ids = fields.One2many("primetech.whatsapp.message", "conversation_id")
    last_message_at = fields.Datetime(index=True)
    active = fields.Boolean(default=True)

    _whatsapp_conversation_unique = models.Constraint(
        "unique(account_id, phone)",
        "Une conversation existe déjà pour ce numéro et ce compte.",
    )

    @api.depends("partner_id", "phone")
    def _compute_name(self):
        for conversation in self:
            conversation.name = conversation.partner_id.display_name or conversation.phone

    @api.model
    def normalize_phone(self, phone):
        return "".join(char for char in (phone or "") if char.isdigit())

    @api.model
    def find_or_create(self, account, phone, partner=False):
        phone = self.normalize_phone(phone)
        conversation = self.search([("account_id", "=", account.id), ("phone", "=", phone)], limit=1)
        if not conversation:
            partner = partner or self.env["res.partner"].search(["|", ("mobile", "ilike", phone[-9:]), ("phone", "ilike", phone[-9:])], limit=1)
            conversation = self.create({"account_id": account.id, "phone": phone, "partner_id": partner.id})
        return conversation

    def action_open_send_document(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Envoyer un document WhatsApp"),
            "res_model": "primetech.whatsapp.send.document", "view_mode": "form", "target": "new",
            "context": {"default_conversation_id": self.id},
        }

    def action_new_message(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Nouveau message"),
            "res_model": "primetech.whatsapp.message", "view_mode": "form", "target": "new",
            "context": {"default_conversation_id": self.id, "default_direction": "outgoing"},
        }
