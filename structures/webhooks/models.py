from django.db import models
from django.utils.translation import gettext_lazy as _

from .core import DiscordWebhookMixin
from .managers import WebhookBaseManager


class WebhookBase(DiscordWebhookMixin, models.Model):
    """Base model for a Webhook"""

    class PingType(models.TextChoices):
        NONE = "NO", _("none")
        HERE = "HE", _("here")
        EVERYONE = "EV", _("everyone")

    class Color(models.IntegerChoices):
        DANGER = 0xD9534F, _("danger")
        INFO = 0x5BC0DE, _("info")
        SUCCESS = 0x5CB85C, _("success")
        WARNING = 0xF0AD4E, _("warning")

        @property
        def css_color(self) -> str:
            return f"#{self.value:X}"

    TYPE_DISCORD = 1

    TYPE_CHOICES = [
        (TYPE_DISCORD, _("Discord Webhook")),
    ]

    name = models.CharField(
        max_length=64, unique=True, help_text="short name to identify this webhook"
    )
    url = models.CharField(
        max_length=255,
        unique=True,
        help_text=(
            "URL of this webhook, e.g. "
            "https://discordapp.com/api/webhooks/123456/abcdef"
        ),
    )
    notes = models.TextField(
        null=True,
        default=None,
        blank=True,
        help_text="you can add notes about this webhook here if you want",
    )
    webhook_type = models.IntegerField(
        choices=TYPE_CHOICES, default=TYPE_DISCORD, help_text="type of this webhook"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="whether notifications are currently sent to this webhook",
    )

    objects = WebhookBaseManager()

    class Meta:
        abstract = True
