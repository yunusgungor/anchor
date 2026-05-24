"""
Anchor Engine — Merkezi Yapılandırma

Tüm magic constants, threshold'lar ve yapılandırma değerleri
bu dosyada toplanmıştır. Tek noktadan değiştirilebilir.
"""

import math
from typing import Final

# ============================================================
# BINARY INDEX
# ============================================================
BINARY_FORMAT_VERSION: Final[int] = 4  # v4: distinctive_keyword_index

# ============================================================
# DISTINCTIVE KEYWORD INDEX (TF-IDF)
# ============================================================
KEYWORD_MIN_LENGTH: Final[int] = 6          # <6 karakter keyword'ler topic eklemez
KEYWORD_MIN_WORD_LEN: Final[int] = 4         # Keyword index'teki minimum kelime uzunluğu
KEYWORD_MAX_ALLOWED_RATIO: Final[float] = 0.2  # ≤%20 rule'da geçen kelimeler keyword olur
KEYWORD_MAX_ALLOWED_MIN: Final[int] = 5     # En az 5 rule'da geçebilir (küçük kümelerde)

# ============================================================
# CLAIM EXTRACTION
# ============================================================
CLAIM_MIN_TERM_LEN: Final[int] = 4          # Claim extraction'da minimum alias uzunluğu
CLAIM_CONFIDENCE_BASE: Final[float] = 0.5   # Base confidence
CLAIM_CONFIDENCE_PER_WORD: Final[float] = 0.15  # Her kelime için eklenen confidence

# ============================================================
# FACT EXTRACTION
# ============================================================
FACT_MIN_LENGTH: Final[int] = 10            # Minimum fact uzunluğu (karakter)
FACT_NEAR_DUPE_THRESHOLD: Final[float] = 0.85  # Near-duplicate dedup eşiği

# ============================================================
# TOPIC EXTRACTION
# ============================================================
TOPIC_OUTPUT_MIN_LEN: Final[int] = 10       # Output-based topic extraction için minimum output uzunluğu
TOPIC_ALIAS_MIN_LEN: Final[int] = 4         # Topic alias'ları için minimum uzunluk
TOPIC_MAX_OUTPUT_RULES: Final[int] = 3      # Output-based discovery max rule sayısı
TOPIC_OUTPUT_KEYWORD_DENSITY_THRESHOLD: Final[float] = 0.15  # matched_keywords / total_keywords
TOPIC_DOMAIN_MAX_RULES: Final[int] = 2      # aynı domain'den en fazla bu kadar rule

# ============================================================
# WORKFLOW VALIDATION
# ============================================================
WF_STEP_CONFIDENCE: Final[float] = 0.6      # Step extraction minimum confidence
WF_ORDER_VIOLATION_PENALTY: Final[float] = 0.3  # Sıra ihlali ceza puanı
WF_ALIAS_CONFIDENCE: Final[float] = 0.6     # Step alias match confidence
WF_TERM_MAP_CONFIDENCE: Final[float] = 0.62 # TR→EN term map match confidence
WF_SEMANTIC_CONFIDENCE_MIN: Final[float] = 0.58  # Semantic step match minimum confidence
WF_SEMANTIC_SENTENCE_MIN_LEN: Final[int] = 12    # Semantic match için min cümle uzunluğu
WF_CHECK_FUZZY_MAX_DISTANCE: Final[int] = 2      # Levenshtein max distance
WF_COMPOUND_CHECK_MIN_WORDS: Final[int] = 2      # Compound check için min kelime sayısı

# ============================================================
# CONFLICT DETECTION
# ============================================================
CONFLICT_DEFAULT_THRESHOLD: Final[float] = 0.6   # Varsayılan conflict eşiği
CONFLICT_DYNAMIC_THRESHOLD_SHARED: Final[float] = 0.65  # 1 shared token threshold
CONFLICT_DYNAMIC_THRESHOLD_2: Final[float] = 0.8       # 2 shared tokens
CONFLICT_DYNAMIC_THRESHOLD_3: Final[float] = 0.85      # 3 shared tokens  
CONFLICT_DYNAMIC_THRESHOLD_4: Final[float] = 0.9       # 4+ shared tokens
CONFLICT_WRONG_DISTANCE_EXACT: Final[float] = 0.5      # Exact wrong claim match distance
CONFLICT_WRONG_DISTANCE_SUFFIX: Final[float] = 0.55    # Suffix-tolerant match distance

