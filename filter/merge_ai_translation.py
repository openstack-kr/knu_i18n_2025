import polib
import os

def merge_ai_translation(base_po_path, ai_po_path, output_po_path):
    """
    base_po_path: 원문 po (예: nova/en/LC_MESSAGES/nova.po)
    local_po_path: AI가 번역한 po 파일
    output_po_path: 생성할 최종 번역 po 파일 (예: nova/ko/LC_MESSAGES/nova.po)
    """

    base_po_path =
    local_po_path = 
    output_po_path = 

    base_po = polib.pofile(base_po_path)
    ai_po = polib.pofile(ai_po_path)

    # AI 번역 파일을 dict로 변환 (msgid 기반 검색)
    ai_map = {e.msgid: e for e in ai_po}

    applied_count = 0
    skipped_count = 0

    # 원문을 기준으로 msgstr 채워 넣기
    for entry in base_po:
        ai_entry = ai_map.get(entry.msgid)

        if ai_entry and ai_entry.msgstr.strip() != "":
            # AI 번역이 존재하면 삽입
            entry.msgstr = ai_entry.msgstr
            applied_count += 1
        else:
            # AI 번역이 없으면 msgstr은 빈 상태 유지
            skipped_count += 1

    # 저장
    os.makedirs(os.path.dirname(output_po_path), exist_ok=True)
    base_po.save(output_po_path)

    print("✔ Merge complete!")
    print(f" - AI 번역 적용된 항목: {applied_count}")
    print(f" - 번역 없음(유지된) 항목: {skipped_count}")
    print(f" - 저장됨: {output_po_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: python merge_ai_translation.py base.po ai.po output.po")
        sys.exit(1)

    merge_ai_translation(sys.argv[1], sys.argv[2], sys.argv[3])
