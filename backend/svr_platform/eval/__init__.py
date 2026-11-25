"""Production evaluation CLI and SHA-256 test-once guard for SVR (AI9, AI10, WF5, D5)."""

from .once_guard import (
    GuardClaim,
    TestOnceGuardError,
    claim_test_evaluation,
    compute_checkpoint_set_sha256,
    compute_file_sha256,
    finalize_test_claim,
    guarded_read_test_file,
    load_test_ledger,
)

__all__ = [
    "GuardClaim",
    "TestOnceGuardError",
    "claim_test_evaluation",
    "compute_checkpoint_set_sha256",
    "compute_file_sha256",
    "finalize_test_claim",
    "guarded_read_test_file",
    "load_test_ledger",
]