# ============================================================
# PERFORMANCE
# ============================================================
HOT_CACHE_MAX: Final[int] = 200             # LRU hot cache max size
BLOOM_EXPECTED_ITEMS: Final[int] = 10_000   # Bloom filter expected items
BLOOM_FP_RATE: Final[float] = 0.01          # Bloom filter false positive rate
SEMANTIC_MAX_FEATURES: Final[int] = 2000    # TF-IDF semantic index max features

# ============================================================
# DOMAIN-SPECIFIC STOPWORDS
# ============================================================
# Bu kelimeler distinctive keyword index'te yer almaz
# (çok yaygın oldukları için false positive üretirler)
STOPWORDS: Final[set] = {
    # İngilizce temel
    'the', 'and', 'for', 'with', 'this', 'that', 'from', 'are', 'was',
    'is', 'not', 'but', 'or', 'as', 'to', 'of', 'in', 'on', 'at', 'by',
    'just', 'use', 'should', 'must', 'can', 'will', 'may',
    'used', 'using', 'based', 'also', 'well', 'need', 'make', 'way',
    'part', 'set', 'get', 'without', 'within', 'between', 'over',
    'first', 'last', 'next', 'each', 'many', 'some', 'any', 'all',
    'both', 'other', 'into', 'through', 'during', 'before', 'after',
    'above', 'below', 'up', 'down', 'out', 'off', 'under', 'again',
    'further', 'once', 'here', 'there', 'when', 'where', 'why',
    'how', 'what', 'which', 'who', 'whom', 'this', 'those', 'these',
    'about', 'across', 'along', 'among', 'around', 'beside', 'beyond',
    'despite', 'except', 'inside', 'outside', 'toward', 'towards',
    'underneath', 'throughout', 'because', 'therefore', 'however',
    'moreover', 'furthermore', 'nevertheless', 'nonetheless',
    'otherwise', 'thus', 'hence', 'namely', 'such', 'like', 'than',
    'rather', 'quite', 'hardly', 'scarcely', 'barely', 'nearly',
    'almost', 'mostly', 'mainly', 'primarily', 'largely', 'widely',
    'typically', 'usually', 'frequently', 'often', 'sometimes',
    'occasionally', 'rarely', 'seldom', 'commonly', 'generally',
    'normally', 'essentially', 'basically', 'roughly', 'approximately',
    'virtually', 'practically', 'simply', 'merely', 'purely',
    'truly', 'highly', 'deeply', 'strongly', 'clearly', 'obviously',
    'apparently', 'evidently', 'presumably', 'supposedly',
    'allegedly', 'reportedly', 'arguably', 'consequently',
    'accordingly', 'subsequently', 'previously', 'initially',
    'originally', 'eventually', 'ultimately', 'finally', 'lastly',
    'meanwhile', 'conversely', 'likewise', 'similarly', 'contrarily',
    'alternatively', 'specially', 'especially', 'particularly',
    'specifically', 'says', 'said', 'seen', 'given', 'taken',
    'called', 'known', 'made', 'come', 'came', 'go', 'goes',
    'went', 'take', 'took', 'see', 'saw', 'know', 'knew',
    'think', 'thought', 'want', 'wanted', 'tell', 'told',
    'give', 'gave', 'find', 'found', 'show', 'showed', 'shown',
    'bring', 'brought', 'leave', 'left', 'keep', 'kept',
    'hold', 'held', 'let', 'begin', 'began', 'begun',
    'feel', 'felt', 'mean', 'meant', 'run', 'ran',
    'move', 'moved', 'live', 'lived', 'work', 'worked',
    'seem', 'seemed', 'look', 'looked', 'become', 'became',
    'remain', 'remained', 'start', 'started', 'stop', 'stopped',
    'try', 'tried', 'ask', 'asked', 'need', 'needed',
    'place', 'places', 'point', 'points', 'case', 'cases',
    'fact', 'facts', 'side', 'sides', 'line', 'lines',
    'kind', 'kinds', 'sort', 'sorts', 'type', 'types',
    'form', 'forms', 'area', 'areas', 'group', 'groups',
    'number', 'numbers', 'system', 'systems',
    'thing', 'things', 'world', 'worlds', 'life', 'lives',
    'hand', 'hands', 'part', 'parts', 'result', 'results',
    'reason', 'reasons', 'difference', 'differences',
    'value', 'values', 'important', 'different', 'possible',
    'common', 'simple', 'basic', 'specific', 'general',
    'current', 'previous', 'following', 'above', 'below',
    'single', 'multiple', 'various', 'similar', 'separate',
    'entire', 'whole', 'complete', 'total', 'partial',
    'direct', 'indirect', 'primary', 'secondary', 'major',
    'minor', 'main', 'central', 'local', 'global',
    'overall', 'overview', 'summary', 'details', 'detail',
    'always', 'never', 'ever', 'very', 'much', 'still',
    'already', 'yet', 'now', 'then', 'than', 'too', 'also',
    'even', 'though', 'although', 'while', 'since', 'until',
    'every', 'everyone', 'everything', 'everywhere',
    'someone', 'something', 'somewhere', 'anyone', 'anything',
    'anywhere', 'nobody', 'nothing', 'both', 'either', 'neither',
    'upon', 'onto', 'into', 'within', 'without',
    # Türkçe temel
    'bir', 've', 'bu', 'ile', 'olan', 'gibi', 'kadar', 'ama',
    'sonra', 'önce', 'için', 'olarak', 'tarafından', 'ancak',
    'daha', 'çok', 'başka', 'kendi', 'aynı', 'her', 'tüm',
    'hem', 'ya', 'da', 'şey', 'değil', 'son', 'yeni',
    'iki', 'üç', 'vb', 'vs', 'dr', 'mr', 'no',
    # Domain generic
    'rules', 'principles', 'standards', 'guide', 'cycle',
    'process', 'practices', 'patterns', 'about',
    'testing', 'management', 'production', 'naming', 'clean',
    # Generic coding keywords (false positive kaynağı)
    'import', 'export', 'extends', 'implements',
    'return', 'yield', 'raise', 'except', 'finally',
    'lambda', 'global', 'nonlocal', 'assert', 'del',
    'break', 'continue', 'pass', 'elif', 'else',
    'default', 'static', 'dynamic', 'abstract',
    'synchronized', 'volatile', 'transient',
    'prototype', 'constructor', 'typeof', 'instanceof',
    'void', 'null', 'undefined', 'nan', 'infinity',
    'console', 'require', 'module', 'exports',
    # Generic everyday words (false positive kaynağı)
    'today', 'yesterday', 'tomorrow', 'morning', 'evening',
    'afternoon', 'night', 'week', 'month', 'year',
    'time', 'times', 'day', 'days', 'date', 'dates',
    'server', 'client', 'user', 'users', 'data',
    'print', 'input', 'output',
    'hello', 'world', 'test', 'tests', 'name', 'names',
    'page', 'pages', 'key', 'keys', 'file', 'files',
    'list', 'lists', 'array', 'object', 'objects',
    'class', 'classes', 'method', 'methods',
    'string', 'number', 'integer', 'float', 'bool',
    'true', 'false', 'none', 'null', 'zero', 'one', 'two',
    'running', 'sleep', 'wait', 'stand', 'sit',
    'weather', 'temperature', 'city', 'country',
    'food', 'water', 'air', 'home', 'house', 'room',
    'door', 'window', 'table', 'chair', 'book',
    'read', 'write', 'speak', 'talk', 'walk', 'play',
    'big', 'small', 'large', 'little', 'great', 'good',
    'bad', 'new', 'old', 'long', 'short', 'high', 'low',
    'fast', 'slow', 'hard', 'soft', 'easy',
    'right', 'wrong', 'real', 'same', 'different',
    'free', 'open', 'close', 'start', 'end', 'begin',
    'top', 'bottom', 'front', 'back', 'left',
    'where', 'here', 'there',
    'who', 'whom', 'whose', 'which', 'what', 'why', 'how',
    'normal', 'special', 'regular', 'daily', 'weekly',
    'monthly', 'yearly', 'annual', 'permanent', 'temporary',
    'active', 'passive', 'public', 'private', 'internal',
    'external', 'native', 'remote', 'local', 'global',
    'source', 'target', 'origin', 'destination',
    'scope', 'range', 'length', 'size', 'volume',
    'color', 'shape', 'image', 'picture', 'photo',
    'sound', 'voice', 'music', 'video', 'text',
    'word', 'letter', 'character', 'symbol', 'sign',
    'drive', 'click', 'press', 'hold', 'drag', 'drop',
    'sort', 'order', 'sequence', 'pattern', 'format',
    'empty', 'full', 'clean', 'dirty', 'fresh', 'stale',
    'state', 'status', 'mode', 'type', 'kind',
    'action', 'event', 'signal', 'message', 'notice',
    'group', 'team', 'member', 'leader', 'owner',
    'role', 'task', 'job', 'duty', 'goal',
    'plan', 'idea', 'view', 'opinion', 'thought',
    'weight', 'height', 'depth', 'width', 'angle',
    'degree', 'rate', 'price', 'cost', 'fee', 'tax', 'budget',
    'allow', 'enable', 'disable', 'grant', 'deny',
    'support', 'help', 'aid', 'assist',
    'check', 'verify', 'confirm', 'validate', 'ensure',
    'create', 'make', 'build', 'form', 'produce',
    'update', 'change', 'modify', 'edit', 'revise',
    'delete', 'remove', 'clear', 'erase', 'cancel',
    'add', 'insert', 'attach', 'include', 'append',
    'connect', 'link', 'join', 'merge', 'combine',
    'split', 'divide', 'separate', 'break', 'cut',
    'send', 'receive', 'accept', 'reject', 'approve',
    'offer', 'provide', 'supply', 'deliver', 'return',
    'request', 'demand', 'require',
    'search', 'find', 'locate', 'track', 'follow',
    'show', 'display', 'present', 'reveal', 'expose',
    'hide', 'cover', 'mask', 'disguise', 'protect',
    'random', 'specific', 'particular', 'certain',
    'domain', 'context', 'environment', 'situation',
    # code/function/design (too generic for aliases)
    'code', 'function', 'design', 'name', 'error',
    'architecture', 'structure', 'style', 'guide',
    # Additional FP fixes
    'sentence', 'paragraph', 'meaning', 'random',
}

