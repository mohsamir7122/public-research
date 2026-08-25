# Medical Research Workbench

منصة عامة قابلة للتكرار لإدارة مشروع بحث طبي من Topic أولي إلى حزمة بحث قابلة للتدقيق، مع تركيز مبدئي على Orthopaedics وSports Medicine. الغرض هو أن يظل الباحث والمساعد في مشروع واحد عبر جلسات متعددة، لا أن تُستبدل القرارات العلمية أوالمسؤولية البشرية بأتمتة شكلية.

## الحالة الحالية

الإصدار 0.2.0 ينفذ ويختبر المسارات الآتية:

- فتح Topic مختصر كـprovisional checkpoint مع Blockers واضحة، من دون تسميته Protocol مكتملًا.
- مسار مستقل للـOriginal Study أوThesis: feasibility، protocol، ethics/governance، registration applicability، data dictionary، Statistical Analysis Plan، data lock، analysis، reporting، QA، وrelease gates.
- ثلاثة مسارات للمراجعات: systematic_review، وsystematic_review_with_meta_analysis، وumbrella_review.
- تحويل المصطلح غير الدقيق “meta-meta-analysis” إلى umbrella_review أوOverview of Reviews.
- Manifest حتمي ومبني على Content Fingerprint، وproject-state.json قابل للاستكمال، وTransition hash chain تكشف التعديلات غير المتسقة.
- بوابات لا تقبل True أوعبارة “approved” كدليل؛ كل Gate تحتاج Artifact داخل المشروع، وSHA-256 مطابقًا، وتاريخًا غير مستقبلي، ومراجعين بشريين مسجلين.
- اشتقاق PRISMA 2020 flow من Event Ledger مع قرارين بشريين مستقلين، واشتقاق PRIOR review-selection flow للـUmbrella Review.
- Citation matrix وCorrected Covered Area ضمن Comparison وOutcome وTime point محددة.
- Generic inverse-variance calculation check للـfixed/random effects مع Paule–Mandel، وإجبار Ratio measures على Log scale، ومنع Pooling بلا Approval artifact موقع من شخصين.
- بناء Search Strategies أولية لـPubMed وScopus وWeb of Science وEmbase، وDeduplication محافظ بالـDOI ثم Title+Year عند غياب DOI.
- فحص المستودع لمنع الأسرار، وبيانات المرضى، والـFull text غير المصرح به، مع Unit Tests وCI.

## طريقة العمل من Topic إلى مشروع

ابدأ بأحد مستويين:

1. Topic مختصر: ينشئ حالة provisional ويحدد الأسئلة الناقصة.
2. Professional intake: يجمد Route وStructured question والنطاق والمراجعين البشر، ثم يفتح الـevidence-gated workflow المناسب.

الـSkill المرفق يحافظ على التعاون عبر الجلسات:

    Use $orthopaedic-publication-workbench to open this topic as a persistent project.
    Normalize the question, choose the defensible route, preserve every decision,
    and stop at any gate that needs my confirmation or independent human review.

أسماء الأشخاص في ملفات examples/ بيانات اصطناعية للاختبار والشرح؛ يجب استبدالها بأسماء المسؤولين الحقيقيين قبل بدء مشروع فعلي.

## Quick start

يتطلب Python 3.11 أو أحدث.

    python -m pip install -e .
    python -m unittest discover -s tests -v
    python scripts/audit_repository.py .

فتح Topic أولي:

    python -m medical_research init-topic --topic examples/provisional_topic.example.json --output output/topic-project

بدء رسالة أوOriginal Study بعد اكتمال الـprofessional intake:

    python -m medical_research init-original-study --topic examples/original_study_topic.example.json --output output/original-study

بدء Systematic Review + Meta-analysis:

    python -m medical_research init-review --topic examples/systematic_review_meta_topic.example.json --output output/acl-review

بدء Umbrella Review؛ قيمة meta-meta analysis في المثال تُطبّع تلقائيًا:

    python -m medical_research init-review --topic examples/umbrella_review_topic.example.json --output output/acl-umbrella

كل Transition يأخذ ملف Evidence JSON. كل مفتاح مطلوب في الـGate يحمل Artifact path وSHA-256 وverified_by وverified_on وnote. ثم:

    python -m medical_research advance-review --project output/acl-review --evidence evidence/topic-intake-gate.json --reviewer "Named Human One" --decision-date YYYY-MM-DD

الأوامر الأخرى:

    python -m medical_research derive-prisma --help
    python -m medical_research derive-prior --help
    python -m medical_research assess-overlap --help
    python -m medical_research run-meta --help

والقدرات السابقة ما تزال متاحة:

    python -m medical_research build-search --config examples/research_question.example.json --output output/search_strategy.json
    python -m medical_research run-pilot --config pilots/acl-remnant-proprioception/question.json --records pilots/acl-remnant-proprioception/records.json --output output/acl-remnant-proprioception.json

## حدود الحقيقة

المستودع ينظم الأدلة، يتحقق من البنية والـchecksums، يمنع تخطي المراحل، ويجري حسابات محددة. لكنه لا:

- يخلق Ethics approval أوRegistration أوبيانات أونتائج أوCitations.
- يجعل AI هو المراجع البشري الثاني أوالمؤلف المسؤول.
- يثبت صحة محتوى Artifact لمجرد أن Hash الخاص به مطابق.
- يحول الـhash chain إلى توقيع رقمي أو يثبت هوية من عدّل الملفات؛ سلامة الحالة هنا فحص اتساق وليست مصادقة مشفرة.
- يجعل دراستين قابلتين للـPooling لمجرد وجود رقمين.
- يحول Calculation check الحالي إلى تحليل نهائي للتصميمات المعقدة؛ multi-arm، dependent effects، rare events، diagnostic accuracy، network، Bayesian، IPD، وmeta-regression تحتاج Extension متخصصًا ومراجعة إحصائية.
- يضمن Novelty أوقبول مجلة أوPublication أوخلو النص من Plagiarism.
- ينفذ تلقائيًا بحثًا شاملًا داخل قواعد مدفوعة أويدخل إلى Subscription full text بلا صلاحية مشروعة.

أي Capability غير مغطاة بمسار تنفيذي واختبار تظل validator_not_implemented، حتى لو كانت موجودة في الخطة أوالتوثيق.

## حدود المستودع العام

لا ترفع بيانات مرضى، أوصورًا قابلة للتعرف، أوHospital exports، أوSubscription PDFs، أوكتبًا محمية، أوAPI keys، أوManuscripts غير منشورة دون قرار صريح. راجع [DATA_POLICY.md](DATA_POLICY.md) و[SECURITY.md](SECURITY.md).

Raw inputs لا تُعدّل، وكل طبقة مشتقة تحتفظ بـProvenance. Official Author Guidelines هي المرجع النهائي لمتطلبات المجلة، وReporting checklist ليست إثباتًا لصحة المنهجية.

## المنهجية

راجع:

- [Workflow](docs/WORKFLOW.md)
- [Research integrity](RESEARCH_INTEGRITY.md)
- [Systematic-review methods standard](skills/orthopaedic-publication-workbench/references/systematic-review-methods.md)
- [Skill operating instructions](skills/orthopaedic-publication-workbench/SKILL.md)

## License

الكود مرخّص بموجب Apache-2.0. لا يمتد الترخيص تلقائيًا إلى المقالات أوالصور أوMetadata الخارجية؛ تبقى حقوق كل مصدر كما هي موثقة في Provenance الخاصة به.
