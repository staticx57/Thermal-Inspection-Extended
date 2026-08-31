"""
Regression coverage for a real bug found while first connecting the actual
Boson SDK to physical hardware (previously the SDK could never be located,
see test_boson_sdk_location.py): bosonGetCameraPN()/bosonGetSensorPN()
return an FLR_BOSON_(SENSOR_)PARTNUMBER_T object whose `.value` is a
fixed-width, null-padded list of raw character codes, not a string. Storing
that struct directly onto BosonInfo.camera_part_number broke
is_radiometric_capable(), which calls `.upper()` on it -- an AttributeError
silently swallowed by that method's broad except, always reporting
non-radiometric regardless of the real camera.
"""
import unittest

from thermal_inspection.sdk.boson_sdk_wrapper import BosonSDK


class _FakePartNumber:
    def __init__(self, value):
        self.value = value


class TestDecodePartNumber(unittest.TestCase):
    def test_decodes_null_padded_char_codes_to_string(self):
        # 'ABC' followed by SDK-style zero padding to a fixed width.
        codes = [ord(c) for c in "ABC"] + [0] * 17
        pn = _FakePartNumber(codes)
        self.assertEqual(BosonSDK._decode_part_number(pn), "ABC")

    def test_decodes_real_camera_part_number(self):
        # Observed on real hardware: 20320A016-6PAAX
        text = "20320A016-6PAAX"
        codes = [ord(c) for c in text] + [None] * (20 - len(text))
        pn = _FakePartNumber(codes)
        self.assertEqual(BosonSDK._decode_part_number(pn), text)

    def test_none_struct_returns_none(self):
        self.assertIsNone(BosonSDK._decode_part_number(None))

    def test_struct_without_value_attribute_returns_none(self):
        self.assertIsNone(BosonSDK._decode_part_number(object()))

    def test_fully_padded_struct_returns_empty_string(self):
        pn = _FakePartNumber([0] * 20)
        self.assertEqual(BosonSDK._decode_part_number(pn), "")


if __name__ == '__main__':
    unittest.main()
