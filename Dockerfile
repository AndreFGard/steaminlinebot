FROM ghcr.io/astral-sh/uv:debian  as steaminlinebot_builder
WORKDIR /bot
COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev

COPY . .
RUN uv sync --no-dev

FROM python:3.14-slim as steaminlinebot
WORKDIR /bot
RUN pip install uv
COPY --from=steaminlinebot_builder /bot/.venv /bot/.venv
COPY --from=steaminlinebot_builder /bot/data /bot/data
COPY --from=steaminlinebot_builder /bot/src /bot/src
COPY --from=steaminlinebot_builder /bot/pyproject.toml /bot/pyproject.toml
COPY --from=steaminlinebot_builder /bot/README.md /bot/README.md
COPY ./.env /bot/.env
CMD uv run --env-file .env bot
