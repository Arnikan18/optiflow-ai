from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class DeliveryResult:
    success: bool
    provider_reference: str | None = None
    failure_reason: str | None = None


def simulate_delivery(*, notification_id: str, recipient: str, channel: str) -> DeliveryResult:
    mode = get_settings().simulated_delivery_mode.strip().lower()
    provider_reference = f"SIM-{channel}-{notification_id}"

    if mode == "success":
        return DeliveryResult(success=True, provider_reference=provider_reference)
    if mode == "fail":
        return DeliveryResult(success=False, failure_reason="Simulated delivery failed")
    if mode == "recipient_rule":
        if "fail" in recipient.lower():
            return DeliveryResult(success=False, failure_reason="Simulated delivery failed")
        return DeliveryResult(success=True, provider_reference=provider_reference)

    raise RuntimeError("Unsupported simulated delivery mode")
