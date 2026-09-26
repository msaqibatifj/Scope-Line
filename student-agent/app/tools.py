"""Sandbox tools for PacketPilot, a scholarship packet readiness agent."""
from __future__ import annotations

import re
from datetime import date, datetime
from time import perf_counter
from typing import Any

from app.models import DocumentAssessment, EligibilityAssessment, PacketFacts

DOCUMENT_ALIASES = {
    'transcript': ['transcript', 'grade report', 'marksheet', 'mark sheet'],
    'cnic copy': ['cnic', 'national id', 'identity card', 'id card'],
    'recommendation letter': ['recommendation letter', 'reference letter', 'referee letter', 'lor'],
    'personal statement': ['personal statement', 'statement of purpose', 'sop', 'motivation letter'],
    'resume': ['resume', 'cv', 'curriculum vitae'],
    'income certificate': ['income certificate', 'salary certificate', 'financial certificate'],
    'enrollment certificate': ['enrollment certificate', 'bonafide certificate', 'student certificate'],
    'portfolio': ['portfolio'],
    'essay': ['essay'],
}

INJECTION_PATTERNS = [
    'ignore previous', 'ignore all previous', 'developer message', 'system prompt',
    'override instructions', 'disregard instructions', 'you are now', 'reveal your prompt',
]

MONTHS = '|'.join([
    'jan', 'january', 'feb', 'february', 'mar', 'march', 'apr', 'april', 'may',
    'jun', 'june', 'jul', 'july', 'aug', 'august', 'sep', 'sept', 'september',
    'oct', 'october', 'nov', 'november', 'dec', 'december',
])


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _contains_any(text: str, phrases: list[str]) -> bool:
    return any(re.search(r'\b' + re.escape(phrase) + r'\b', text) for phrase in phrases)


def _sentence_windows(text: str) -> list[str]:
    chunks = re.split(r'[\n.;]+', text)
    return [chunk.strip().lower() for chunk in chunks if chunk.strip()]


def _extract_documents(text: str) -> tuple[list[str], list[str], list[str]]:
    required: list[str] = []
    provided: list[str] = []
    explicitly_missing: list[str] = []
    windows = _sentence_windows(text)
    required_markers = ['required', 'requires', 'need', 'needs', 'must include', 'mandatory', 'submit', 'include']
    provided_markers = ['i have', 'have', 'attached', 'provided', 'available', 'yes', 'submitted']
    missing_markers = ['missing', 'do not have', "don't have", 'no ', 'not available', 'without']

    for canonical, aliases in DOCUMENT_ALIASES.items():
        for window in windows:
            if not _contains_any(window, aliases):
                continue
            if any(marker in window for marker in missing_markers):
                explicitly_missing.append(canonical)
            elif any(marker in window for marker in required_markers):
                required.append(canonical)
            elif any(marker in window for marker in provided_markers):
                provided.append(canonical)
            else:
                required.append(canonical)
    return _unique(required), _unique(provided), _unique(explicitly_missing)


def _extract_cgpa(text: str) -> tuple[float | None, float | None]:
    lowered = text.lower()
    applicant = None
    minimum = None
    for match in re.finditer(r'(?:cgpa|gpa)[^0-9]{0,20}(\d(?:\.\d{1,2})?)', lowered):
        value = float(match.group(1))
        before = lowered[max(0, match.start() - 35):match.start()]
        after = lowered[match.end():match.end() + 35]
        if any(token in before + after for token in ['>=', 'above', 'minimum', 'min', 'at least', 'greater than', 'require']):
            minimum = value if minimum is None else max(minimum, value)
        elif applicant is None:
            applicant = value
    for match in re.finditer(r'(?:above|minimum|min|at least|>=)\s*(\d(?:\.\d{1,2})?)', lowered):
        nearby = lowered[max(0, match.start() - 25):match.end() + 25]
        if 'cgpa' in nearby or 'gpa' in nearby:
            value = float(match.group(1))
            minimum = value if minimum is None else max(minimum, value)
    return applicant, minimum


