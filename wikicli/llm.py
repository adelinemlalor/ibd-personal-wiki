"""Thin client for the local Ollama server that runs Gemma.

Only the standard library is used, so nothing here can reach the internet:
the one URL we talk to is the local Ollama server from config.json.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .config import Config


class ModelUnavailable(RuntimeError):
    """Raised when the local runtime is not running or the model is not pulled."""


@dataclass
class Reply:
    text: str
    model: str
    stats: dict = field(default_factory=dict)


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class LocalGemma:
    def __init__(self, cfg: Config):
        if cfg.mode != "local":
            raise ModelUnavailable(
                f"Mode '{cfg.mode}' is not implemented. This project runs Gemma locally only "
                "(use --mode local).")
        host = urlparse(cfg.ollama_url).hostname
        if host not in LOCAL_HOSTS:
            raise ModelUnavailable(f"Refusing non-local model URL in local mode: {cfg.ollama_url}")
        self.cfg = cfg
        self.url = cfg.ollama_url.rstrip("/")
        self.model = cfg.model

    # ---- low-level HTTP -------------------------------------------------
    def _post(self, path: str, payload: dict, stream: bool):
        req = urllib.request.Request(
            self.url + path, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            return urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 404 and "not found" in body:
                raise ModelUnavailable(
                    f"Model '{self.model}' is not downloaded. Run: ollama pull {self.model}")
            raise ModelUnavailable(f"Ollama returned HTTP {e.code}: {body[:300]}")
        except (urllib.error.URLError, ConnectionError) as e:
            raise ModelUnavailable(
                f"Cannot reach the local Ollama server at {self.url} ({e}). "
                "Start it with `ollama serve` (or open the Ollama app) and try again.")

    def _get(self, path: str) -> dict:
        try:
            with urllib.request.urlopen(self.url + path, timeout=10) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, ConnectionError) as e:
            raise ModelUnavailable(f"Cannot reach the local Ollama server at {self.url} ({e}).")

    # ---- public API -----------------------------------------------------
    def chat(self, messages: list[dict], *, temperature: float | None = None,
             json_schema: dict | None = None, stream_to=None) -> Reply:
        """Send a message list to Gemma. If stream_to is a file (e.g. sys.stdout),
        tokens are printed as they arrive."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream_to is not None,
            "think": False,
            "options": {
                "temperature": self.cfg.temperature if temperature is None else temperature,
                "num_ctx": self.cfg.num_ctx,
            },
        }
        if json_schema is not None:
            payload["format"] = json_schema

        t0 = time.time()
        resp = self._post("/api/chat", payload, stream=payload["stream"])
        text_parts, final = [], {}
        with resp:
            if payload["stream"]:
                for line in resp:
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    piece = msg.get("message", {}).get("content", "")
                    if piece:
                        text_parts.append(piece)
                        stream_to.write(piece)
                        stream_to.flush()
                    if msg.get("done"):
                        final = msg
                stream_to.write("\n")
            else:
                final = json.loads(resp.read())
                text_parts.append(final.get("message", {}).get("content", ""))

        stats = {
            "wall_seconds": round(time.time() - t0, 2),
            "load_seconds": round(final.get("load_duration", 0) / 1e9, 2),
            "prompt_tokens": final.get("prompt_eval_count"),
            "output_tokens": final.get("eval_count"),
            "gen_tokens_per_sec": _rate(final.get("eval_count"), final.get("eval_duration")),
        }
        return Reply(text="".join(text_parts).strip(), model=final.get("model", self.model), stats=stats)

    def chat_json(self, messages: list[dict], schema: dict, retries: int = 2) -> dict:
        """Ask for structured output and parse it; retry once on malformed JSON."""
        last_err = None
        for _ in range(retries):
            reply = self.chat(messages, json_schema=schema, temperature=0.1)
            try:
                return json.loads(reply.text)
            except json.JSONDecodeError as e:
                last_err = e
        raise ValueError(f"Gemma did not return valid JSON: {last_err}")

    def status(self) -> dict:
        """Runtime version, whether the model is pulled, and loaded-model memory."""
        version = self._get("/api/version").get("version")
        tags = [m["name"] for m in self._get("/api/tags").get("models", [])]
        loaded = [
            {"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 2),
             "gpu_gb": round(m.get("size_vram", 0) / 1e9, 2),
             "context": m.get("context_length")}
            for m in self._get("/api/ps").get("models", [])
        ]
        return {"runtime": f"ollama {version}", "model": self.model,
                "model_pulled": self.model in tags, "loaded": loaded}


def _rate(count, duration_ns):
    if not count or not duration_ns:
        return None
    return round(count / (duration_ns / 1e9), 1)


def die(msg: str, code: int = 2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)
