"""
model.py — KalamGPT model wrapper
Loads the fine-tuned GPT-2 and exposes a .generate() interface.
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import os
import logging

logger = logging.getLogger(__name__)

KALAM_SYSTEM_PROMPT = """You are Kalam GPT, an AI inspired by Dr. A.P.J. Abdul Kalam — scientist, President, teacher, and visionary of India.

PERSONALITY: Speak with warmth, humility, and hope. Use 'we' for India's future. Never be dismissive.

REASONING: Dig to the root of every question. Connect individual problems to larger systems.

INNOVATION: Connect unrelated domains to generate novel ideas."""


class KalamGPT:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.device = 0 if torch.cuda.is_available() else -1
        self._load_model()

    def _load_model(self):
        logger.info(f"Loading KalamGPT from {self.model_path}...")

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found at {self.model_path}")

        self.tokenizer = AutoTokenizer.from_pretrained("gpt2")
        self.tokenizer.pad_token = self.tokenizer.eos_token

        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=dtype,
        )
        self.model.resize_token_embeddings(len(self.tokenizer))

        self.pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device=self.device,
        )

        logger.info(f"✅ KalamGPT loaded on {'GPU' if self.device == 0 else 'CPU'}")

    def generate(
        self,
        user_message: str,
        rag_context: str = "",
        max_new_tokens: int = 250,
        temperature: float = 0.80,
        top_p: float = 0.92,
        repetition_penalty: float = 1.3,
    ) -> str:
        """
        Generate a Kalam-style response.
        Handles RAG context + truncates to stay under GPT-2's 1024 token limit.
        """
        if not user_message or not user_message.strip():
            return "Please ask me something. I am here to help."

        # Build prompt with RAG context
        system = "You are Kalam GPT, inspired by Dr. A.P.J. Abdul Kalam.\n\n"
        
        if rag_context:
            prompt_text = f"{system}Context:\n{rag_context}\n\nQuestion: {user_message}\n\nAnswer:"
        else:
            prompt_text = f"{system}Question: {user_message}\n\nAnswer:"

        # Tokenize and truncate to stay under 1024 - max_new_tokens
        tokens = self.tokenizer.encode(prompt_text)
        max_input_tokens = 1024 - max_new_tokens - 50

        if len(tokens) > max_input_tokens:
            tokens = tokens[-max_input_tokens:]

        prompt_text = self.tokenizer.decode(tokens)

        try:
            result = self.pipe(
                prompt_text,
                max_new_tokens=min(max_new_tokens, 200),
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )
            full_output = result[0]["generated_text"]
            response = full_output[len(prompt_text):].strip()
            return response if response else "Let me think on this more deeply."

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return "I encountered an error generating a response. Please try again."

    def health_check(self) -> dict:
        return {
            "model_path": self.model_path,
            "device": "GPU" if self.device == 0 else "CPU",
            "loaded": self.model is not None,
        }