# ============================================================
# DOMAIN SYNONYM MAP (ClaimExtractor için)
# ============================================================
DOMAIN_SYNONYMS: Final[list[tuple[str, list[str]]]] = [
    ("pipeline", ["ci/cd", "ci", "cd", "build pipeline"]),
    ("retrospective", ["retro", "retros", "retrospective"]),
    ("retrospectives", ["retro", "retros", "postmortem", "post-mortem"]),
    ("architecture", ["arch", "system design", "architectural"]),
    ("release", ["deploy", "go-live", "ship", "release process"]),
    ("refinement", ["grooming", "backlog grooming", "backlog refinement"]),
    ("singleton", ["singleton pattern"]),
    ("tdd", ["test-driven", "test driven", "tdd cycle"]),
    ("code review", ["pr review", "peer review", "code review process"]),
    ("branching", ["git branch", "branch strategy", "branching model"]),
]

# ============================================================
# RULE DOMAINS (output-based clustering)
# ============================================================
RULE_DOMAIN_MAP: Final[dict[str, str]] = {
    'incident-response': 'workflow-ops',
    'release-process': 'workflow-ops',
    'bug-fix': 'workflow-dev',
    'code-review': 'workflow-dev',
    'tdd-cycle': 'workflow-dev',
    'story-implementation': 'workflow-dev',
    'architecture-decision': 'workflow-arch',
    'clean-architecture': 'architecture',
    'solid-principles': 'architecture',
    'design-patterns': 'architecture',
    'pipeline-standards': 'delivery',
    'automated-testing': 'delivery',
    'adr': 'documentation',
    'retrospectives': 'process',
    'agile-and-refinement': 'process',
    'branching-and-commits': 'git',
    'secure-coding': 'security',
    'test-pyramid': 'testing',
    'red-green-refactor': 'testing',
    'mocking-guide': 'testing',
    'naming-and-structure': 'clean-code',
    'function-design': 'clean-code',
    'error-handling': 'clean-code',
}

