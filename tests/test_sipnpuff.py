# OWNER: P2
"""Bootstrap checks for sipnpuff.py: with no device nothing changes. TODO(P2): event detector on (t_ms, mv) pairs."""
from helm.sipnpuff import SipPuff


def test_no_device_is_silent():
    for port in (None, "off", "auto"):
        sip = SipPuff(port)
        sip.start()
        assert sip.connected is False and sip.level == 0.0 and sip.poll() == []
        sip.stop()
