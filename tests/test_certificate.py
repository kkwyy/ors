import random

import pytest

import ors
from ors.certificate import Certificate, model_fingerprint, verify_certificate

pytest.importorskip("highspy", reason="highspy backend not installed")


def make_infeasible() -> ors.Model:
    m = ors.Model("inf")
    x = m.add_var(lb=0, name="x")
    m.add_constr(x >= 2, name="demand")
    m.add_constr(x <= 1, name="capacity")
    return m


def test_certificate_built_and_verified():
    m = make_infeasible()
    diagnosis = m.diagnose()

    assert diagnosis.certificate is not None
    assert diagnosis.certificate.verified
    assert diagnosis.certificate.value < 0
    names = {t.name for t in diagnosis.certificate.terms}
    assert {"demand", "capacity"} <= names


def test_certificate_hash_matches_model():
    m = make_infeasible()
    diagnosis = m.diagnose()
    assert diagnosis.certificate.model_hash == model_fingerprint(m)
    assert diagnosis.certificate.model_hash.startswith("sha256:")


def test_certificate_json_roundtrip(tmp_path):
    m = make_infeasible()
    diagnosis = m.diagnose()
    path = tmp_path / "cert.json"
    diagnosis.certificate.to_json(str(path))

    loaded = Certificate.from_json(str(path))
    check = verify_certificate(m, loaded)
    assert check.verified, check.reason


def test_tampered_certificate_rejected():
    m = make_infeasible()
    diagnosis = m.diagnose()
    diagnosis.certificate.terms[0].multiplier = -1.0

    check = verify_certificate(m, diagnosis.certificate)
    assert not check.verified


def test_wrong_model_rejected():
    m = make_infeasible()
    diagnosis = m.diagnose()

    other = ors.Model("other")
    y = other.add_var(lb=0, name="y")
    other.add_constr(y >= 3, name="lo")
    other.add_constr(y <= 0, name="hi")

    check = verify_certificate(other, diagnosis.certificate)
    assert not check.verified
    assert "hash" in check.reason.lower()


def test_bounds_only_infeasibility():
    m = ors.Model("bounds")
    m.add_var(lb=5, ub=1, name="x")

    diagnosis = m.diagnose()
    assert diagnosis.status == "infeasible"
    assert diagnosis.iis is not None
    assert diagnosis.iis.constraints == []
    assert diagnosis.certificate is not None
    assert diagnosis.certificate.verified


def test_random_certificates():
    random.seed(11)
    for _ in range(10):
        m = ors.Model("rand")
        xs = [m.add_var(lb=0, ub=10, name=f"x{i}") for i in range(4)]
        for k in range(5):
            a = random.uniform(-2, 2)
            b = random.uniform(-2, 2)
            m.add_constr(a * xs[0] + b * xs[1] <= random.uniform(-3, 8), name=f"r{k}")
        m.add_constr(xs[0] >= 9, name="force_lo")
        m.add_constr(xs[0] <= 1, name="force_hi")

        diagnosis = m.diagnose()
        assert diagnosis.certificate is not None, diagnosis.summary()
        assert diagnosis.certificate.verified
