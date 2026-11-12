"""Gradio demo skeleton (Role 6 Phase 1): upload, run, ticket display.

Shows the cached flag, stage timings, route reason and needs_human_review
for every run. Mock pipeline only: fixed fixture transcript and fields.

Run with ``src/svr/run_demo.sh`` (it unsets the proxy environment variables
first: this sandbox's ``no_proxy`` contains IPv6 entries that httpx, used
by Gradio at import time, cannot parse, so ``import gradio`` fails unless
they are unset). The plain HTML demo at GET / in the API needs no Gradio.
"""

from __future__ import annotations

import json
import os
import uuid

from .pipeline import run_pipeline
from .schemas import Ticket
from .stages.intake import validate_and_measure


def format_ticket_markdown(ticket: Ticket) -> str:
    """Ticket display for the demo: flags, route reason, timings."""
    cached = "YES, CACHED" if ticket.cached else "no (live mock run)"
    review = "YES, needs human review" if ticket.needs_human_review else "no"
    timings = ", ".join(f"{k}: {v} ms" for k, v in ticket.stage_timing_ms.items())
    return (
        f"## Ticket {ticket.id}\n\n"
        f"- **Status:** {ticket.ticket_status.value} | "
        f"**Assignment:** {ticket.assignment_status.value}\n"
        f"- **Cached:** {cached}\n"
        f"- **Needs human review:** {review}\n"
        f"- **Category:** {ticket.complaint_category} | "
        f"**Urgency:** {ticket.complaint_urgency} | "
        f"**Customer state (text):** {ticket.customer_state_text} | "
        f"**Churn:** {ticket.churn_risk}\n"
        f"- **Customer state (final, fused):** {ticket.customer_state_final} "
        f"(fusion disabled)\n"
        f"- **Route reason:** {ticket.route_reason}\n"
        f"- **Stage timings:** {timings}\n"
        f"- **Total processing:** {ticket.processing_ms} ms\n"
    )


def run_demo(file_path: str | None) -> tuple[str, str]:
    """Gradio callback: run the mock pipeline on the uploaded file.

    Bytes are read only to measure size and format, then discarded; the
    pipeline runs on the measured metadata. An invalid upload returns a
    clear error message instead of a ticket."""
    if not file_path:
        return "Upload an audio file first (WAV / MP3 / M4A, max 25 MB, 60 s).", ""
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as fh:
        data = fh.read()
    voicemail_id = f"voicemail-{uuid.uuid4().hex[:12]}"
    try:
        meta = validate_and_measure(data, filename, voicemail_id)
    except ValueError as exc:
        return f"Upload rejected: {exc}", ""
    finally:
        del data
    result = run_pipeline(meta, voicemail_id)
    return format_ticket_markdown(result.ticket), json.dumps(
        result.ticket.model_dump(), indent=2
    )


def build_demo() -> object:
    """Build the Gradio interface. Gradio is imported lazily so importing
    this module never fails when Gradio is unavailable."""
    import gradio as gr

    with gr.Blocks(title="SVR Phase 1 Demo (mock)") as demo:
        gr.Markdown(
            "# Smart Voicemail Router, Phase 1 Demo (MOCK)\n"
            "Upload a voicemail clip. The pipeline is a mock: fixed fixture "
            "transcript and fields, no real model, no real data."
        )
        audio = gr.Audio(type="filepath", label="Voicemail (WAV / MP3 / M4A)")
        run_btn = gr.Button("Run pipeline")
        summary = gr.Markdown(label="Ticket")
        raw = gr.Code(label="Ticket JSON", language="json")
        run_btn.click(fn=run_demo, inputs=audio, outputs=[summary, raw])
    return demo


def main() -> None:
    demo = build_demo()
    demo.launch(server_name="127.0.0.1", server_port=7860)


if __name__ == "__main__":
    main()
