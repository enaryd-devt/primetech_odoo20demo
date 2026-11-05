from odoo import http
from odoo.http import request


class WhatsAppWebhookController(http.Controller):
    @http.route("/primetech_whatsapp/webhook", type="http", auth="public", methods=["GET"], csrf=False)
    def verify(self, **params):
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        account = request.env["primetech.whatsapp.account"].sudo().search([("verify_token", "=", token), ("active", "=", True)], limit=1)
        return request.make_response(challenge or "", headers=[("Content-Type", "text/plain")], status=200 if account else 403)

    @http.route("/primetech_whatsapp/webhook", type="http", auth="public", methods=["POST"], csrf=False)
    def receive(self, **kwargs):
        # Meta sends a regular JSON HTTP body, not an Odoo JSON-RPC request.
        payload = request.httprequest.get_json(silent=True) or {}
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                account = request.env["primetech.whatsapp.account"].sudo().search([("phone_number_id", "=", metadata.get("phone_number_id")), ("active", "=", True)], limit=1)
                if not account:
                    continue
                for message in value.get("messages", []):
                    request.env["primetech.whatsapp.message"].sudo().receive_from_webhook(account, message.get("from"), message)
        return request.make_json_response({"ok": True})
