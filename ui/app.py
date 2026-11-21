"""Farmer-facing crop insurance help. Backend owns calculations and approvals."""

from __future__ import annotations
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from ui.i18n import LANGUAGES, translate
except ModuleNotFoundError:
    from i18n import LANGUAGES, translate

LANGUAGE = "en"


def t(text):
    return translate(text, LANGUAGE)


IST = ZoneInfo("Asia/Kolkata")
API_BASE_URL = os.environ.get("FASALBIMA_API_URL", "http://127.0.0.1:8000").rstrip("/")
SOURCES = {
    "revamped_ogs_final.pdf": "https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf",
    "revised_operational_guidelines.pdf": "https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf",
    "pmfby_faq.html": "https://pmfby.gov.in/faq",
}


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        text = str(value).strip().replace(" IST", "+05:30").replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return (dt if dt.tzinfo else dt.replace(tzinfo=IST)).astimezone(IST)
    except ValueError:
        return None


def call_agent_api(
    query=None,
    thread_id=None,
    approved=None,
    calculation_id=None,
    agent_type="langgraph",
    execution_mode="backend",
    request_id=None,
    language=None,
):
    req = request_id or uuid.uuid4().hex
    payload = dict(
        query=query,
        thread_id=thread_id,
        approved=approved,
        calculation_id=calculation_id,
        agent_type="langgraph",
        request_id=req,
        language=language or st.session_state.get("language", "en"),
    )
    try:
        response = requests.post(f"{API_BASE_URL}/agent", json=payload, timeout=180)
        if response.ok:
            return response.json(), None, req
        return None, "We could not complete this request. Please try again.", req
    except requests.exceptions.Timeout:
        return (
            None,
            "Your answer is taking longer than expected. Use Try again to recover the same request.",
            req,
        )
    except requests.exceptions.RequestException:
        return None, "The service is not reachable right now. Please try again shortly.", req


def save_feedback_entry(thread_id, response_id, query, rating, comment=None):
    try:
        return requests.post(
            f"{API_BASE_URL}/feedback",
            json=dict(
                thread_id=thread_id,
                response_id=response_id,
                query=query,
                rating=rating,
                comment=comment,
            ),
            timeout=5,
        ).ok
    except requests.exceptions.RequestException:
        return False


def accept_result(result, question):
    st.session_state.pending_approval = (
        result.get("pending_calculation") if result.get("requires_approval") else None
    )
    for call in result.get("tool_calls", []):
        if call.get("tool") == "pmfby_premium" and call.get("output"):
            st.session_state.latest_estimate = call["output"]
    st.session_state.messages.append(
        dict(
            role="assistant",
            content=(
                t("Check the details below, then confirm or cancel the estimate.")
                if result.get("requires_approval")
                else result.get("answer", "")
            ),
            response_id=result.get("response_id", uuid.uuid4().hex),
            query=question,
            citations=result.get("citations", []),
            provider=result.get("provider", ""),
        )
    )


def submit(question=None, approved=None):
    pending = st.session_state.pending_approval or {}
    payload = dict(
        query=question,
        thread_id=st.session_state.thread_id,
        approved=approved,
        calculation_id=pending.get("id") if approved is not None else None,
        language=st.session_state.get("language", "en"),
    )
    if question:
        st.session_state.messages.append(dict(role="user", content=question))
    with st.spinner(t("Checking the official guidance…")):
        result, error, req = call_agent_api(**payload)
    if error:
        st.session_state.retry_request = dict(payload, request_id=req)
        st.session_state.service_error = error
    else:
        st.session_state.retry_request = None
        st.session_state.service_error = None
        accept_result(
            result, question or ("Calculate my premium" if approved else "Cancel calculation")
        )
    st.rerun()


st.set_page_config(
    page_title="FasalBima Sathi · Crop insurance help",
    page_icon=str(ROOT / "ui/assets/favicon.png"),
    layout="centered",
)
for key, default in dict(
    thread_id=uuid.uuid4().hex,
    messages=[],
    pending_approval=None,
    claim_clock_data=None,
    feedback_status={},
    retry_request=None,
    service_error=None,
    demo_mode=False,
    latest_estimate=None,
).items():
    if key not in st.session_state:
        st.session_state[key] = default

