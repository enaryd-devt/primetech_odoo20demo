import logging
import base64
import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class WhatsAppAccount(models.Model):
    _name = "primetech.whatsapp.account"
    _description = "Compte WhatsApp Business"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    is_active = fields.Boolean(string="Actif", related="active", readonly=False)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    phone_number_id = fields.Char(required=True, help="ID du numéro de téléphone fourni par Meta.")
    business_account_id = fields.Char(string="ID compte WhatsApp Business")
    access_token = fields.Char(required=True, groups="primetech_whatsapp_connect.group_primetech_whatsapp_manager")
    verify_token = fields.Char(required=True, groups="primetech_whatsapp_connect.group_primetech_whatsapp_manager")
    api_version = fields.Char(default="v22.0", required=True)
    display_phone_number = fields.Char(string="Numéro affiché")
    webhook_url = fields.Char(string="URL de rappel", readonly=True, copy=False)

    def _api_url(self, suffix):
        self.ensure_one()
        return "https://graph.facebook.com/%s/%s" % (self.api_version, suffix.lstrip("/"))

    def _headers(self):
        self.ensure_one()
        return {"Authorization": "Bearer %s" % self.access_token}

    def _request(self, method, suffix, **kwargs):
        self.ensure_one()
        try:
            response = requests.request(method, self._api_url(suffix), headers=self._headers(), timeout=45, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            _logger.exception("WhatsApp API call failed for account %s", self.display_name)
            raise UserError(_("L'API WhatsApp a refusé la demande : %s") % exc) from exc

    def action_test_connection(self):
        """Validate the configured token and phone number without sending a message."""
        self.ensure_one()
        if not self.phone_number_id or not self.access_token:
            raise UserError(_("Renseignez l'ID du numéro WhatsApp et le jeton d'accès avant le test."))

        result = self._request(
            "GET",
            self.phone_number_id,
            params={"fields": "id,display_phone_number,verified_name"},
        )
        phone = result.get("display_phone_number") or self.phone_number_id
        verified_name = result.get("verified_name")
        message = _("La connexion à WhatsApp est valide pour le numéro %s.") % phone
        if verified_name:
            message += " " + _("Compte vérifié : %s.") % verified_name
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connexion WhatsApp réussie"),
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

    def action_generate_webhook_url(self):
        """Build the callback URL from the server address used by the current user."""
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_str("web.base.url")
        try:
            http_request = request.httprequest
            forwarded_scheme = http_request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
            scheme = forwarded_scheme or http_request.scheme
            base_url = "%s://%s" % (scheme, http_request.host)
        except RuntimeError:
            # The action can also be invoked outside an HTTP request (e.g. tests).
            pass

        if not base_url:
            raise UserError(_("Impossible de déterminer l'adresse du serveur Odoo."))
        self.webhook_url = "%s/primetech_whatsapp/webhook" % base_url.rstrip("/")
        # ``reload`` makes the URL and its copy icon immediately available.
        return {
            "type": "ir.actions.client",
            "tag": "reload",
            "params": {
                "title": _("URL de rappel générée"),
                "message": _("Copiez cette URL dans la configuration Webhook de Meta."),
                "type": "success",
                "sticky": False,
            },
        }

    def send_text(self, phone, body, reply_to=None):
        payload = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": body}}
        if reply_to:
            payload["context"] = {"message_id": reply_to}
        return self._request("POST", "%s/messages" % self.phone_number_id, json=payload)

    def upload_media(self, attachment):
        self.ensure_one()
        raw = attachment.raw
        if not raw:
            raise UserError(_("La pièce jointe est vide."))
        files = {"file": (attachment.name, raw, attachment.mimetype or "application/octet-stream")}
        data = {"messaging_product": "whatsapp", "type": attachment.mimetype or "application/octet-stream"}
        result = self._request("POST", self.phone_number_id + "/media", data=data, files=files)
        return result.get("id")

    def send_attachment(self, phone, attachment, caption=False):
        media_id = self.upload_media(attachment)
        media_type = "image" if (attachment.mimetype or "").startswith("image/") else "document"
        content = {"id": media_id}
        if caption:
            content["caption"] = caption
        return self._request("POST", "%s/messages" % self.phone_number_id, json={
            "messaging_product": "whatsapp", "to": phone, "type": media_type, media_type: content,
        })

    def download_media(self, media_id):
        """Return a binary Odoo attachment for an incoming Meta-hosted media."""
        self.ensure_one()
        metadata = self._request("GET", media_id)
        try:
            response = requests.get(metadata["url"], headers=self._headers(), timeout=45)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("Impossible de télécharger le média WhatsApp : %s") % exc) from exc
        return self.env["ir.attachment"].create({
            "name": metadata.get("filename") or (media_id + ".bin"),
            "type": "binary", "datas": base64.b64encode(response.content),
            "mimetype": metadata.get("mime_type") or response.headers.get("Content-Type"),
        })
