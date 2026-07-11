"""TDD tests for new_vehicle.py — scaffold a vehicle directory at onboarding."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import new_vehicle as nv


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(nv.slugify("Toyota", "Tacoma", 1995), "1995-toyota-tacoma")

    def test_spaces_and_case(self):
        self.assertEqual(nv.slugify("Land Rover", "Range Rover", 2003), "2003-land-rover-range-rover")


class TestScaffold(unittest.TestCase):
    def test_creates_vehicle_json_with_clocks(self):
        root = Path(tempfile.mkdtemp())
        vdir = nv.scaffold_vehicle(root, make="Honda", model="Civic", year=2015, fuel="gasoline")
        vj = json.loads((vdir / "vehicle.json").read_text())
        self.assertEqual(vj["slug"], "2015-honda-civic")
        self.assertEqual(vj["clocks"][0]["kind"], "odometer")
        self.assertTrue((vdir / "events").is_dir())
        self.assertTrue((vdir / "knowledge").is_dir())

    def test_idempotent_refuses_existing(self):
        root = Path(tempfile.mkdtemp())
        nv.scaffold_vehicle(root, make="Honda", model="Civic", year=2015)
        with self.assertRaises(FileExistsError):
            nv.scaffold_vehicle(root, make="Honda", model="Civic", year=2015)


if __name__ == "__main__":
    unittest.main()
