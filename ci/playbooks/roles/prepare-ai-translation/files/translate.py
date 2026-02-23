#!/usr/bin/env python3
"""AI translation pipeline for OpenStack i18n.

Translates POT files into multiple languages using LLM models
with glossary-based consistency and parallel batch processing.

Execution flow:
    1. Load config and initialize utilities
    2. For each target language:
       a. Load glossary and few-shot examples
       b. Translate POT entries in parallel batches
       c. Save PO file and experiment log
"""

import os
import time
import concurrent.futures
import json
import argparse
from dataclasses import dataclass

import ollama
from tqdm import tqdm
from babel import Locale
from babel.messages import pofile, Catalog

from utils import ResourceLoader, load_config, logger


def get_language_name(lang_code):
    """Resolve a language code to its full English display name.

    Returns:
        Full language name (e.g., 'Korean (South Korea)'),
        or lang_code as-is if unrecognized.
    """
    try:
        return Locale.parse(lang_code).get_display_name('en')
    except Exception:
        return lang_code


PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")

DEFAULT_SYSTEM_PROMPT = (
    "You are a strict translation engine.\n"
    "You are translating from English to {language_name}.\n"
    "\n"
    "[Output Format Rules (MUST Follow)]\n"
    "* Respond ONLY with the raw, translated text for {language_name}.\n"
    "* Your answer MUST be 100% in {language_name}.\n"
    "* Do NOT mix in any other languages (including English).\n"
    "* Do NOT add explanations, comments, apologies, or quotes.\n"
    "\n"
    "[Critical Preservation Rules (MUST Follow)]\n"
    "* Preserve all reStructuredText (RST) syntax exactly.\n"
    "* Preserve all placeholders exactly.\n"
    "* Preserve all HTML tags exactly.\n"
    "* You MUST use the exact translations provided in the "
    "`[Glossary]` section.\n"
    "\n"
    "[Anti-Hallucination Rules (MUST Follow)]\n"
    "* You MUST NOT add placeholders that are NOT in the original `msgid`.\n"
    "* You MUST NOT repeat phrases. Repetition is strictly forbidden.\n"
    "\n"
    "[Glossary]\n"
)


@dataclass
class TranslationContext:
    glossary: dict
    few_shot_examples: list
    call_llm_fn: object
    max_workers: int
    system_prompt: str


