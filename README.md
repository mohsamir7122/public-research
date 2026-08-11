# Medical Research Workbench

منصة عامة قابلة للتكرار لإدارة البحث الطبي، مع تركيز مبدئي على **Orthopaedics** و**Sports Medicine**. يبدأ المشروع من سؤال بحثي منظم، ثم يبني Search Strategy قابلة للتدقيق، ويستورد السجلات ويزيل التكرار، ويجهز ملفات Screening وData Extraction وRisk of Bias وStatistical Analysis Plan.

## الحالة الحالية

هذه نسخة تأسيسية تشغيلية وليست نظامًا مكتملًا لإنتاج بحث أو Manuscript تلقائيًا. القدرات المنفذة حاليًا:

- بناء استعلامات أولية لـPubMed وScopus وWeb of Science وEmbase من ملف JSON منظم.
- إزالة التكرار بالـDOI أولًا، ثم بالعنوان والسنة فقط عندما لا يوجد DOI متعارض.
- قوالب منظمة للـProtocol وSearch Log وScreening وData Extraction وRisk of Bias وStatistical Analysis Plan.
- فحص المستودع لمنع الأسرار والبيانات الحساسة والـFull text غير المصرح به.
- اختبارات آلية وCI.

الـScreening الذكي، وPRISMA، وEvidence tables، وJournal verification، وManuscript authoring ما تزال Roadmap ولا يجوز وصفها كقدرات منفذة قبل إضافتها واختبارها.

## Quick start

يتطلب Python 3.11 أو أحدث.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v

python -m medical_research build-search \
  --config examples/research_question.example.json \
  --output output/search_strategy.json

python scripts/audit_repository.py .
```

## حدود المستودع العام

لا ترفع بيانات مرضى، أو صورًا قابلة للتعرف، أو ملفات مستشفى، أو Subscription PDFs، أو كتبًا محمية، أو API keys، أو Manuscripts غير منشورة دون قرار صريح. راجع [DATA_POLICY.md](DATA_POLICY.md) و[SECURITY.md](SECURITY.md).

## منهجية القرار

- Raw inputs لا تُعدّل؛ كل تحويل ينتج طبقة مشتقة مع Provenance.
- لا يُعامل Link أوSnippet على أنه دليل تم التحقق منه.
- لا يُحوّل أي Score إلى Acceptance probability.
- Official Author Guidelines هي المرجع النهائي لمتطلبات المجلة.
- لا يُدمج سجلان لهما DOI مختلفان تلقائيًا حتى لو تشابه العنوان.

## License

لم يُحدَّد ترخيص إعادة الاستخدام بعد. كون المستودع Public لا يمنح تلقائيًا حق إعادة استخدام محتواه خارج ما تسمح به قوانين GitHub وحقوق النشر.
