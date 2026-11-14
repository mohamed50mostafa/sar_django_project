"""Pure-math/numpy tests for scenes.geotiff_builder (no rasterio needed).

These run under plain unittest (and under pytest/pytest-django) because
estimate_bytes/plan_downsample/build_band_stack never import rasterio or
Django -- only build_rgb_like_geotiff (which actually writes a file) does.
"""
import unittest

import numpy as np

from scenes.geotiff_builder import (
    BAND_COUNT,
    DEFAULT_MAX_BYTES,
    build_band_stack,
    estimate_bytes,
    plan_downsample,
    stretch_to_uint8,
)


class EstimateBytesTests(unittest.TestCase):
    def test_zero_or_negative_dims_are_zero(self):
        self.assertEqual(estimate_bytes(0, 100), 0)
        self.assertEqual(estimate_bytes(100, -1), 0)

    def test_matches_width_height_bands(self):
        self.assertEqual(estimate_bytes(10, 20, band_count=3, bytes_per_pixel=1), 10 * 20 * 3)


class PlanDownsampleTests(unittest.TestCase):
    def test_small_raster_is_not_downsampled(self):
        plan = plan_downsample(512, 512, max_bytes=DEFAULT_MAX_BYTES)
        self.assertEqual(plan.scale, 1.0)
        self.assertEqual((plan.out_width, plan.out_height), (512, 512))

    def test_large_raster_is_downsampled_under_budget(self):
        # A typical Sentinel-1 IW GRD scene is roughly this size.
        plan = plan_downsample(25000, 17000, max_bytes=DEFAULT_MAX_BYTES)
        self.assertLess(plan.scale, 1.0)
        self.assertLessEqual(plan.estimated_compressed_bytes, DEFAULT_MAX_BYTES)
        self.assertGreater(plan.out_width, 0)
        self.assertGreater(plan.out_height, 0)

    def test_isotropic_scaling_preserves_aspect_ratio(self):
        plan = plan_downsample(30000, 10000, max_bytes=DEFAULT_MAX_BYTES)
        self.assertAlmostEqual(plan.out_width / plan.out_height, 30000 / 10000, places=2)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            plan_downsample(0, 100)
        with self.assertRaises(ValueError):
            plan_downsample(100, 100, max_bytes=0)


class BandStackTests(unittest.TestCase):
    def test_always_returns_three_bands(self):
        rng = np.random.default_rng(1)
        vv = rng.exponential(50, size=(64, 64)).astype("float32")
        vh = rng.exponential(20, size=(64, 64)).astype("float32")
        stack = build_band_stack(vv, vh)
        self.assertEqual(stack.shape[0], BAND_COUNT)
        self.assertEqual(stack.dtype, np.uint8)

    def test_single_polarization_falls_back_to_three_identical_bands(self):
        rng = np.random.default_rng(2)
        vv = rng.exponential(50, size=(32, 32)).astype("float32")
        stack = build_band_stack(vv, None)
        self.assertEqual(stack.shape[0], BAND_COUNT)
        self.assertTrue(np.array_equal(stack[0], stack[1]))
        self.assertTrue(np.array_equal(stack[1], stack[2]))

    def test_stretch_handles_constant_band_without_crashing(self):
        flat = np.full((8, 8), 5.0, dtype="float32")
        out = stretch_to_uint8(flat)
        self.assertEqual(out.shape, (8, 8))

    def test_stretch_handles_all_nan_band(self):
        nan_band = np.full((4, 4), np.nan, dtype="float32")
        out = stretch_to_uint8(nan_band)
        self.assertTrue(np.all(out == 0))


if __name__ == "__main__":
    unittest.main()