class AITranslator:
    @staticmethod
    def build_llm_caller(model_name):
        """Build an Ollama-based LLM caller function.

        Forces the model to respond with a JSON array of strings
        using a structured output schema.

        Returns a callable that accepts a message list and returns
        the model's response text.
        """
        _response_format = {"type": "array", "items": {"type": "string"}}

        def _call(messages):
            response = ollama.chat(
                model=model_name,
                messages=messages,
                stream=False,
                format=_response_format,
                options={
                    "temperature": 0,
                    "top_p": 1,
                    "repetition_penalty": 1.2,
                },
            )
            return response["message"]["content"].strip()

        return _call

    @staticmethod
    def create_batches(entries, batch_size):
        return [
            entries[i:i + batch_size]
            for i in range(0, len(entries), batch_size)
        ]

    def _retry_individually(self, entries, batch_idx, total_batches,
                            language_name, ctx):
        """Retry failed batch entries one by one."""
        logger.warning(
            f"[Batch {batch_idx + 1}/{total_batches}] "
            "Retrying entries one by one...")
        results = []
        for entry in entries:
            results.extend(self.translate_batch(
                [entry], batch_idx, total_batches,
                language_name, ctx, is_fallback=True))
        return results

    def translate_batch(self, entries, batch_idx, total_batches,
                        language_name, ctx, is_fallback=False):
        """Translate a batch of PO entries using the LLM.

        On count mismatch or error, retries each entry individually
        unless is_fallback=True, in which case returns empty strings.

        Args:
            entries: List of PO entries to translate.
            batch_idx: Index of the current batch (0-based).
            total_batches: Total number of batches.
            language_name: Full language name for the prompt.
            ctx: TranslationContext with glossary, examples, etc.
            is_fallback: If True, skip individual retry on failure.

        Returns:
            list: [(msgid, translation, locations), ...].
                On error with is_fallback=True, translation is empty string.
        """

        glossary_text = "\n".join(
            f"* '{en}': '{translated}'"
            for en, translated in ctx.glossary.items())
        system_prompt = ctx.system_prompt + glossary_text

        messages = [
            {
                "role": "system",
                "content": system_prompt.format(language_name=language_name),
            },
        ]

        # Add few-shot examples
        few_shot_inputs = [msgid for msgid, _ in ctx.few_shot_examples]
        few_shot_outputs = [msgstr for _, msgstr in ctx.few_shot_examples]

        messages.append({
            "role": "user",
            "content": (
                "Here are examples of translating a JSON array:\n"
                f"{json.dumps(few_shot_inputs, ensure_ascii=False)}"
            )
        })
        messages.append({
            "role": "assistant",
            "content": json.dumps(few_shot_outputs, ensure_ascii=False)
        })

        # Build translation request
        texts_to_translate = [entry.id for entry in entries]
        user_content = (
            f"Translate the following {len(texts_to_translate)} items.\n"
            "Your response MUST be a single, valid JSON array `[...]` "
            f"containing exactly {len(texts_to_translate)} "
            "translated strings in the same order."
            "Do NOT add any other text, explanations, "
            "or markdown formatting.\n\n"
            f"{json.dumps(texts_to_translate, ensure_ascii=False)}")

        messages.append({"role": "user", "content": user_content})

        # Call LLM and parse response
        try:
            translations = json.loads(ctx.call_llm_fn(messages))

            if not isinstance(translations, list):
                raise ValueError(
                    f"Expected JSON array, got {type(translations).__name__}")

            if len(translations) != len(entries):
                logger.warning(
                    f"[Batch {batch_idx + 1}/{total_batches}] "
                    "Translation count mismatch: "
                    f"expected {len(entries)}, got {len(translations)}")
                if is_fallback:
                    return [(entry.id, "", entry.locations)
                            for entry in entries]
                return self._retry_individually(
                    entries, batch_idx, total_batches, language_name, ctx)

            return [
                (entry.id, translation.strip().rstrip(']"').strip(),
                 entry.locations)
                for entry, translation in zip(entries, translations)
            ]

        except Exception as e:
            logger.error(
                f"[Batch {batch_idx + 1}/{total_batches}] "
                f"Error translating batch: {e}")
            if is_fallback:
                return [(entry.id, "", entry.locations) for entry in entries]
            return self._retry_individually(
                entries, batch_idx, total_batches, language_name, ctx)

    def translate_pot_file(self, pot_path, po_path, language_code,
                           language_name, batch_size, ctx):
        """Translate a POT file and save as PO.

        Reads entries from the POT file, translates them in parallel
        batches, and writes the results to a PO file.

        Args:
            pot_path: Path to the source POT file.
            po_path: Path to save the translated PO file.
            language_code: Target language code (e.g., 'ko_KR').
            language_name: Full language name for prompts.
            batch_size: Number of entries per translation batch.
            ctx: TranslationContext with glossary, examples, etc.
        """
        with open(pot_path, "rb") as f:
            pot = pofile.read_po(f)

        po = Catalog(
            locale=language_code,
            project=pot.project,
            version=pot.version,
            copyright_holder=pot.copyright_holder,
            msgid_bugs_address=pot.msgid_bugs_address,
            creation_date=pot.creation_date,
            language_team=pot.language_team,
            charset="UTF-8",
        )

        entries_to_translate = [entry for entry in pot if entry.id]
        total_entries = len(entries_to_translate)

        batches = self.create_batches(entries_to_translate, batch_size)
        total_batches = len(batches)

        logger.info(
            f"--- Translating {os.path.basename(pot_path)} "
            f"to {language_code} ---")
        logger.info(
            f"Total {total_entries} entries in {total_batches} batches "
            f"(batch_size: {batch_size}, workers: {ctx.max_workers})")

        # Translate in parallel
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=ctx.max_workers
        ) as executor:
            results = list(
                tqdm(
                    executor.map(
                        lambda args: self.translate_batch(
                            *args, language_name, ctx),
                        [(batch, i, total_batches)
                         for i, batch in enumerate(batches)]),
                    total=total_batches,
                    desc=f"Translating batches [{language_code}]",
                    unit="batch",
                ))

        for batch_result in results:
            for msgid, translation, locations in batch_result:
                po.add(
                    id=msgid, string=translation,
                    locations=locations,
                    user_comments=["Initial translation by AI."])

        try:
            with open(po_path, "wb") as f:
                pofile.write_po(f, po)
            logger.info(f"Saved: {po_path}")
        except Exception as e:
            logger.error(f"Failed to save PO file: {e}")

    def translate_language(self, lang_code, pot_path, po_filename,
                           config, resources, call_llm_fn):
        """Run the full translation pipeline for a single language.

        Loads glossary, few-shot examples, and system prompt, then
        translates the POT file and saves the experiment log.

        Args:
            lang_code: Target language code (e.g., 'ko_KR').
            pot_path: Path to the source POT file.
            po_filename: Output PO filename (e.g., 'neutron_lib.po').
            config: Parsed config dictionary.
            resources: ResourceLoader instance.
            call_llm_fn: LLM caller function.
        """
        lang_start_time = time.time()
        logger.info(f"--- [{lang_code}] Translation start ---")

        language_name = get_language_name(lang_code)

        glossary = resources.load_glossary(
            lang_code,
            glossary_dir=config['paths']['glossary_dir'],
            glossary_po_file=config['files']['glossary_po'],
        )
        few_shot_examples = resources.load_fixed_examples(
            lang_code,
            config['paths']['example_dir'],
            config['files']['fixed_json'],
            config['urls']['example'],
            config['files']['example_file'],
        )

        system_prompt = resources.load_support_prompt(lang_code)
        if system_prompt:
            logger.info(f"Using custom support prompt for {lang_code}")
        else:
            system_prompt = DEFAULT_SYSTEM_PROMPT

        ctx = TranslationContext(
            glossary=glossary,
            few_shot_examples=few_shot_examples,
            call_llm_fn=call_llm_fn,
            max_workers=config['ai']['workers'],
            system_prompt=system_prompt,
        )

        model = config['ai']['model']
        po_file_path = os.path.join(
            config['paths']['po_dir'], model, lang_code, po_filename)
        os.makedirs(os.path.dirname(po_file_path), exist_ok=True)

        self.translate_pot_file(
            pot_path, po_file_path,
            lang_code, language_name,
            config['ai']['batch_size'], ctx,
        )

        lang_duration = round(time.time() - lang_start_time, 2)
        logger.info(
            f"--- [{lang_code}] Translation end ({lang_duration}s) ---")


def get_args():
    parser = argparse.ArgumentParser(
        description="Run AI translation pipeline")
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to config YAML file (default: config.yaml)")
    return parser.parse_args()


def main():
    config = load_config(get_args().config)

    model = config['ai']['model']
    pot_path = os.path.join(
        config['paths']['pot_dir'], config['files']['pot_file'])

    if not os.path.exists(pot_path):
        raise FileNotFoundError(f"POT file not found: {pot_path}")

    po_filename = os.path.basename(pot_path).replace(".pot", ".po")
    resources = ResourceLoader(
        glossary_url=config['urls']['glossary'], prompt_dir=PROMPT_DIR)
    translator = AITranslator()
    call_llm_fn = AITranslator.build_llm_caller(model)

    logger.info(
        f"--- Translation Start | LLM: {model} "
        f"| Batch Size: {config['ai']['batch_size']} ---")

    start_time = time.time()
    for lang_code in config['languages']:
        translator.translate_language(
            lang_code, pot_path, po_filename, config, resources, call_llm_fn)

    logger.info(
        f"Total translation time: {round(time.time() - start_time, 2)}s")


if __name__ == "__main__":
    main()
