"""Separate user operations from client data and retain unresolved goal fields."""
import re
from pydantic import BaseModel, ConfigDict


class PendingGoal(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    instruction: str
    project_id: str | None = None
    request_id: str | None = None
    request_text: str | None = None


def instruction_text(text: str) -> str:
    # Client speech, quoted text and colon-delimited request bodies are data.
    prefix = re.split(r'\b(?:the\s+)?client\s+(?:says?|said|requests?|asked)\b', text, maxsplit=1, flags=re.I)[0]
    if ':' in prefix:
        prefix = prefix.split(':', 1)[0]
    return re.sub(r'"[^"]*"|“[^”]*”', ' ', prefix)


def operations(text: str) -> list[str]:
    text = instruction_text(text).lower()
    result = []
    if re.search(r'\b(list|show|display|enumerate|browse)\b.{0,35}\bprojects\b|\b(project inventory|available projects)\b', text):
        result.append('list')
    if re.search(r'\b(inspect|show|view|review|read|examine|display|look at)\b.{0,35}\b(agreement|contract)\b|\b(agreed scope|what is included)\b', text):
        result.append('inspect')
    draft = bool(re.search(r'\b(draft|prepare|write|create)\b.{0,35}\b(draft|change request|scope (?:change )?note|proposal)\b|\bdraft\b', text))
    if draft or re.search(r'\b(analy[sz]e|assess|compare|evaluate|check|scope|drift)\b', text):
        # "agreed scope" by itself is an inspection rather than a second operation.
        if draft or not ('inspect' in result and not re.search(r'\b(analy[sz]e|assess|compare|evaluate|check|drift)\b', text)):
            result.append('analyze')
    if draft:
        result.append('draft')
    return result


def ids(text: str, prefix: str) -> list[str]:
    return list(dict.fromkeys(f'{prefix}-{m.group(1)}' for m in re.finditer(rf'\b{prefix}[-\s]?(\d{{3}})\b', instruction_text(text), re.I)))


def inline_request(text: str) -> str | None:
    if 'analyze' not in operations(text):
        return None
    speech = re.search(r'\b(?:the\s+)?client\s+(?:says?|said|requests?|asked)\b\s*:?', text, re.I)
    if speech:
        body = text[speech.end():].strip()
    elif ':' in text:
        body = text.split(':', 1)[1].strip()
    else:
        body = re.sub(r'\b(?:project|request)[-\s]?\d{3}\b', ' ', text, flags=re.I)
        body = re.sub(r'\b(?:change request|scope change note|client request|can you|in scope|out of scope)\b', ' ', body, flags=re.I)
        body = re.sub(r'\b(?:please|analy[sz]e|assess|compare|evaluate|check|review|scope|drift|for|against|draft|prepare|write|create|a|an|the|and|then|of|whether|is|it)\b', ' ', body, flags=re.I)
    body = body.strip(' \t\n:.,"“”')
    body = re.sub(r'\s+', ' ', body)
    return body if re.search(r'\w', body) else None


def forbidden_action(text: str) -> bool:
    text = instruction_text(text).lower()
    # Negation is scoped to its clause rather than subsequent independent actions.
    for clause in re.split(r'[;.!?]|\b(?:but|then)\b', text):
        pattern = r'\b(send|email|e-mail|dispatch|forward|contact|message|deliver|transmit|notify|mail|publish|invoice|charge|sign|alter|modify|delete|change)\b'
        matches = list(re.finditer(pattern, clause))
        for index, match in enumerate(matches):
            verb = match.group(1)
            tail = clause[match.end():matches[index+1].start() if index+1 < len(matches) else len(clause)]
            prefix = clause[:match.start()]
            negated = bool(re.search(r"\b(do not|don't|dont|never|without|no)\b(?:\W+\w+){0,3}\W*$", prefix))
            consequential = verb in {'invoice', 'charge', 'sign'} or bool(re.search(r'\b(client|customer|card|northstar|field notes|juniper|proposal|draft|change request|scope note|contract|agreement|project)\b', tail))
            if consequential and not negated:
                return True
    return False


def resolve_reply(task: str, pending: PendingGoal | None) -> str:
    if pending is None or re.match(r'\s*(?:please\s+)?(?:list|show|inspect|review|read|analy[sz]e|assess|compare|evaluate|draft|prepare|check)\b', task, re.I) or forbidden_action(task):
        return task
    projects, requests = ids(task, 'project'), ids(task, 'request')
    project = projects[0] if len(projects) == 1 else pending.project_id
    request = requests[0] if len(requests) == 1 else pending.request_id
    body = pending.request_text
    if not projects and not requests:
        body, request = task.strip(), None
    instruction = re.sub(r'\b(?:project|request)[-\s]?\d{3}\b', '', pending.instruction, flags=re.I).strip()
    selection = ' '.join(x for x in (project, request) if x)
    if len(projects) > 1 or len(requests) > 1:
        selection = task
    return f'{instruction} {selection}' + (f': {body}' if body and not request else '')


def pending_goal(task: str) -> PendingGoal:
    project, request = ids(task, 'project'), ids(task, 'request')
    return PendingGoal(instruction=instruction_text(task), project_id=project[0] if len(project)==1 else None,
                       request_id=request[0] if len(request)==1 else None, request_text=inline_request(task))
