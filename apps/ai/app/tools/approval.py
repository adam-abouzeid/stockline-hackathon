"""
Customer approval before confirming an order — enforced in code, not only in the prompt.

`confirm_order` is allowed only if, in the conversation history:
  1. the order was recapped: the agent finished a turn (a final assistant message, no tool call) AFTER the last
     modification of the order, and
  2. the customer then spoke again, and
  3. that last customer message is an unambiguous approval (`is_explicit_approval`), and
  4. nothing modified the order since (same turn included).

`is_explicit_approval` is deliberately conservative: a false "no" costs one more question, a false "yes" books a wrong
order. It is a deterministic French/English check on short messages, covered by tests/test_approval.py.
"""

import re
import unicodedata
from dataclasses import dataclass

from .order_state import MODIFYING_TOOLS

AFFIRMATIVE = (
    "oui", "ouais", "ouaip", "yes", "yep", "ok", "okay", "okey", "dac", "daccord", "d accord", "vas y", "vasy", "allez", "go",
    "c est bon", "cest bon", "ca marche", "ca roule", "parfait", "nickel", "impeccable", "tres bien", "bien sur", "banco",
    "entendu", "exactement", "c est ca", "confirme", "confirmez", "valide", "validez", "envoie", "envoyez", "sure", "that s right",
    "tout a fait", "absolument", "evidemment", "volontiers",
)  # fmt: skip

# Anything that suggests a change, a doubt, a question or a refusal. Presence of ANY of them → not an approval.
BLOCKERS = (
    "non", "pas", "jamais", "attend", "attends", "attendez", "mais", "par contre", "sauf", "finalement", "plutot", "change",
    "modifi", "ajout", "rajout", "retir", "enlev", "supprim", "annul", "remplac", "en plus", "de plus", "et aussi", "aussi",
    "combien", "quand", "quel", "comment", "pourquoi", "peut etre", "sais pas", "sais plus", "hesit", "reflechi", "verifi",
    "laisse", "sinon", "et si", "euh", "hum", "bof", "wait", "but", "no", "not", "actually", "maybe", "change", "instead",
)  # fmt: skip
BLOCKERS += ("pense", "crois", "normalement", "priori", "suppose", "probablement", "si")  # hedges: clearer refusal reasons

# Every word of an approval must be here (after `normalize`: lowercase, no accents, apostrophes/hyphens → spaces).
ALLOWED_WORDS = frozenset(
    "oui ouais ouaip yes yep ok okay okey dac daccord d accord vas y vasy allez go c est bon ca marche roule parfait parfaitement "
    "nickel impeccable tres bien sur banco entendu exactement confirme confirmez valide validez envoie envoyez sure that s right "
    "ben bah alors donc je le la on pour moi me nous commande tout fait voila note compris absolument evidemment volontiers "
    "super top genial merci beaucoup s il vous plait svp au revoir bonne journee soiree bientot monsieur madame a".split()
)  # fmt: skip
HARMLESS_NEGATIONS = ("pas de souci", "pas de probleme", "pas de soucis", "no problem", "no worries")

NUMBER_WORDS = (
    "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "quinze", "vingt", "trente",
    "quarante", "cinquante", "soixante", "cent", "mille", "demi", "double", "triple", "two", "three", "four", "five", "ten",
)  # fmt: skip

MAX_WORDS = 10


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9?]+", " ", text).strip()


@dataclass
class Verdict:
    approved: bool
    reason: str


def is_explicit_approval(text: str | None) -> Verdict:
    """True only for a short, unconditional "yes" to the recap."""
    t = normalize(text or "")
    if not t:
        return Verdict(False, "message vide")
    if "?" in t:
        return Verdict(False, "le client pose une question")
    for ok in HARMLESS_NEGATIONS:
        t = t.replace(ok, " ")
    t = f" {t} "
    words = t.split()
    if len(words) > MAX_WORDS:
        return Verdict(False, "message trop long pour être un simple accord")
    if re.search(r"\d", t):
        return Verdict(False, "le client donne un chiffre (quantité ou date) : ce n'est pas un simple accord")
    for w in NUMBER_WORDS:
        if f" {w} " in t:
            return Verdict(False, "le client donne une quantité : ce n'est pas un simple accord")
    for b in BLOCKERS:
        # prefix match for stems ("modifi"), whole-word match for short words ("non", "no")
        if (f" {b} " in t) if len(b) <= 4 else (f" {b}" in t):
            return Verdict(False, f"réserve ou changement détecté (« {b.strip()} »)")
    # Allowlist (V2): EVERY word must be a yes-word or a polite filler. A blocklist can never list every way to hedge
    # ("oui je pense", "oui si tu veux", "oui pour lundi"…): an unknown word means "not a plain yes" → one more question.
    unknown = [w for w in words if w not in ALLOWED_WORDS]
    if unknown:
        return Verdict(False, f"mot qui n'est pas un simple accord (« {unknown[0]} »)")
    if any(f" {a} " in t for a in AFFIRMATIVE):
        return Verdict(True, "accord explicite")
    return Verdict(False, "aucun accord explicite")


def confirmation_gate(messages: list | None, modified_this_turn: bool = False) -> Verdict:
    """May the agent confirm the order NOW? Judged on the live history (voice / chat modes)."""
    msgs = list(messages or [])
    last_user = next((i for i in range(len(msgs) - 1, -1, -1) if msgs[i].role == "user" and (msgs[i].content or "").strip()), None)
    if last_user is None:
        return Verdict(False, "aucun message du client")
    if modified_this_turn or any(m.role == "tool" and m.name in MODIFYING_TOOLS for m in msgs[last_user + 1 :]):
        return Verdict(False, "la commande vient d'être modifiée : récapitule-la au client et attends son accord")
    approval = is_explicit_approval(msgs[last_user].content)
    if not approval.approved:
        return Verdict(False, f"pas d'accord explicite du client sur le récapitulatif ({approval.reason})")
    last_change = max((i for i, m in enumerate(msgs[:last_user]) if m.role == "tool" and m.name in MODIFYING_TOOLS), default=None)
    if last_change is None:
        return Verdict(False, "la commande n'a pas été préparée dans cet appel")
    recap = any(
        m.role == "assistant" and not m.tool_calls and (m.content or "").strip() for m in msgs[last_change + 1 : last_user]
    )
    if not recap:
        return Verdict(False, "le récapitulatif n'a pas été lu au client avant son accord")
    return Verdict(True, "récapitulatif lu puis accord explicite")
