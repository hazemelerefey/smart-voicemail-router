"""Tests for Module 1: schema, tenant isolation fields, Fernet encryption, and seed integrity."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from svr_platform.crypto import EncryptionService
from svr_platform.models import Agent, Organization, ScriptTemplate, SkillMapping, SystemSetting
from svr_platform.taxonomy import ComplaintCategory


def test_seed_creates_all_11_mappings_templates_and_3_agents(db_manager):
    with db_manager.session_factory() as db:
        org = db.scalar(select(Organization))
        assert org is not None
        assert org.name == "Egypt Telecom Care"

        agents = db.scalars(
            select(Agent).where(Agent.organization_id == org.id).order_by(Agent.seed_order.asc())
        ).all()
        assert [a.name for a in agents] == [
            "Network Care Specialist",
            "Billing & Bundles Specialist",
            "Subscriber Care Specialist",
        ]
        assert all(a.capacity == 5 and a.current_load == 0 and a.available and a.active for a in agents)

        mappings = db.scalars(select(SkillMapping).where(SkillMapping.organization_id == org.id)).all()
        mapped_categories = {m.category for m in mappings}
        assert mapped_categories == {c.value for c in ComplaintCategory}

        # Verify FR20 exact mapping
        by_cat = {m.category: m.skill_name for m in mappings}
        assert by_cat["sim_services"] == "Network"
        assert by_cat["offers_and_packages"] == "Billing"
        assert by_cat["cancellation_request"] == "General"

        templates = db.scalars(
            select(ScriptTemplate).where(ScriptTemplate.organization_id == org.id)
        ).all()
        assert {t.category for t in templates} == {c.value for c in ComplaintCategory}

        setting = db.get(SystemSetting, org.id)
        assert setting is not None
        assert setting.confidence_threshold == 0.5
        assert setting.auto_routing_enabled is True
        assert setting.retention_days == 90


def test_encryption_at_rest_roundtrip(test_settings, tmp_path: Path):
    crypto = EncryptionService(test_settings.svr_encryption_key)
    raw_audio = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x01\x02\x03\x04" * 25
    target = tmp_path / "encrypted.bin"
    crypto.write_encrypted_file(target, raw_audio)

    on_disk = target.read_bytes()
    assert on_disk != raw_audio
    assert b"RIFF" not in on_disk
    assert crypto.read_encrypted_file(target) == raw_audio
