# PrimeTech WhatsApp Connect

Connects Odoo Community to one or more WhatsApp Business accounts through the
official Meta WhatsApp Cloud API. It does not automate WhatsApp Web.

## Initial configuration

1. Install the module and open **WhatsApp > Configuration**.
2. Create one account per Meta phone number: enter the phone-number ID, a
   long-lived access token and a private verification token.
3. In Meta Developers, configure the callback URL as:
   `https://your-odoo-domain/primetech_whatsapp/webhook`.
4. Subscribe the Meta application to `messages` webhooks.

The callback URL must be publicly accessible through HTTPS. Meta template and
24-hour customer-care window policies continue to apply to all outbound
messages; approved templates should be added before initiating conversations
outside that window.
