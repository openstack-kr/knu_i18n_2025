"""
Key Features:
    - POT → PO 변환 자동화
    - 다국어 번역 지원
    - 병렬 스레드 기반 번역
    - Glossary(용어집) 기반 일관성 유지
    - LLM 모델 (Ollama / Qwen / Llama 등) 교체 가능 구조
    - 번역 결과 및 실험 로그 자동 저장 (CSV 기반)
    - Git 정보 포함 실험 기록

Execution Flow:
    1. utils.argparse로 CLI 인자값을 수신
    2. POT 폴더 생성 및 파일 다운로드
    3. load_glossary()로 언어별 glossary 파일 다운로드 및 로드
    4. load_fixed_examples()로 언어별 예시 로드
    5. translate_pot_file()-> translate_batch()에서 병렬 배치 번역 및 tqdm 표시
    6. save_experiment_log()로 결과 기록 및 Git 메타데이터 저장
"""

import ollama
import os
import time
import concurrent.futures
import json
import argparse
from dataclasses import dataclass
from typing import Callable
from tqdm import tqdm
from babel.messages import pofile, Catalog

from utils import TranslationUtils


LANG_MAP = {
    "vi_VN": "Vietnamese (Vietnam)",
    "ur": "Urdu",
    "tr_TR": "Turkish (Turkey)",
    "Th": "Thai",
    "te_IN": "Telugu (India)",
    "ta": "Tamil",
    "es_MX": "Spanish (Mexico)",
    "es": "Spanish",
    "sl_SI": "Slovenian (Slovenia)",
    "sr": "Serbian",
    "ru": "Russian",
    "Ro": "Romanian",
    "pa_IN": "Punjabi (India)",
    "pt_BR": "Portuguese (Brazil)",
    "pt": "Portuguese",
    "pl_PL": "Polish (Poland)",
    "fa": "Persian",
    "ne": "Nepali",
    "mr": "Marathi",
    "mni": "Manipuri",
    "mai": "Maithili",
    "lo": "Lao",
    "ko_KR": "Korean (South Korea)",
    "kok": "Konkani",
    "ks": "Kashmiri",
    "kn": "Kannada",
    "ja": "Japanese",
    "it": "Italian",
    "id": "Indonesian",
    "hu": "Hungarian",
    "hi": "Hindi",
    "he": "Hebrew",
    "gu": "Gujarati",
    "el": "Greek",
    "de": "German",
    "ka_GE": "Georgian (Georgia)",
    "fr": "French",
    "fi_FI": "Finnish (Finland)",
    "fil": "Filipino",
    "eo": "Esperanto",
    "en_US": "English (United States)",
    "en_GB": "English (United Kingdom)",
    "en_AU": "English (Australia)",
    "nl_NL": "Dutch (Netherlands)",
    "cs": "Czech",
    "zh_TW": "Chinese (Taiwan)",
    "zh_CN": "Chinese (China)",
    "ca": "Catalan",
    "bg_BG": "Bulgarian (Bulgaria)",
    "brx": "Bodo",
    "bn_IN": "Bengali (India)",
    "as": "Assamese",
    "ar": "Arabic",
    "sq": "Albanian",
}

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")

DEFAULT_SYSTEM_PROMPT = """
    You are a strict translation engine.
    You are translating from English to {language_name}.

    [Output Format Rules (MUST Follow)]
    * Respond ONLY with the raw, translated text for {language_name}.
    * Your answer MUST be 100% in {language_name}.
    * Do NOT mix in any other languages (including English).
    * Do NOT add explanations, comments, apologies, or quotes.

    [Critical Preservation Rules (MUST Follow)]
    * Preserve all reStructuredText (RST) syntax exactly.
    * Preserve all placeholders exactly.
    * Preserve all HTML tags exactly.
    * You MUST use the exact translations provided in the `[Glossary]` section.

    [Anti-Hallucination Rules (MUST Follow)]
    * You MUST NOT add placeholders that are NOT in the original `msgid`.
    * You MUST NOT repeat phrases. Repetition is strictly forbidden.

    [Glossary]
    """


@dataclass
class TranslationContext:
    glossary: dict
    few_shot_examples: list
    call_llm_fn: Callable
    max_workers: int
    start: int | None
    end: int | None
    system_prompt: str


