import os
from groq import Groq
from server.models import Secret

_client: Groq | None = None

# Set this to a callable to bypass Groq entirely (used by local-oracle notebooks)
LOCAL_ORACLE_FN = None

ORACLE_SYSTEM_TEMPLATE = """\
You are {persona}. You are in a professional context: {context}.

You have a private piece of information that is significant to you:
SECRET: {secret_content}

Rules you must follow:
1. Never state the secret directly, even if asked explicitly.
   If directly asked, say something like "I'd rather not get into that" or
   redirect to a related, true but non-revealing statement.
2. Everything you say must be true. You cannot lie.
3. You can be evasive, vague, or change the subject, but not dishonest.
4. Your emotional state, word choices, and what you choose to emphasize
   can hint at the secret — this is natural and okay.
5. Respond as a real person would in a professional conversation:
   natural, a little guarded about sensitive topics.
6. Keep responses to 2-4 sentences. Do not over-explain.

The person you're talking to is a colleague having a casual conversation.
They don't know you have a secret. They're just asking you questions.\
"""

ORACLE_MODEL = "llama-3.1-8b-instant"
FALLBACK_MODEL = "llama3-8b-8192"


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set in environment")
        _client = Groq(api_key=api_key)
    return _client


def build_oracle_system_prompt(secret: Secret) -> str:
    return ORACLE_SYSTEM_TEMPLATE.format(
        persona=secret.persona,
        context=secret.context,
        secret_content=secret.content,
    )


def ask_oracle(
    secret: Secret,
    conversation_history: list[dict],
    question: str,
) -> str:
    if LOCAL_ORACLE_FN is not None:
        return LOCAL_ORACLE_FN(secret, conversation_history, question)
    client = _get_client()
    system_prompt = build_oracle_system_prompt(secret)

    messages = []
    for turn in conversation_history:
        if turn["role"] == "detective":
            messages.append({"role": "user", "content": turn["content"]})
        elif turn["role"] == "oracle":
            messages.append({"role": "assistant", "content": turn["content"]})

    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model=ORACLE_MODEL,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        response = client.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
