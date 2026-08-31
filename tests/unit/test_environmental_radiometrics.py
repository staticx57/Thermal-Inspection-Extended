import numpy as np
from thermal_inspection.processing.radiometric_converter import TLinearConverter


def test_environmental_parameter_setting():
    converter = TLinearConverter()
    converter.set_environmental_parameters(
        emissivity=0.85,
        distance_m=3.5,
        atmospheric_temp_c=22.0,
        reflected_temp_c=25.0,
        transmission=0.90,
        enable=True,
    )
    assert converter.emissivity == 0.85
    assert converter.distance_m == 3.5
    assert converter.atmospheric_temp_c == 22.0
    assert converter.reflected_temp_c == 25.0
    assert converter.atmospheric_transmission == 0.90
    assert converter.enable_environmental_compensation is True


def test_environmental_compensation_math():
    converter = TLinearConverter()

    # Disabled compensation should return identical temperature
    apparent_temp = 50.0
    assert converter.apply_environmental_compensation(apparent_temp) == 50.0

    # Enable compensation with lower emissivity
    converter.set_environmental_parameters(
        emissivity=0.80,
        reflected_temp_c=20.0,
        atmospheric_temp_c=20.0,
        transmission=1.0,
        enable=True,
    )

    # Surface emitting less radiation (emissivity 0.8) for an apparent 50°C reading
    # means the true object surface must be warmer than 50°C!
    compensated_temp = converter.apply_environmental_compensation(apparent_temp)
    assert compensated_temp > apparent_temp


def test_vectorized_frame_environmental_compensation():
    converter = TLinearConverter()
    converter.set_environmental_parameters(
        emissivity=0.80,
        reflected_temp_c=20.0,
        atmospheric_temp_c=20.0,
        transmission=0.95,
        enable=True,
    )

    frame_16bit = np.full((10, 10), 30000, dtype=np.uint16)
    temp_frame = converter.convert_frame(frame_16bit)

    assert temp_frame.shape == (10, 10)
    assert temp_frame.dtype == np.float32
    assert not np.isnan(temp_frame).any()
