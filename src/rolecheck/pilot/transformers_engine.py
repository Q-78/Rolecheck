"""Concrete, offline Gate 4 Qwen3 generation engine."""

from __future__ import annotations

import importlib
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rolecheck.pilot.config import PILOT_VERSION
from rolecheck.pilot.execution import (
    RoleGenerationRequest,
    generation_engine_identity,
    required_generation_engine_identity,
)
from rolecheck.pilot.models import RawGeneration
from rolecheck.schemas import RuntimeAdapterIdentity


class Qwen3SingleGpuGenerationEngine:
    """Load the frozen Qwen3-8B snapshot once on the sole visible GPU."""

    def __init__(
        self,
        *,
        model_path: Path,
        generation_config: Mapping[str, object] | None = None,
        runtime_version: str = PILOT_VERSION,
        cuda_visible_devices: str = "0",
    ) -> None:
        if not model_path.is_dir():
            raise ValueError("frozen model snapshot directory is missing")
        torch: Any = importlib.import_module("torch")
        transformers: Any = importlib.import_module("transformers")
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError("Gate 4 requires exactly one visible CUDA GPU")
        self._torch = torch
        self._identity = (
            required_generation_engine_identity()
            if generation_config is None
            else generation_engine_identity(
                generation_config=generation_config,
                runtime_version=runtime_version,
                cuda_visible_devices=cuda_visible_devices,
            )
        )
        self._tokenizer = transformers.AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True, trust_remote_code=False
        )
        self._model = transformers.AutoModelForCausalLM.from_pretrained(
            str(model_path),
            torch_dtype=torch.bfloat16,
            device_map={"": "cuda:0"},
            local_files_only=True,
            trust_remote_code=False,
        )
        self._model.eval()
        devices = {str(parameter.device) for parameter in self._model.parameters()}
        dtypes = {str(parameter.dtype) for parameter in self._model.parameters()}
        if devices != {"cuda:0"}:
            raise RuntimeError(f"model parameters escaped GPU 0: {sorted(devices)}")
        if dtypes != {"torch.bfloat16"}:
            raise RuntimeError(f"model parameters are not uniformly BF16: {sorted(dtypes)}")
        self._runtime_state = {
            "visible_cuda_devices": torch.cuda.device_count(),
            "cuda_device_name": torch.cuda.get_device_name(0),
            "parameter_devices": sorted(devices),
            "parameter_dtypes": sorted(dtypes),
            "quantized": bool(getattr(self._model, "is_quantized", False)),
        }
        if self._runtime_state["quantized"]:
            raise RuntimeError("quantization is forbidden")

    @property
    def identity(self) -> RuntimeAdapterIdentity:
        identity = self._identity
        return identity.model_copy(deep=True)

    @property
    def runtime_state(self) -> dict[str, object]:
        return dict(self._runtime_state)

    def generate(self, request: RoleGenerationRequest) -> RawGeneration:
        torch = self._torch
        torch.manual_seed(request.role_seed)
        torch.cuda.manual_seed_all(request.role_seed)
        config = dict(request.generation_config)
        enable_thinking = config.pop("enable_thinking", True)
        if not isinstance(enable_thinking, bool):
            raise ValueError("enable_thinking must be an explicit boolean")
        messages = [
            {"role": "system", "content": request.prompt.system_prompt},
            {"role": "user", "content": request.prompt.user_prompt},
        ]
        input_ids = self._tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
            return_tensors="pt",
        ).to("cuda:0")
        attention_mask = torch.ones_like(input_ids, dtype=torch.long, device=input_ids.device)
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = self._model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                pad_token_id=self._tokenizer.eos_token_id,
                **config,
            )
        torch.cuda.synchronize()
        latency_ms = (time.perf_counter() - started) * 1000
        token_ids = output[0, input_ids.shape[-1] :].tolist()
        decoded = self._tokenizer.decode(token_ids, skip_special_tokens=True)
        return RawGeneration(
            raw_token_ids=token_ids,
            raw_decoded_output=decoded,
            input_token_count=int(input_ids.shape[-1]),
            output_token_count=len(token_ids),
            latency_ms=latency_ms,
        )

    def close(self) -> None:
        model = self._model
        self._model = None
        self._tokenizer = None
        del model
        self._torch.cuda.empty_cache()
