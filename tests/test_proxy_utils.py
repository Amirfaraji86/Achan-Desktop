import unittest

from core.proxy import fragment_payload, parse_authority


class ProxyUtilityTests(unittest.TestCase):
    def test_parse_ipv4_authority(self):
        self.assertEqual(parse_authority("example.com:443"), ("example.com", 443))

    def test_parse_ipv6_authority(self):
        self.assertEqual(parse_authority("[2001:db8::1]:443"), ("2001:db8::1", 443))

    def test_fragment_small_payload_is_safe(self):
        data = b"abc"
        chunks = fragment_payload(data, 300)
        self.assertEqual(b"".join(chunks), data)
        self.assertTrue(all(chunks))

    def test_fragment_payload_preserves_all_bytes(self):
        data = bytes(range(256)) * 3
        chunks = fragment_payload(data, 300)
        self.assertEqual(b"".join(chunks), data)
        self.assertLessEqual(len(chunks), 300)


if __name__ == "__main__":
    unittest.main()
