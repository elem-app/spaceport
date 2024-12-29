import base64
import logging
import pprint
from enum import StrEnum
from typing import Literal, NamedTuple, Sequence, TypedDict

from anthropic import NOT_GIVEN as ANT_NOT_GIVEN
from anthropic import AsyncAnthropic
from anthropic.types import ImageBlockParam, TextBlock, TextBlockParam
from openai import NOT_GIVEN as OAI_NOT_GIVEN
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionContentPartParam

from pylib.blob import MediaType, MultimediaBlob
from pylib.id import TypedStrID
from pylib.optional import NOT_GIVEN, NoneValueError, NotGiven, assume_given, unwrap
from spaceport.globals import globals

envvars = globals.envvars
llm_logger = logging.getLogger("llm")

_oai_client: AsyncOpenAI | None = None
_ant_client: AsyncAnthropic | None = None


class Vendor(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

    @classmethod
    def from_str(cls, s: str) -> "Vendor":
        return cls(s.lower())


class MessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"


class UserMessage(NamedTuple):
    content: str | MultimediaBlob
    type_: MessageType = MessageType.TEXT
    role: Literal["user"] = "user"


class AssistantMessage(NamedTuple):
    content: str
    type_: Literal[MessageType.TEXT] = MessageType.TEXT
    role: Literal["assistant"] = "assistant"


type ChatMessage = UserMessage | AssistantMessage


def _to_oai_content_part(
    type_: MessageType, content: str | MultimediaBlob
) -> ChatCompletionContentPartParam:
    match type_:
        case MessageType.TEXT:
            assert isinstance(content, str)
            return {"type": "text", "text": content}
        case MessageType.IMAGE:
            assert (
                isinstance(content, MultimediaBlob)
                and content.media_type == MediaType.IMAGE
            )
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64.b64encode(content.bytes).decode('utf-8')}",
                    "detail": "auto",
                },
            }


def _to_ant_block(
    type_: MessageType, content: str | MultimediaBlob
) -> TextBlockParam | ImageBlockParam:
    match type_:
        case MessageType.TEXT:
            assert isinstance(content, str)
            return {"type": "text", "text": content}
        case MessageType.IMAGE:
            assert (
                isinstance(content, MultimediaBlob)
                and content.media_type == MediaType.IMAGE
            )
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(content.bytes).decode("utf-8"),
                },
            }


class VendorError(Exception):
    pass


class LLMID(TypedStrID):
    type_name = "LLM"


class InferenceOptions(TypedDict):
    max_tokens: int | NotGiven
    temperature: float


_FALLBACK_OAI_OPTIONS: InferenceOptions = {"max_tokens": NOT_GIVEN, "temperature": 0.0}
_FALLBACK_ANT_OPTIONS: InferenceOptions = {"max_tokens": 1024, "temperature": 0.0}


class LLM:
    def __init__(
        self,
        name: str,
        vendor: Vendor,
        model: str,
        *,
        preamble: str | NotGiven = NOT_GIVEN,
        options: InferenceOptions | NotGiven = NOT_GIVEN,
    ):
        self.id = LLMID(name)
        self.vendor = vendor
        self.model = model
        self.preamble = preamble or NOT_GIVEN
        self.options = options or (
            _FALLBACK_OAI_OPTIONS if vendor == Vendor.OPENAI else _FALLBACK_ANT_OPTIONS
        )
        self.llm_logger = llm_logger.getChild(name)

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        preamble: str | NotGiven = NOT_GIVEN,
        options: InferenceOptions | NotGiven = NOT_GIVEN,
    ) -> str:
        if preamble is NOT_GIVEN:
            preamble = self.preamble

        if options is NOT_GIVEN:
            options = self.options
        else:
            options = self.options | assume_given(options)

        self.llm_logger.info(pprint.pformat(messages))

        match self.vendor:
            case Vendor.OPENAI:
                resp = await self._chat_oai(self.model, preamble, messages, options)
            case Vendor.ANTHROPIC:
                resp = await self._chat_ant(self.model, preamble, messages, options)

        self.llm_logger.info("Response: %s", pprint.pformat(resp))
        return resp

    async def _chat_oai(
        self,
        model: str,
        preamble: str | NotGiven,
        messages: Sequence[ChatMessage],
        options: InferenceOptions,
    ) -> str:
        global _oai_client
        if _oai_client is None:
            _oai_client = AsyncOpenAI(api_key=envvars.openai_api_key)
        resp = await _oai_client.chat.completions.create(
            model=model,
            max_tokens=options["max_tokens"] or OAI_NOT_GIVEN,
            temperature=options["temperature"],
            messages=[
                {"role": "system", "content": preamble or ""},
                *[
                    {
                        "role": m.role,
                        "content": [_to_oai_content_part(m.type_, m.content)],
                    }
                    if m.role == "user"
                    else {
                        "role": m.role,
                        "content": m.content,
                    }
                    for m in messages
                ],
            ],
        )
        try:
            return unwrap(resp.choices[0].message.content)
        except IndexError:
            raise VendorError("OpenAI returned no message content")
        except NoneValueError:
            raise VendorError("OpenAI returned None for message content")

    async def _chat_ant(
        self,
        model: str,
        preamble: str | NotGiven,
        messages: Sequence[ChatMessage],
        options: InferenceOptions,
    ) -> str:
        global _ant_client
        if _ant_client is None:
            _ant_client = AsyncAnthropic(api_key=envvars.anthropic_api_key)
        resp = await _ant_client.messages.create(
            model=model,
            max_tokens=assume_given(options["max_tokens"]),
            system=[
                {
                    "type": "text",
                    "text": preamble or "",
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            if preamble
            else ANT_NOT_GIVEN,
            temperature=options["temperature"],
            messages=[
                {"role": m.role, "content": [_to_ant_block(m.type_, m.content)]}
                for m in messages
            ],
        )
        try:
            if not isinstance(resp.content[0], TextBlock):
                raise VendorError("Anthropic returned non-text message content")
            return resp.content[0].text
        except IndexError:
            raise VendorError("Anthropic returned no message content")
        except NoneValueError:
            raise VendorError("Anthropic returned None for message content")
