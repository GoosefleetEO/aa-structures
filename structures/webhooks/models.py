"""Models for webhooks."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from .core import DiscordWebhookMixin
from .managers import WebhookBaseManager


class WebhookBase(DiscordWebhookMixin, models.Model):
    """Base model for a Webhook"""

    class PingType(models.TextChoices):
        """A ping type for webhooks."""

        NONE = "NO", _("none")
        HERE = "HE", _("here")
        EVERYONE = "EV", _("everyone")

    class Color(models.IntegerChoices):
        """A color for embeds."""

        DANGER = 0xD9534F, _("danger")
        INFO = 0x5BC0DE, _("info")
        SUCCESS = 0x5CB85C, _("success")
        WARNING = 0xF0AD4E, _("warning")

        @property
        def css_color(self) -> str:
            """Return color as CSS value."""
            return f"#{self.value:X}"

    TYPE_DISCORD = 1

    TYPE_CHOICES = [
        (TYPE_DISCORD, _("Discord Webhook")),
    ]

    name = models.CharField(
        verbose_name=_("name"),
        max_length=64,
        unique=True,
        help_text=_("Short name to identify this webhook"),
    )
    url = models.CharField(
        verbose_name=_("url"),
        max_length=255,
        unique=True,
        help_text=_(
            "URL of this webhook, e.g. "
            "https://discordapp.com/api/webhooks/123456/abcdef"
        ),
    )
    notes = models.TextField(
        verbose_name=_("notes"),
        null=True,
        default=None,
        blank=True,
        help_text=_("Notes regarding this webhook"),
    )
    webhook_type = models.IntegerField(
        verbose_name=_("webhook type"),
        choices=TYPE_CHOICES,
        default=TYPE_DISCORD,
        help_text=_("Type of this webhook"),
    )
    is_active = models.BooleanField(
        verbose_name=_("is active"),
        default=True,
        help_text=_("Whether notifications are currently sent to this webhook"),
    )

    objects = WebhookBaseManager()

    class Meta:
        abstract = True
