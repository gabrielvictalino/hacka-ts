"""Reconhecimento local de ação e medida; o texto apresentado continua literal."""

import re

# Vocabulário de ações, independente de códigos, temas ou valores do acervo.
ACTION_FORMS = {
    "solicitação": r"solicita(?:r|ção|ções)?|pedir|pedido(?:s)?|requerer|requerimento(?:s)?",
    "cancelamento": r"cancela(?:r|mento|mentos)?",
    "inscrição": r"inscreve(?:r)?|inscreve-se|inscrição|inscrições",
    "prorrogação": r"prorroga(?:r|ção|ções)?",
    "renovação": r"renova(?:r|ção|ções)?",
    "aprovação": r"aprova(?:r|ção|ções)?",
    "pagamento": r"paga(?:r|mento|mentos)?",
    "assinatura": r"assina(?:r|tura|turas)?",
    "emissão": r"emitir|emite|emissão|emissões",
    "programação": r"programa(?:r|ção|ções)?",
}
ACTION_PATTERNS = {key: re.compile(rf"\b(?:{forms})\b", re.I) for key, forms in ACTION_FORMS.items()}
TIME = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:dias?|horas?|semanas?|mês|meses|anos?)\b|\b\d{2}/\d{2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", re.I
)
MONEY = re.compile(r"R\$\s*\d[\d.,]*|\b\d+(?:[.,]\d+)?\s*(?:reais|%|por cento)", re.I)
UNCERTAIN = re.compile(
    r"consult[ae]|encaminh|entre em contato|a confirmar|"
    r"não (consta|há|informa|especifica|define|estabelece)|"
    r"não (está |foi |é )?(informad|definid|especificad|estabelecid)|"
    r"sem (confirmação|definição|informação|prazo|valor)",
    re.I,
)
COMPARISON_OR_NEGATION = re.compile(
    r"\b(?:não|nem|nunca|jamais|difer\w*|distint\w*|diverg\w*|compar\w*|depende|superior|inferior)\b", re.I
)
CONNECTORS = set(
    "de da do das dos a o as os para com em no na nos nas ao aos é será mínimo mínima máximo máxima até pelo menos formal".split()
)


EXCLUSION = re.compile(r"\b(?:salvo|exceto|ressalvad[oa]s?|excluíd[oa]s?|(?:com|à)\s+exceção)\b", re.I)


def affirmative_scope(sentence):
    """Uma ação citada como exceção não pertence à regra quantitativa geral."""
    while match := EXCLUSION.search(sentence):
        before = sentence[: match.start()].rstrip(" ,")
        # Uma ressalva depois da medida não fornece outro sujeito para essa medida.
        if TIME.search(before) or MONEY.search(before):
            return before
        remainder = sentence[match.end() :]
        boundary = re.search(r"(?<!\d),|,(?!\d)", remainder)
        if not boundary:
            return before
        # Exceção inicial ou intercalada: conserva a oração geral depois da vírgula.
        sentence = before + " " + remainder[boundary.end() :]
    return sentence.strip()


def normalize_terms(value):
    value = re.sub(r"\bquantos?\s+(?:dias?|horas?|meses)\b", "prazo", value, flags=re.I)
    value = re.sub(r"\b(?:antecedência|antecedencia)\b", "prazo", value, flags=re.I)
    for action, pattern in ACTION_PATTERNS.items():
        value = pattern.sub(action, value)
    return value.casefold()


SEARCH_ALIASES = {
    "solicitação": "solicitar solicita solicitação pedir pedido requerer requerimento",
    "cancelamento": "cancelar cancela cancelamento",
    "inscrição": "inscrever inscreve inscrição",
    "prorrogação": "prorrogar prorroga prorrogação",
    "renovação": "renovar renova renovação",
    "aprovação": "aprovar aprova aprovação",
    "pagamento": "pagar paga pagamento",
    "assinatura": "assinar assina assinatura",
    "emissão": "emitir emite emissão",
    "programação": "programar programa programação",
}


def search_terms(value):
    # A expansão só recupera candidatos; não confirma respostas por si só.
    expanded = [value]
    for action, aliases in SEARCH_ALIASES.items():
        if action in value:
            expanded.append(aliases)
    if "prazo" in value:
        expanded.append("prazo antecedência dias")
    return " ".join(expanded)


def quantity_kind(question):
    if re.search(r"\b(?:quem|responsável)\b", question, re.I):
        return None
    if re.search(r"prazo|antecedência|quantos?\s+(?:dias?|horas?|mês|meses)", question, re.I):
        return "deadline"
    if re.search(r"valor|cust[oa]|preço|quanto", question, re.I):
        return "value"
    return None


def actions(value):
    return {key for key, pattern in ACTION_PATTERNS.items() if pattern.search(value)}


def words(value):
    return set(re.findall(r"[^\W\d_]+", value.casefold()))


def direct_quantity(sentence, question, scope, kind):
    """A medida deve seguir um marcador ligado à mesma ação da pergunta."""
    source_actions, requested_actions = actions(sentence), actions(question)
    if len(source_actions) > 1 or (requested_actions and source_actions != requested_actions):
        return False
    if COMPARISON_OR_NEGATION.search(sentence):
        return False
    allowed = CONNECTORS | words(question) | words(scope) | source_actions
    normalized = normalize_terms(sentence)
    for measure in (TIME if kind == "deadline" else MONEY).finditer(normalized):
        prefix = normalized[: measure.start()]
        markers = list(re.finditer(r"\b(?:prazo|valor|custo|preço)\b", prefix))
        if markers:
            tail = prefix[markers[-1].end() :]
            if words(tail) <= allowed:
                return True
        # “Solicitação: até 45 dias antes” ou “solicitar com 45 dias de antecedência”.
        if kind == "deadline" and source_actions:
            action = next(iter(source_actions))
            tail = prefix.rsplit(action, 1)[-1]
            if re.search(r"\b(?:até|com)\s*$", tail) and words(tail) <= allowed:
                return True
    return False


def support_assertions(excerpt, question, scope):
    # Quebras gráficas de linha não separam uma afirmação dentro do mesmo item.
    sentences = re.split(r"(?<=[.!?;])\s+", " ".join(excerpt.split()))
    kind = quantity_kind(question)
    for sentence in sentences:
        sentence = affirmative_scope(sentence)
        if not sentence or UNCERTAIN.search(sentence):
            continue
        if kind and not direct_quantity(sentence, question, scope, kind):
            continue
        normalized = normalize_terms(sentence)
        if kind == "deadline":
            normalized += " prazo"
        yield normalized + " " + normalize_terms(scope)