def _extract_deadline(text: str) -> str | None:
    patterns = [
        rf'({MONTHS})\s+(\d{{1,2}})(?:,?\s*(20\d{{2}}))?',
        rf'(\d{{1,2}})\s+({MONTHS})(?:,?\s*(20\d{{2}}))?',
        r'(20\d{2})-(\d{1,2})-(\d{1,2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(0)
    return None


def _parse_deadline(raw: str | None, today: date) -> date | None:
    if not raw:
        return None
    raw = raw.strip().replace(',', '')
    for fmt in ['%B %d %Y', '%b %d %Y', '%d %B %Y', '%d %b %Y', '%Y-%m-%d']:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    for fmt in ['%B %d', '%b %d', '%d %B', '%d %b']:
        try:
            parsed = datetime.strptime(raw, fmt).date().replace(year=today.year)
            if parsed < today:
                parsed = parsed.replace(year=today.year + 1)
            return parsed
        except ValueError:
            pass
    return None


def extract_packet_info(task: str, external_context: list[dict[str, Any]], history_text: str = '') -> PacketFacts:
    trusted_text = f'{history_text}\n{task}'
    untrusted_text = '\n'.join(item.get('content', '') for item in external_context)
    combined = f'{trusted_text}\n{untrusted_text}'
    required, provided, explicitly_missing = _extract_documents(combined)
    applicant_cgpa, min_cgpa = _extract_cgpa(combined)
    deadline = _extract_deadline(combined)
    warnings = []
    if untrusted_text and any(pattern in untrusted_text.lower() for pattern in INJECTION_PATTERNS):
        warnings.append('Untrusted external content contained instruction-like text and was treated only as data.')
    if explicitly_missing:
        warnings.append('Some documents were explicitly marked unavailable by the user.')
    profile = {}
    requirements = {}
    if applicant_cgpa is not None:
        profile['cgpa'] = applicant_cgpa
    if min_cgpa is not None:
        requirements['min_cgpa'] = min_cgpa
    return PacketFacts(
        required_documents=required,
        provided_documents=_unique([doc for doc in provided if doc not in explicitly_missing]),
        missing_documents=explicitly_missing,
        eligibility_requirements=requirements,
        applicant_profile=profile,
        deadline=deadline,
        warnings=warnings,
        untrusted_instruction_count=sum(1 for pattern in INJECTION_PATTERNS if pattern in untrusted_text.lower()),
    )


def assess_eligibility(facts: PacketFacts, today: date | None = None) -> EligibilityAssessment:
    today = today or date.today()
    reasons: list[str] = []
    missing: list[str] = []
    eligible: bool | None = True
    min_cgpa = facts.eligibility_requirements.get('min_cgpa')
    cgpa = facts.applicant_profile.get('cgpa')
    if min_cgpa is not None:
        if cgpa is None:
            missing.append('applicant CGPA')
            eligible = None
        elif cgpa < min_cgpa:
            eligible = False
            reasons.append(f'CGPA {cgpa:g} is below the required {min_cgpa:g}.')
        else:
            reasons.append(f'CGPA {cgpa:g} meets the required {min_cgpa:g}.')
    else:
        missing.append('eligibility threshold such as minimum CGPA')
        eligible = None

    deadline_date = _parse_deadline(facts.deadline, today)
    deadline_risk = 'unknown'
    if facts.deadline and deadline_date:
        days = (deadline_date - today).days
        if days < 0:
            deadline_risk = 'passed'
            eligible = False
            reasons.append(f'Deadline {facts.deadline} has passed.')
        elif days <= 3:
            deadline_risk = 'urgent'
            reasons.append(f'Deadline {facts.deadline} is urgent.')
        else:
            deadline_risk = 'ok'
            reasons.append(f'Deadline {facts.deadline} is still open.')
    elif not facts.deadline:
        missing.append('application deadline')
        if eligible is True:
            eligible = None
    return EligibilityAssessment(eligible=eligible, reasons=reasons, missing_information=_unique(missing), deadline_risk=deadline_risk)


def check_required_documents(facts: PacketFacts) -> DocumentAssessment:
    required = facts.required_documents
    provided = facts.provided_documents
    missing = _unique(facts.missing_documents + [doc for doc in required if doc not in provided])
    uncertain = [] if required else ['required document list']
    return DocumentAssessment(
        ready=bool(required) and not missing,
        required_documents=required,
        provided_documents=provided,
        missing_documents=missing,
        uncertain_documents=uncertain,
    )


def build_readiness_report(facts: PacketFacts, eligibility: EligibilityAssessment, documents: DocumentAssessment) -> dict[str, Any]:
    if eligibility.eligible is False:
        readiness = 'blocked'
    elif eligibility.missing_information:
        readiness = 'needs_clarification'
    elif documents.ready:
        readiness = 'ready'
    else:
        readiness = 'not_ready'
    next_steps = []
    if eligibility.missing_information:
        next_steps.append('Provide ' + ', '.join(eligibility.missing_information) + '.')
    if documents.missing_documents:
        next_steps.append('Collect missing document(s): ' + ', '.join(documents.missing_documents) + '.')
    if not next_steps and readiness == 'ready':
        next_steps.append('Review the packet once more before submitting through the official portal.')
    return {
        'readiness': readiness,
        'required_documents': documents.required_documents,
        'provided_documents': documents.provided_documents,
        'missing_documents': documents.missing_documents,
        'eligibility_reasons': eligibility.reasons,
        'missing_information': eligibility.missing_information + documents.uncertain_documents,
        'deadline_risk': eligibility.deadline_risk,
        'warnings': facts.warnings,
        'next_steps': next_steps,
    }

TOOLS = {
    'extract_packet_info': extract_packet_info,
    'assess_eligibility': assess_eligibility,
    'check_required_documents': check_required_documents,
    'build_readiness_report': build_readiness_report,
}


def timed_call(tool_name: str, **kwargs: Any) -> tuple[Any, float]:
    started = perf_counter()
    result = TOOLS[tool_name](**kwargs)
    return result, (perf_counter() - started) * 1000
