import time

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent, NativeOutput, capture_run_messages
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from qws.core.models import DrafterReply, Prompt, Reply, SupportReply

TIMEOUT_SECONDS = 60


def _chain(error: BaseException):
    while error is not None:
        yield error
        error = error.__cause__ or error.__context__


def short_error(error: Exception) -> str:
    """A short message. Never the key, never a stack trace."""
    chain = list(_chain(error))
    if any(isinstance(e, (TimeoutError, openai.APITimeoutError)) for e in chain):
        return "Model call failed: timeout."
    for e in chain:
        if isinstance(e, ModelHTTPError):
            return f"Model call failed: HTTP {e.status_code}."
    return "Model call failed."


class RealDrafter:
    """Asks an OpenAI model through a PydanticAI Agent: no retries, no tools."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        settings: dict[str, int | float | str],
        model: Model | None = None,  # tests pass a fake model
    ) -> None:
        self._model_name = model_name
        self._api_key = api_key
        self._settings = settings
        self._model = model

    def _build_model(self) -> Model:
        if self._model is not None:
            return self._model
        client = AsyncOpenAI(api_key=self._api_key, max_retries=0, timeout=TIMEOUT_SECONDS)
        return OpenAIResponsesModel(self._model_name, provider=OpenAIProvider(openai_client=client))

    def _reply(self, **fields) -> DrafterReply:
        return DrafterReply(label="real", model=self._model_name, settings=self._settings, **fields)

    def draft(self, prompt: Prompt) -> DrafterReply:
        return self._ask(prompt, Reply)

    def judge(self, prompt: Prompt) -> DrafterReply:
        return self._ask(prompt, SupportReply)

    def _ask(self, prompt: Prompt, output_type: type[BaseModel]) -> DrafterReply:
        if self._model is None and not self._api_key:
            return self._reply(error="OPENAI_API_KEY is not set.")
        if self._model is None and not self._model_name:
            return self._reply(error="MODEL_NAME is not set.")
        started = time.monotonic()
        try:
            agent = Agent(
                self._build_model(),
                output_type=NativeOutput(output_type),
                instructions=prompt.system,
                retries=0,
            )
            with capture_run_messages() as messages:
                try:
                    result = agent.run_sync(
                        prompt.user, model_settings={**self._settings, "timeout": TIMEOUT_SECONDS}
                    )
                except UnexpectedModelBehavior:
                    # The model answered but the reply does not fit the schema: hand the
                    # raw text back so it is saved; DraftService judges it.
                    last = messages[-1] if messages else None
                    if not isinstance(last, ModelResponse) or not last.text:
                        raise
                    return self._reply(
                        raw_reply=last.text,
                        latency_ms=round((time.monotonic() - started) * 1000),
                        input_tokens=last.usage.input_tokens,
                        output_tokens=last.usage.output_tokens,
                    )
            usage = result.usage
            return self._reply(
                raw_reply=result.response.text or result.output.model_dump_json(),
                latency_ms=round((time.monotonic() - started) * 1000),
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )
        except Exception as e:
            return self._reply(
                error=short_error(e), latency_ms=round((time.monotonic() - started) * 1000)
            )
