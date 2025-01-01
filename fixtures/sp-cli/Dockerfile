FROM python:3.12

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /opt/spaceport

COPY ./pylib/. ./pylib
COPY ./spaceport/. ./spaceport
COPY ./spaceport_simpl/. ./spaceport_simpl
COPY ./spaceport_cli/. ./spaceport_cli
COPY ./pyproject.toml .

RUN uv pip install --system -e .
RUN export SP_DOTENV="$(sp tc get-config-dir)/.env" && \
    echo "SPACEPORT_OPENAI_API_KEY=<NOT_GIVEN>\nSPACEPORT_ANTHROPIC_API_KEY=<NOT_GIVEN>" > "$SP_DOTENV"

WORKDIR /

CMD ["tail", "-f", "/dev/null"]
