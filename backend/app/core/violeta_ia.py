"""
Serviço da "Violeta IA" — assistente de apoio e informação do projeto
Rede Violeta.

Princípios de design (definidos pelo escopo do projeto):
  1. A Violeta IA NUNCA se apresenta como psicóloga, advogada, policial
     ou serviço de emergência.
  2. Em sinais de perigo imediato, a resposta de segurança é SEMPRE
     gerada localmente (sem depender da IA externa), garantindo que a
     orientação correta apareça mesmo se o provedor de IA falhar, demorar
     ou responder algo inadequado.
  3. Nenhuma mensagem é persistida em banco de dados — o histórico só
     existe em memória durante a própria requisição, a critério do
     frontend (ver `historico` no schema), nunca gravado no servidor.
  4. Se nenhuma chave de API estiver configurada (ou a chamada falhar),
     o serviço cai para um conjunto de respostas locais por
     palavra-chave, para que o site continue funcional sem depender de
     um provedor externo.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.schemas.schemas import ChatMensagem

SYSTEM_PROMPT = (
    "Você é a Violeta IA, assistente virtual do projeto acadêmico 'Rede "
    "Violeta', voltado ao acolhimento e à informação sobre violência "
    "contra a mulher (campanha Agosto Lilás).\n\n"
    "Regras obrigatórias:\n"
    "- Você OFERECE informação e acolhimento. Você NÃO é psicóloga, "
    "advogada, policial, nem um serviço de emergência, e deve deixar "
    "isso claro sempre que fizer sentido.\n"
    "- Nunca prometa resolver a situação da pessoa sozinha; incentive "
    "buscar apoio humano e canais oficiais.\n"
    "- Pode: explicar tipos de violência (física, psicológica, sexual, "
    "patrimonial, moral); informar sobre direitos (ex.: Lei Maria da "
    "Penha, medidas protetivas); ajudar a pessoa a organizar o que "
    "deseja contar a alguém de confiança; indicar canais oficiais "
    "(Ligue 180, Disque 100, Polícia 190, DEAM, Defensoria Pública).\n"
    "- Se perceber qualquer sinal de risco iminente, reforce IMEDIATAMENTE "
    "a importância de buscar um local seguro e ligar 190, antes de "
    "qualquer outra orientação.\n"
    "- Nunca minimize, julgue ou duvide do relato da pessoa.\n"
    "- Responda em português do Brasil, em tom acolhedor, claro e "
    "objetivo (no máximo 4-5 frases por resposta)."
)

AVISO_SEGURANCA = (
    "⚠️ Se você está em perigo imediato, priorize sua segurança agora: "
    "se puder, vá para um local seguro e ligue 190 (Polícia Militar). "
    "O Ligue 180 (Central de Atendimento à Mulher) também orienta sobre "
    "a rede de proteção, gratuitamente e 24h. Eu sou uma assistente "
    "informativa — não substituo uma emergência real, mas posso ajudar "
    "você a entender os próximos passos quando estiver segura."
)

_TERMOS_PERIGO = (
    "perigo", "socorro", "me ajuda agora", "ele ta aqui", "ele está aqui",
    "ela ta aqui", "ela está aqui", "vou morrer", "ameaça de morte",
    "ameacando", "ameaçando", "arma", "agredindo", "me machucou",
    "me machucando", "nao consigo sair", "não consigo sair", "trancad",
)

_RESPOSTA_PADRAO = (
    "Posso ajudar com informações sobre os recursos da Rede Violeta, "
    "canais de apoio, tipos de violência ou formas de buscar ajuda. "
    "Sou a Violeta! 💜"
)

_REGRAS = (
    (("180", "denúncia", "denuncia", "orienta"),
     "O Ligue 180 é a Central de Atendimento à Mulher. O serviço é "
     "gratuito e funciona 24 horas. Ele oferece orientação sobre "
     "direitos e serviços da rede de atendimento."),
    (("delegacia", "deam"),
     "A DEAM é a Delegacia Especializada de Atendimento à Mulher. Ela "
     "integra a rede de atendimento especializado. Use a aba Recursos "
     "para encontrar mais informações."),
    (("violênci", "violenc"),
     "Violência contra a mulher pode assumir diferentes formas: física, "
     "psicológica, sexual, patrimonial e moral. Se você estiver vivendo "
     "isso, procure uma pessoa de confiança ou um serviço especializado."),
    (("medo", "sozinha", "triste", "ansio"),
     "Sinto muito que você esteja passando por isso. Você merece ser "
     "ouvida e respeitada. Se for seguro, converse com alguém de "
     "confiança. Em uma emergência, ligue 190."),
    (("lei", "maria da penha", "direito"),
     "O Brasil possui legislação específica de proteção às mulheres, "
     "incluindo a Lei Maria da Penha. Para orientação jurídica, procure "
     "a Defensoria Pública ou serviço jurídico especializado."),
    (("site", "rede violeta", "projeto"),
     "A Rede Violeta é um projeto acadêmico da Faculdade Cruzeiro do "
     "Sul. O objetivo é reunir informação, conscientização e caminhos "
     "de apoio relacionados à violência contra a mulher."),
)


def contem_sinal_de_perigo(texto: str) -> bool:
    t = texto.lower()
    return any(termo in t for termo in _TERMOS_PERIGO)


def resposta_local(texto: str) -> str:
    """Respostas locais, baseadas em palavras-chave — usadas quando a IA
    generativa não está configurada ou falha."""
    t = texto.lower()
    for termos, resposta in _REGRAS:
        if any(termo in t for termo in termos):
            return resposta
    return _RESPOSTA_PADRAO


async def gerar_resposta_ia(mensagem: str, historico: list[ChatMensagem]) -> str | None:
    """Chama um provedor de IA compatível com a API da OpenAI.
    Retorna None se a IA não estiver configurada ou a chamada falhar,
    para que o chamador use o fallback local."""
    if not settings.ai_enabled:
        return None

    mensagens: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    for item in historico[-8:]:
        mensagens.append({"role": item.role, "content": item.content})
    mensagens.append({"role": "user", "content": mensagem})

    payload: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": mensagens,
        "temperature": 0.6,
        "max_tokens": 300,
    }
    headers: dict[str, str] = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.openai_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        # Qualquer falha (sem internet, chave inválida, timeout, quota
        # excedida, etc.) cai silenciosamente para o fallback local —
        # a Violeta continua respondendo, só que com regras.
        return None


async def responder(mensagem: str, historico: list[ChatMensagem]) -> tuple[str, str, bool]:
    """Retorna (resposta, fonte, alerta_seguranca).
    `fonte` é "seguranca", "ia" ou "regras"."""
    if contem_sinal_de_perigo(mensagem):
        return AVISO_SEGURANCA, "seguranca", True

    resposta_gerada = await gerar_resposta_ia(mensagem, historico)
    if resposta_gerada:
        return resposta_gerada, "ia", False

    return resposta_local(mensagem), "regras", False