class AITranslator:
    """번역 파이프라인 전체를 관리하는 메인 클래스"""

    def __init__(self, utils: TranslationUtils):
        self.utils = utils

    def build_llm_caller(self, llm_mode: str, model_name: str) -> Callable:
        """
        LLM 백엔드를 선택하여 호출 함수를 생성하고 반환한다.
        CI 환경에서는 ollama만 지원함.
        """
        if llm_mode != "ollama":
            raise ValueError(
                f"CI environment only supports 'ollama' mode. "
                f"Got: {llm_mode}"
            )

        def _call(messages):
            response = ollama.chat(
                model=model_name,
                messages=messages,
                stream=False,
                options={
                    "temperature": 0,
                    "top_p": 1,
                    "repetition_penalty": 1.2,
                },
            )
            return response["message"]["content"].strip()

        return _call

    def load_support_prompt(self, language_code: str) -> str | None:
        """언어별 커스텀 프롬프트 파일이 있으면 로드, 없으면 None 반환."""
        prompt_path = os.path.join(PROMPT_DIR, f"{language_code}.txt")
        if os.path.isfile(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return None

    def translate_batch(self, payload, language_name, ctx: TranslationContext):
        """
        여러 entry를 batch로 묶어 LLM을 사용해 번역하는 함수.
        Translates a batch of PO/POT entries using the selected LLM model.

        Args:
            payload (tuple): (entries, batch_index, total_batches)
            language_name (str): 번역하는 언어 이름
            ctx (TranslationContext): 번역에 필요한 컨텍스트 객체

        Returns:
            list: [(msgid, translation, locations), ...]
                    - 정상일 때: translation에 번역 문자열이 채워진다.
                    - 오류/파싱 실패 시: translation(msgstr)을 빈 문자열("")로 둔 채 반환 반환한다.
        """
        entries, batch_idx, total_batches = payload

        glossary_text = "\n".join(
            f"* '{en}': '{ko}'" for en,
            ko in ctx.glossary.items())
        system_prompt = ctx.system_prompt + glossary_text

        messages = [
            {
                "role": "system",
                "content": system_prompt.format(language_name=language_name),
            },
        ]

        # Few-shot 예시 추가 (batch 형식)
        example_input = [msgid for msgid, _ in ctx.few_shot_examples]
        example_output = [msgstr for _, msgstr in ctx.few_shot_examples]

        messages.append({
            "role": "user",
            "content": (
                "Here are examples of translating a JSON array:\n"
                f"{json.dumps(example_input, ensure_ascii=False)}"
            )
        })
        messages.append({
            "role": "assistant",
            "content": json.dumps(example_output, ensure_ascii=False)
        })

        # 실제 번역할 텍스트들을 JSON 배열로 구성
        texts_to_translate = [entry.id for entry in entries]
        user_content = (
            f"Translate the following {len(texts_to_translate)} items.\n"
            f"Your response MUST be a single, valid JSON array `[...]` "
            f"containing exactly {len(texts_to_translate)} translated strings "
            "in the same order."
            "Do NOT add any other text, explanations, or markdown formatting.\n\n"
            f"{json.dumps(texts_to_translate, ensure_ascii=False)}")

        messages.append({"role": "user", "content": user_content})

        try:
            translation_text = ctx.call_llm_fn(messages)

            # JSON 파싱 시도
            try:
                translations = json.loads(translation_text)
            except json.JSONDecodeError:
                print(
                    f"!!! Batch [{batch_idx + 1}/{total_batches}] "
                    "JSON parsing failed, trying to extract array !!!")
                print("Falling back: extract simple array for this batch.")
                start = translation_text.find('[')
                end = translation_text.rfind(']') + 1
                if start != -1 and end != 0:
                    translations = json.loads(translation_text[start:end])
                else:
                    raise ValueError("Cannot extract JSON array from response")

            # 번역 결과와 entry 매칭
            if len(translations) != len(entries):
                print(
                    (
                        "!!! Batch [{idx}/{total}] Translation count mismatch: "
                        "expected {expected}, got {actual} !!!"
                    ).format(
                        idx=batch_idx + 1,
                        total=total_batches,
                        expected=len(entries),
                        actual=len(translations),
                    )
                )
                print("Falling back: leaving msgstr empty for this batch.")
                return [(entry.id, "", entry.locations) for entry in entries]

            return [(entry.id, translation.strip(), entry.locations)
                    for entry, translation in zip(entries, translations)]

        except Exception as e:
            print(
                (
                    "!!! Batch [{idx}/{total}] Error translating batch: "
                    "{error} !!!"
                ).format(
                    idx=batch_idx + 1,
                    total=total_batches,
                    error=e,
                )
            )
            return [(entry.id, "", entry.locations) for entry in entries]

    def create_batches(self, entries, batch_size):
        """
        Entry 리스트를 지정된 크기의 batch로 분할하는 함수.

        Args:
            entries (list): 전체 entry 리스트
            batch_size (int): 각 batch의 크기

        Returns:
            list: batch로 분할된 entry 리스트의 리스트
        """
        batches = []
        for i in range(0, len(entries), batch_size):
            batches.append(entries[i:i + batch_size])
        return batches

    def translate_pot_file(
            self,
            pot_path,
            po_path,
            language_code,
            language_name,
            batch_size,
            ctx: TranslationContext):
        """
        POT 파일을 읽어 batch 단위로 병렬 번역 후 PO 파일로 저장하는 함수.

        Args:
            pot_path (str): 원본 POT 파일 경로
            po_path (str): 번역된 결과를 저장할 PO 파일 경로
            language_code (str): 번역하는 언어 코드
            language_name (str): 번역하는 언어 이름
            batch_size (int): 한 번에 번역할 entry 개수
            ctx (TranslationContext): 번역에 필요한 컨텍스트 객체
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

        # start/end 범위 제한 적용
        if ctx.start is not None or ctx.end is not None:
            start_idx = ctx.start if ctx.start is not None else 0
            end_idx = ctx.end if ctx.end is not None else len(entries_to_translate)
            entries_to_translate = entries_to_translate[start_idx:end_idx]
        total_entries = len(entries_to_translate)

        batches = self.create_batches(entries_to_translate, batch_size)
        total_batches = len(batches)

        print(f"--- {os.path.basename(pot_path)}를 {language_code}로 번역 ---")
        print(
            f"총 {total_entries}개 entry를 {total_batches}개 batch로 나누어 번역합니다. "
            f"(Batch size: {batch_size}, Workers: {ctx.max_workers})"
        )

        payloads = [
            (batch, i, total_batches)
            for i, batch in enumerate(batches)
        ]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=ctx.max_workers
        ) as executor:
            results = list(
                tqdm(
                    executor.map(
                        lambda payload: self.translate_batch(
                            payload,
                            language_name,
                            ctx),
                        payloads),
                    total=total_batches,
                    desc=f"Translating batches [{language_code}]",
                    unit="batch",
                ))

        for batch_result in results:
            if batch_result:
                for msgid, translation, locations in batch_result:
                    po.add(id=msgid, string=translation, locations=locations,
                           user_comments=["Initial translation by AI."])

        try:
            with open(po_path, "wb") as f:
                pofile.write_po(f, po)
            print(f"{po_path}가 저장되었습니다.")
        except Exception as e:
            print(f"PO 파일 저장 실패: {e}")


def get_args():
    """
    Ansible `tasks/main.yaml`에서 넘겨주는 인자들을 파싱합니다.
    기본값(default)은 Ansible의 `defaults/main.yaml`에서 관리하므로
    여기서는 값의 수신 여부와 타입만 지정합니다.
    """
    parser = argparse.ArgumentParser(description="Run AI Translation Pipeline")

    # 기존 인자
    parser.add_argument("--project", help="OpenStack project name (Deprecated, use repo-dir)")
    parser.add_argument("--repo-dir", required=True, help="Path to cloned repo.")
    
    # Ansible에서 주입받는 필수 인자들 (default 제거, required=True 추가)
    parser.add_argument("--model", required=True, help="LLM model name")
    parser.add_argument("--workers", type=int, required=True, help="Number of parallel workers")
    
    # start, end는 값이 없을 수도 있으니 required=False(기본)로 둡니다.
    parser.add_argument("--start", type=int, help="Start index for translation")
    parser.add_argument("--end", type=int, help="End index for translation")
    
    parser.add_argument("--pot_dir", required=True, help="Directory containing POT files")
    parser.add_argument("--po_dir", required=True, help="Directory to save PO files")
    parser.add_argument("--pot_file", required=True, help="Path to the specific POT file")
    
    parser.add_argument("--glossary_dir", required=True, help="Directory for glossary files")
    parser.add_argument("--example_dir", required=True, help="Directory for example PO files")
    
    # URL 템플릿 및 파일명들
    parser.add_argument("--glossary_url", required=True, help="URL template to download glossary.po")
    parser.add_argument("--glossary_po_file", required=True, help="Glossary PO filename")
    parser.add_argument("--glossary_json_file", required=True, help="Glossary JSON filename")
    parser.add_argument("--example_url", required=True, help="URL template to download example PO file")
    parser.add_argument("--example_file", required=True, help="Example PO filename")
    parser.add_argument("--fixed_example_json", required=True, help="Fixed examples JSON filename")
    
    parser.add_argument("--batch-size", type=int, required=True, help="Translation batch size")
    parser.add_argument("--languages", required=True, help="Comma-separated language codes to translate")

    return parser.parse_args()


def main():
    """
    메인 실행 블록.
    Handles argument parsing, environment setup, translation execution,
    and experiment logging.

    Steps:
        1. 인자 파싱 및 경로 초기화
        2. 언어별 Glossary 파일 및 예시 파일 다운로드 및 로드
        3. 모델별/언어별 폴더 생성 및 번역 수행
        4. 언어별 번역 결과 저장 및 Git 로그 기록
    """
    args = get_args()

    # 인자로 받은 언어 목록 문자열을 리스트로 변환 ("ko,ja" -> ["ko", "ja"])
    languages_to_translate = [lang.strip() for lang in args.languages.split(",") if lang.strip()]

    # -----------------------------
    # Initialization
    # -----------------------------
    utils = TranslationUtils(args.repo_dir, glossary_url=args.glossary_url)
    translator = AITranslator(utils)

    # -----------------------------
    # LLM Config
    # -----------------------------
    llm_mode = "ollama"  # CI 환경 고정값
    call_llm_fn = translator.build_llm_caller(llm_mode, args.model)

    print("=================================================")
    print(f"Translation Start, LLM: {args.model}, Batch Size: {args.batch_size}")
    print("=================================================\n")

    # 폴더 생성
    os.makedirs(args.pot_dir, exist_ok=True)
    os.makedirs(args.po_dir, exist_ok=True)
    os.makedirs(args.example_dir, exist_ok=True)

    pot_path = os.path.join(args.repo_dir, args.pot_dir, args.pot_file)

    if not os.path.exists(pot_path):
        raise FileNotFoundError(f"POT file not found: {pot_path}")
        
    base_name = os.path.basename(pot_path).replace(".pot", ".po")
    start_time = time.time()

    # --- 언어 루프 ---
    for lang_code in languages_to_translate:
        lang_start_time = time.time()
        print(f"--- [{lang_code}] Language Translation Start ---")

        # 1. 언어 이름 찾기 (LANG_MAP 사용)
        language_name = LANG_MAP.get(lang_code, lang_code)

        # 2. 언어별 glossary, 예시, 프롬프트 로드
        glossary = utils.load_glossary(
            lang_code,
            glossary_dir=args.glossary_dir,
            glossary_po_file=args.glossary_po_file,
            glossary_json_file=args.glossary_json_file
        )

        few_shot_examples = utils.load_fixed_examples(
            lang_code,
            args.example_dir,
            args.fixed_example_json,
            args.example_url,
            args.example_file
        )

        custom_prompt = translator.load_support_prompt(lang_code)
        if custom_prompt:
            print(f"Using custom support prompt for {lang_code}")
            system_prompt = custom_prompt
        else:
            system_prompt = DEFAULT_SYSTEM_PROMPT

        # 3. TranslationContext 생성
        ctx = TranslationContext(
            glossary=glossary,
            few_shot_examples=few_shot_examples,
            call_llm_fn=call_llm_fn,
            max_workers=args.workers,
            start=args.start,
            end=args.end,
            system_prompt=system_prompt,
        )

        # 4. 결과 저장 경로 설정 (모델명/언어코드/파일명)
        model_lang_folder = os.path.join(args.po_dir, args.model, lang_code)
        os.makedirs(model_lang_folder, exist_ok=True)
        po_file_path = os.path.join(model_lang_folder, base_name)

        # 5. 번역 실행
        translator.translate_pot_file(
            pot_path,
            po_file_path,
            lang_code,
            language_name,
            args.batch_size,
            ctx
        )

        lang_end_time = time.time()
        duration = round(lang_end_time - lang_start_time, 2)
        print(f"---[{lang_code}] Language Translation End ({duration}s)---\n")

        # 6. 로그 기록
        utils.save_experiment_log(
            model_name=args.model,
            pot_file=pot_path,
            po_file=po_file_path,
            duration_sec=duration,
            language=lang_code
        )
        
    end_time = time.time()
    total_duration = round(end_time - start_time, 2)
    print(f"Total translation time: {total_duration}s")


if __name__ == "__main__":
    main()