st.logo(str(ROOT / "ui/assets/logo.svg"), size="large", icon_image=str(ROOT / "ui/assets/mark.svg"))
header = st.columns([3, 1.3], vertical_alignment="center")
with header[0]:
    st.image(str(ROOT / "ui/assets/logo.svg"), width=290)
with header[1]:
    LANGUAGE = st.selectbox(
        "Language / भाषा",
        list(LANGUAGES),
        format_func=LANGUAGES.get,
        key="language",
        disabled=bool(st.session_state.pending_approval or st.session_state.retry_request),
    )
st.caption(t("Built for farmers. Independent guidance, not a government service."))
st.title(t("A helping hand for your harvest"))
st.markdown(t("Understand your crop cover, estimate your premium, and know when to report a loss."))
st.caption(
    t("Information from official guidelines. Your insurer and state decide coverage and claims.")
)
with st.container(horizontal=True):
    if st.button(t("Start a new conversation"), icon=":material/refresh:", key="reset"):
        st.session_state.thread_id = uuid.uuid4().hex
        for key in [
            "messages",
            "pending_approval",
            "retry_request",
            "service_error",
            "claim_clock_data",
            "feedback_status",
            "latest_estimate",
        ]:
            st.session_state[key] = (
                [] if key == "messages" else {} if key == "feedback_status" else None
            )
        st.rerun()
    st.link_button(
        t("Official PMFBY portal"), "https://pmfby.gov.in/", icon=":material/open_in_new:"
    )

section = st.segmented_control(
    t("How can we help?"),
    ["Ask a question", "Estimate premium", "Report crop loss"],
    default="Ask a question",
    key="section",
    format_func=t,
)
busy = bool(st.session_state.pending_approval or st.session_state.retry_request)
if st.session_state.service_error:
    st.warning(t(st.session_state.service_error))
if st.session_state.retry_request and st.button(t("Try again"), key="retry", type="primary"):
    payload = st.session_state.retry_request
    with st.spinner(t("Recovering your request…")):
        result, error, _ = call_agent_api(**payload)
    if error:
        st.session_state.service_error = error
    else:
        st.session_state.service_error = None
        st.session_state.retry_request = None
        accept_result(result, payload.get("query") or "Calculation confirmation")
    st.rerun()

if section == "Estimate premium":
    st.subheader(t("Estimate what you may pay"))
    st.caption(
        t(
            "Use the scale of finance from your bank or notified crop details. This is not a quotation or payment."
        )
    )
    if st.session_state.latest_estimate:
        estimate = st.session_state.latest_estimate
        with st.container(border=True):
            st.caption(t("Your latest estimate"))
            figures = st.columns(2)
            figures[0].metric(t("Sum insured"), f"₹{estimate['sum_insured']:,.2f}")
            figures[1].metric(
                t("Estimated maximum premium")
                if estimate.get("is_estimated_maximum")
                else t("Farmer premium"),
                f"₹{estimate['farmer_premium']:,.2f}",
            )
            st.caption(t("An estimate, not a payment or claim approval."))
    with st.form("premium_form"):
        crop = st.selectbox(
            t("Your crop"),
            [
                "Choose a crop",
                "Soybean",
                "Wheat",
                "Paddy",
                "Cotton",
                "Gram",
                "Mustard",
                "Maize",
                "Onion",
            ],
            key="crop",
            format_func=t,
        )
        season = st.selectbox(
            t("Growing season"), ["Choose a season", "Kharif", "Rabi"], key="season", format_func=t
        )
        cols = st.columns(2)
        area = cols[0].number_input(t("Land area"), min_value=0.0, value=0.0, step=0.1, key="area")
        unit = cols[1].selectbox(
            t("Area measured in"), ["Hectares", "Acres"], key="area_unit", format_func=t
        )
        cols = st.columns(2)
        finance = cols[0].number_input(
            t("Scale of finance (₹)"), min_value=0.0, value=0.0, step=1000.0, key="finance"
        )
        finance_unit = cols[1].selectbox(
            t("Finance amount is for"),
            ["One hectare", "One acre"],
            key="finance_unit",
            format_func=t,
        )
        calculate = st.form_submit_button(
            t("Review my estimate"), type="primary", disabled=busy, width="stretch"
        )
    if calculate:
        if crop == "Choose a crop" or season == "Choose a season" or not area or not finance:
            st.error(
                t(
                    "Please choose your crop and season, and enter an area and finance amount greater than zero."
                )
            )
        else:
            submit(
                f"Calculate {crop.lower()} premium in {season.lower()} for {area} {'ha' if unit == 'Hectares' else 'acres'} with scale of finance Rs {finance} per {'ha' if finance_unit == 'One hectare' else 'acre'}."
            )