# ============================================================
# DIAGRAM CONSTANTS
# ============================================================

# Diagram extraction
DIAGRAM_MIN_NODES: Final[int] = 2       # En az 2 node'lu diyagram anlamlı
DIAGRAM_MIN_EDGES: Final[int] = 1       # En az 1 edge
DIAGRAM_MAX_FLOW_DEPTH: Final[int] = 10 # Flow traversal max derinlik
DIAGRAM_MAX_FLOWS: Final[int] = 5       # Maksimum flow sayısı (loopback patlamasını önle)
DIAGRAM_TERM_MIN_LENGTH: Final[int] = 3 # Node label'ından term min length

# Diagram-based flow matching
FLOW_VIOLATION_SEVERITY: Final[str] = "WARNING"  # Flow ihlali severity

# Diagram to fact çevirimi
DIAGRAM_FACT_PREFIX: Final[str] = "[D] "  # Diagram fact'lerini işaretle

# ============================================================
# AUTO-ALIAS EXCLUDED WORDS
# ============================================================
AUTO_ALIAS_EXCLUDED: Final[set] = {
    'rules', 'principles', 'standards', 'guide', 'cycle',
    'process', 'practices', 'about', 'and', 'the', 'for',
    'with', 'testing', 'management', 'production',
    'naming', 'clean',
    'code', 'function', 'design', 'name', 'error',
    'architecture', 'structure', 'style', 'guide',
}