if section == "Report crop loss":
    st.subheader(t("Know your reporting deadline"))
    st.info(
        "For the localized-calamity / post-harvest cases covered by the cited guidelines, the reporting window is 72 hours. Do not wait for this app to submit a claim: contact your insurer, bank or agriculture office."
    )
    with st.form("loss_form"):
        date = st.date_input(
            t("When did the loss happen?"),
            value=None,
            max_value=datetime.now(IST).date(),
            key="loss_date",
        )
        clock = st.time_input(
            t("Approximate time of loss (India time)"), value=None, key="loss_time"
        )
        check = st.form_submit_button(t("Show my deadline"), type="primary", width="stretch")
    if check:
        if date is None or clock is None:
            st.error(
                t("Please enter both the date and the approximate time. We will not guess either.")
            )
        else:
            try:
                result = requests.post(
                    f"{API_BASE_URL}/claim-clock",
                    json={"loss_timestamp": datetime.combine(date, clock).isoformat()},
                    timeout=10,
                )
                if result.ok:
                    st.session_state.claim_clock_data = result.json()
                else:
                    st.error(
                        t("Please check the loss date and time. It must not be in the future.")
                    )
            except requests.exceptions.RequestException:
                st.error(
                    "The deadline service is unavailable. Please report urgent losses directly to your insurer."
                )

    @st.fragment(run_every="5s")
    def render_clock():
        data = st.session_state.claim_clock_data
        if not data:
            return
        deadline = parse_iso_datetime(data.get("deadline_timestamp"))
        if deadline is None:
            st.error(t("The deadline could not be read. Please check the event again."))
            return
        seconds = int((deadline - datetime.now(IST)).total_seconds())
        with st.container(border=True):
            if seconds <= 0:
                st.warning(
                    "The calculated reporting window has passed. Contact your insurer or agriculture office promptly for guidance. This app cannot decide claim eligibility."
                )
            else:
                st.metric(
                    t("Time left to report"),
                    f"{seconds // 3600}h {(seconds % 3600) // 60}m {seconds % 60}s",
                )
            st.markdown(f"**{t('Report by')} {deadline:%d %b %Y, %I:%M %p} IST**")
            st.caption(data.get("og_version", "See official guidelines for applicable conditions."))
            st.markdown(t("**Ways to report**"))
            for channel in data.get("reporting_channels", []):
                st.markdown(f"- {t(channel)}")
            st.link_button(t("Read the official guidelines"), SOURCES["revamped_ogs_final.pdf"])

    render_clock()
    with st.expander(t("Keep these ready"), expanded=True):
        for item in [
            "Crop and field location",
            "Date, time and type of loss",
            "Policy/application reference, if available",
            "Photos of the damage, if safe to take",
            "Insurer or bank contact and reporting acknowledgement",
        ]:
            st.checkbox(t(item), key="ready_" + item)
        st.caption(t("This is a personal checklist, not a submitted claim."))
    if st.session_state.claim_clock_data:
        data = st.session_state.claim_clock_data
        note = "\n".join(
            [
                t("This is a personal checklist, not a submitted claim."),
                str(data.get("loss_timestamp", "")),
                t("Report by") + ": " + str(data.get("deadline_timestamp", "")),
                *[t(c) for c in data.get("reporting_channels", [])],
                *[
                    t(c)
                    for c in [
                        "Crop and field location",
                        "Date, time and type of loss",
                        "Policy/application reference, if available",
                        "Photos of the damage, if safe to take",
                    ]
                ],
            ]
        )
        st.download_button(
            t("Download my reporting note"),
            note.encode("utf-8-sig"),
            file_name="crop-loss-note.txt",
            mime="text/plain",
            key="download_note",
        )

if section == "Ask a question" and not st.session_state.messages:
    st.subheader(t("What would you like to know?"))
    st.caption(t("Ask in your own words. For example:"))
    with st.container(horizontal=True):
        for index, (label, question) in enumerate(
            [
                ("What does insurance cover?", "Which crop losses are covered under PMFBY?"),
                ("How much is the premium?", "What are the farmer premium rates under PMFBY?"),
                (
                    "How do I report a loss?",
                    "How do I report localized hailstorm damage under PMFBY?",
                ),
            ]
        ):
            if st.button(t(label), key=f"example_{index}", disabled=busy):
                submit(question)

for index, message in enumerate(st.session_state.messages):
    with st.chat_message(
        message["role"],
        avatar=":material/agriculture:" if message["role"] == "assistant" else ":material/person:",
    ):
        st.markdown(message["content"])
        if message.get("citations"):
            with st.expander(t("Read the official sources")):
                seen = set()
                for number, citation in enumerate(message["citations"], 1):
                    source = citation.get("source") or citation.get("source_url", "")
                    url = (
                        source if source.startswith("https://") else SOURCES.get(Path(source).name)
                    )
                    page = citation.get("page")
                    title = (
                        citation.get("title") or citation.get("rule_topic") or "PMFBY guidelines"
                    )
                    target = f"{url}#page={page}" if url and page and ".pdf" in url.lower() else url
                    if target and target not in seen:
                        st.link_button(
                            f"[{number}] {title}" + (f" · page {page}" if page else ""), target
                        )
                        seen.add(target)
        if message["role"] == "assistant" and message.get("response_id"):
            response_id = message["response_id"]
            vote = st.feedback("thumbs", key=f"vote_{response_id}_{index}")
            if vote is not None and st.session_state.feedback_status.get(response_id) != vote:
                if save_feedback_entry(
                    st.session_state.thread_id,
                    response_id,
                    message.get("query", ""),
                    "up" if vote else "down",
                ):
                    st.session_state.feedback_status[response_id] = vote
                    st.caption(t("Thank you. Your feedback has been saved."))
                else:
                    st.caption(t("Feedback could not be saved. Please try again."))

pending = st.session_state.pending_approval
if pending:
    params = pending.get("params", {})
    with st.container(border=True):
        st.subheader(t("Are these details correct?"))
        st.markdown(
            f"**{t('Your crop')}:** {t(str(params.get('crop', '')).title())}  ·  **{t('Growing season')}:** {t(str(params.get('season') or 'as applicable').title())}"
        )
        st.markdown(
            f"**{t('Land area')}:** {params.get('area')} {t('Hectares' if params.get('area_unit', 'ha') == 'ha' else 'Acres')}"
        )
        st.markdown(
            f"**Scale of finance:** ₹{params.get('scale_of_finance', 0):,.2f} {'per acre' if params.get('scale_of_finance_unit') == 'per_acre' else 'per hectare'}"
        )
        st.caption(
            t(
                "Confirmation only calculates an estimate. It does not buy insurance, take payment or submit a claim."
            )
        )
        columns = st.columns(2)
        if columns[0].button(
            t("Yes, calculate my estimate"),
            key="approve",
            type="primary",
            disabled=bool(st.session_state.retry_request),
            width="stretch",
        ):
            submit(approved=True)
        if columns[1].button(
            t("Cancel"),
            key="cancel",
            disabled=bool(st.session_state.retry_request),
            width="stretch",
        ):
            submit(approved=False)

if section == "Ask a question":
    question = st.chat_input(t("Ask about your crop insurance…"), disabled=busy, key="question")
    if question:
        submit(question)
st.divider()
st.caption(
    t(
        "We cannot check your personal claim status or bank payments. Never share an Aadhaar number, account number, OTP or API key here."
    )
)
