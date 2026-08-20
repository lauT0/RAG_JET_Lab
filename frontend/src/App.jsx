import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ChevronDown,
  Download,
  Moon,
  PanelRightClose,
  PanelRightOpen,
  Send,
  Sun,
  X,
} from 'lucide-react'

// =============================================================================
// MOCK DATA — replace this object (and the api helpers below) when wiring
// real /api/chat and /api/retrieve endpoints.
// =============================================================================
const MOCK = {
  corpus: { documentCount: 142, regions: ['Nigeria', 'Ghana'] },
  similarityThreshold: 0.55,
  exampleQuestions: [
    {
      id: 'ex1',
      label: 'Hiring in Lagos',
      text: 'How do Lagos startups typically hire and onboard early engineers?',
    },
    {
      id: 'ex2',
      label: 'Accra meetups',
      text: 'How do Accra developer communities organize meetups and keep them sustainable?',
    },
    {
      id: 'ex3',
      label: 'Infrastructure',
      text: 'What infrastructure constraints most often shape product decisions in Nigerian and Ghanaian startups?',
    },
    {
      id: 'ex4',
      label: 'Mentorship',
      text: 'What informal mentorship norms show up in West African tech communities?',
    },
  ],
  chunks: [
    {
      id: 'c1',
      title: 'State of Tech Talent in Lagos 2023',
      sourceType: 'report',
      country: 'Nigeria',
      score: 0.91,
      text: 'Early-stage Lagos startups often hire through personal networks and community Slack channels before posting publicly. Onboarding is frequently informal: new engineers shadow a senior for one to two weeks, with documentation treated as a living Google Doc rather than a formal handbook.',
    },
    {
      id: 'c2',
      title: 'DevFest Accra Community Notes',
      sourceType: 'transcript',
      country: 'Ghana',
      score: 0.87,
      text: 'Meetup organizers in Accra described rotating venues between coworking spaces and university labs to keep costs low. Continuity depends less on sponsorship than on a small core of volunteer facilitators who also run WhatsApp announcement groups.',
    },
    {
      id: 'c3',
      title: 'Building through blackouts — forum thread',
      sourceType: 'forum',
      country: 'Nigeria',
      score: 0.82,
      text: 'Several founders noted that unreliable power and expensive data shape architecture choices: offline-first UX, aggressive caching, and SMS fallbacks remain common even for products that appear fully digital to end users.',
    },
    {
      id: 'c4',
      title: 'Mentorship circles in Ghanaian tech',
      sourceType: 'blog',
      country: 'Ghana',
      score: 0.79,
      text: 'Informal mentorship often happens through church networks, alumni groups, and senior engineers who answer DMs after talks. Formal mentorship programs exist, but many junior developers report that the trusted path is still a personal introduction.',
    },
    {
      id: 'c5',
      title: 'CcHUB Ecosystem Interview Series',
      sourceType: 'transcript',
      country: 'Nigeria',
      score: 0.74,
      text: 'Interview participants described onboarding as relationship-building first: clarifying who to ask when stuck matters more than tooling checklists. Probation periods are common, but feedback cadence varies widely by team size.',
    },
    {
      id: 'c6',
      title: 'Ghana Tech Report — Connectivity chapter',
      sourceType: 'report',
      country: 'Ghana',
      score: 0.71,
      text: 'Intermittent connectivity in secondary cities pushes teams toward progressive enhancement and lighter client bundles. Product managers interviewed cited user empathy for low-bandwidth contexts as a cultural expectation, not only a technical constraint.',
    },
  ],
  groundedAnswers: {
    ex1: `Lagos startups often recruit early engineers through personal networks and community channels before public job posts.[1] Onboarding tends to be informal: new hires shadow a senior engineer for one to two weeks, with living docs rather than formal handbooks.[1][5] Relationship clarity—who to ask when stuck—is frequently treated as more important than tooling checklists during the first weeks.[5]`,
    ex2: `Accra meetup organizers often rotate venues between coworking spaces and university labs to control cost.[2] Sustainability hinges less on sponsorship than on a small volunteer core that also maintains WhatsApp announcement groups.[2] Continuity is social infrastructure as much as calendar logistics.`,
    ex3: `Unreliable power and expensive data frequently shape product decisions: offline-first patterns, caching, and SMS fallbacks remain common.[3] In Ghana, intermittent connectivity outside major hubs pushes teams toward progressive enhancement and lighter clients; low-bandwidth empathy is often described as a cultural expectation, not only a constraint.[6]`,
    ex4: `Informal mentorship frequently runs through church networks, alumni groups, and senior engineers who respond after talks or via DMs.[4] Formal programs exist, but many juniors still describe a trusted personal introduction as the primary path into guidance relationships.[4]`,
    default: `Across Nigerian and Ghanaian tech communities, hiring, learning, and product choices are shaped by dense social networks and infrastructure realities.[1][3] Community spaces—meetups, forums, and informal mentorship—often substitute for institutional onboarding pipelines.[2][4]`,
  },
  baseAnswers: {
    ex1: `Startups in major African cities often hire through a mix of job boards, referrals, and university pipelines. Onboarding typically includes orientation, tooling setup, and pairing with a buddy. Practices vary by company size and funding stage.`,
    ex2: `Developer communities usually organize meetups through Meetup.com, Discord, or social media, seeking sponsors for venues and refreshments. Consistency depends on organizer capacity and attendance.`,
    ex3: `Infrastructure challenges such as power and internet reliability can affect software architecture. Teams may optimize for offline use, reduce bandwidth, or design resilient sync strategies.`,
    ex4: `Mentorship in tech often includes formal programs and informal peer learning. Junior developers benefit from guidance on skills, career paths, and industry norms.`,
    default: `Tech ecosystems in West Africa include startups, communities, and educational initiatives. Practices around hiring, meetups, infrastructure, and mentorship vary by city and organization.`,
  },
}

const SOURCE_TYPES = ['report', 'blog', 'forum', 'transcript']
const COUNTRIES = ['Nigeria', 'Ghana']
const MODES = [
  { id: 'grounded', label: 'Grounded (RAG)' },
  { id: 'base', label: 'Base model' },
  { id: 'compare', label: 'Compare' },
]
const RUBRIC_DIMS = [
  { id: 'culturalAccuracy', label: 'Cultural accuracy' },
  { id: 'specificity', label: 'Specificity' },
  { id: 'hallucination', label: 'Hallucination' },
  { id: 'nuance', label: 'Nuance' },
]

const USE_MOCK = true // set false when FastAPI /api/chat & /api/retrieve are live

// -----------------------------------------------------------------------------
// API boundary — swap implementations here only
// -----------------------------------------------------------------------------
async function retrieveContext(query) {
  if (!USE_MOCK) {
    const res = await fetch('/api/retrieve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    })
    if (!res.ok) throw new Error('retrieve failed')
    return res.json()
  }

  await delay(280 + Math.random() * 220)
  const q = query.toLowerCase()
  const ranked = [...MOCK.chunks]
    .map((c) => {
      let boost = 0
      if (/lagos|hiring|onboard|hire/.test(q) && /lagos|hire|onboard/i.test(c.text + c.title))
        boost += 0.08
      if (/accra|meetup/.test(q) && /accra|meetup/i.test(c.text + c.title)) boost += 0.08
      if (/infra|power|connect|bandwidth|blackout/.test(q) && /power|connect|bandwidth|offline/i.test(c.text))
        boost += 0.08
      if (/mentor/.test(q) && /mentor/i.test(c.text + c.title)) boost += 0.08
      return { ...c, score: Math.min(0.98, c.score + boost - Math.random() * 0.02) }
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)

  return {
    chunks: ranked,
    latencyMs: Math.round(180 + Math.random() * 140),
  }
}

async function* streamChat({ query, mode, chunks }) {
  if (!USE_MOCK) {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, mode, chunk_ids: chunks?.map((c) => c.id) }),
    })
    if (!res.ok) throw new Error('chat failed')
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      yield decoder.decode(value, { stream: true })
    }
    return
  }

  const key = MOCK.exampleQuestions.find((e) => e.text === query)?.id ?? 'default'
  const grounded =
    chunks.length === 0
      ? 'I could not find sufficiently relevant context in the curated corpus for this question. Try rephrasing or narrowing to Nigeria/Ghana tech community practices covered in the collection.'
      : MOCK.groundedAnswers[key] || MOCK.groundedAnswers.default
  const base = MOCK.baseAnswers[key] || MOCK.baseAnswers.default

  if (mode === 'compare') {
    // Caller streams each side separately in compare mode
    yield* streamTokens(grounded)
    return
  }

  const text = mode === 'base' ? base : grounded
  yield* streamTokens(text)
}

async function* streamTokens(text) {
  const parts = text.split(/(\s+)/)
  for (const part of parts) {
    yield part
    await delay(12 + Math.random() * 28)
  }
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function cn(...xs) {
  return xs.filter(Boolean).join(' ')
}

// =============================================================================
// App
// =============================================================================
export default function App() {
  const [dark, setDark] = useState(() =>
    typeof window !== 'undefined'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
      : false,
  )
  const [mode, setMode] = useState('grounded')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false)
  const [activeChunks, setActiveChunks] = useState([])
  const [highlightedChunkId, setHighlightedChunkId] = useState(null)
  const [typeFilter, setTypeFilter] = useState(new Set())
  const [countryFilter, setCountryFilter] = useState(new Set())
  const [scores, setScores] = useState({})
  const listRef = useRef(null)
  const chunkRefs = useRef({})
  const abortRef = useRef(false)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages, streaming])

  const filteredChunks = useMemo(() => {
    return activeChunks.filter((c) => {
      if (typeFilter.size && !typeFilter.has(c.sourceType)) return false
      if (countryFilter.size && !countryFilter.has(c.country)) return false
      return true
    })
  }, [activeChunks, typeFilter, countryFilter])

  const scrollToChunk = useCallback((id) => {
    setHighlightedChunkId(id)
    setInspectorOpen(true)
    setMobileSheetOpen(true)
    requestAnimationFrame(() => {
      chunkRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  }, [])

  const updateScore = useCallback((messageId, patch) => {
    setScores((prev) => ({
      ...prev,
      [messageId]: { ...(prev[messageId] || {}), ...patch },
    }))
  }, [])

  const exportScores = useCallback(() => {
    const payload = messages
      .filter((m) => m.role === 'assistant')
      .map((m) => ({
        messageId: m.id,
        questionId: m.questionId,
        mode: m.answerMode,
        query: m.query,
        scores: scores[m.id] || null,
        meta: m.meta,
      }))
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `rag-eval-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [messages, scores])

  const send = useCallback(
    async (rawText) => {
      const query = (rawText ?? input).trim()
      if (!query || streaming) return

      abortRef.current = false
      setInput('')
      setStreaming(true)

      const userMsg = { id: uid(), role: 'user', content: query }
      setMessages((m) => [...m, userMsg])

      let chunks = []
      let retrieveLatency = 0
      if (mode !== 'base') {
        const retrieved = await retrieveContext(query)
        chunks = retrieved.chunks.filter((c) => c.score >= MOCK.similarityThreshold)
        retrieveLatency = retrieved.latencyMs
        setActiveChunks(retrieved.chunks)
      } else {
        setActiveChunks([])
      }

      const noContext = mode !== 'base' && chunks.length === 0
      const questionId = MOCK.exampleQuestions.find((e) => e.text === query)?.id ?? null

      if (mode === 'compare') {
        const groundedId = uid()
        const baseId = uid()
        setMessages((m) => [
          ...m,
          {
            id: groundedId,
            role: 'assistant',
            answerMode: 'grounded',
            comparePair: baseId,
            content: '',
            streaming: true,
            query,
            questionId,
            citations: chunks,
            meta: {
              retrievalCount: chunks.length,
              latencyMs: retrieveLatency,
              noContext,
            },
          },
          {
            id: baseId,
            role: 'assistant',
            answerMode: 'base',
            comparePair: groundedId,
            content: '',
            streaming: true,
            query,
            questionId,
            citations: [],
            meta: { retrievalCount: 0, latencyMs: 0, noContext: false },
          },
        ])

        const t0 = performance.now()
        let gText = ''
        const key = questionId ?? 'default'
        const gFull =
          chunks.length === 0
            ? 'I could not find sufficiently relevant context in the curated corpus for this question.'
            : MOCK.groundedAnswers[key] || MOCK.groundedAnswers.default
        for await (const token of streamTokens(gFull)) {
          if (abortRef.current) break
          gText += token
          setMessages((msgs) =>
            msgs.map((msg) => (msg.id === groundedId ? { ...msg, content: gText } : msg)),
          )
        }
        const gLatency = Math.round(performance.now() - t0 + retrieveLatency)

        let bText = ''
        const bFull = MOCK.baseAnswers[key] || MOCK.baseAnswers.default
        const t1 = performance.now()
        for await (const token of streamTokens(bFull)) {
          if (abortRef.current) break
          bText += token
          setMessages((msgs) =>
            msgs.map((msg) => (msg.id === baseId ? { ...msg, content: bText } : msg)),
          )
        }
        const bLatency = Math.round(performance.now() - t1)

        setMessages((msgs) =>
          msgs.map((msg) => {
            if (msg.id === groundedId)
              return {
                ...msg,
                streaming: false,
                meta: { ...msg.meta, latencyMs: gLatency },
              }
            if (msg.id === baseId)
              return {
                ...msg,
                streaming: false,
                meta: { ...msg.meta, latencyMs: bLatency },
              }
            return msg
          }),
        )
      } else {
        const asstId = uid()
        setMessages((m) => [
          ...m,
          {
            id: asstId,
            role: 'assistant',
            answerMode: mode,
            content: '',
            streaming: true,
            query,
            questionId,
            citations: mode === 'grounded' ? chunks : [],
            meta: {
              retrievalCount: mode === 'grounded' ? chunks.length : 0,
              latencyMs: retrieveLatency,
              noContext,
            },
          },
        ])

        const t0 = performance.now()
        let text = ''
        for await (const token of streamChat({ query, mode, chunks })) {
          if (abortRef.current) break
          text += token
          setMessages((msgs) =>
            msgs.map((msg) => (msg.id === asstId ? { ...msg, content: text } : msg)),
          )
        }
        const totalLatency = Math.round(performance.now() - t0 + (mode === 'grounded' ? retrieveLatency : 0))
        setMessages((msgs) =>
          msgs.map((msg) =>
            msg.id === asstId
              ? {
                  ...msg,
                  streaming: false,
                  meta: { ...msg.meta, latencyMs: totalLatency },
                }
              : msg,
          ),
        )
      }

      setStreaming(false)
    },
    [input, streaming, mode],
  )

  const toggleFilter = (set, value, setter) => {
    const next = new Set(set)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    setter(next)
  }

  // Pair compare messages for rendering
  const renderItems = useMemo(() => {
    const items = []
    const seen = new Set()
    for (const msg of messages) {
      if (seen.has(msg.id)) continue
      if (msg.role === 'user') {
        items.push({ type: 'user', msg })
        continue
      }
      if (msg.comparePair) {
        const pair = messages.find((m) => m.id === msg.comparePair)
        if (!pair) {
          items.push({ type: 'assistant', msg })
          continue
        }
        seen.add(msg.id)
        seen.add(pair.id)
        const grounded = msg.answerMode === 'grounded' ? msg : pair
        const base = msg.answerMode === 'base' ? msg : pair
        items.push({ type: 'compare', grounded, base, userQuery: msg.query })
      } else {
        items.push({ type: 'assistant', msg })
      }
    }
    return items
  }, [messages])

  return (
    <div
      className={cn(
        'flex h-dvh flex-col bg-canvas text-ink',
        'dark:bg-[var(--color-canvas-dark)] dark:text-[var(--color-ink-dark)]',
      )}
    >
      <Header
        dark={dark}
        onToggleDark={() => setDark((d) => !d)}
        mode={mode}
        onModeChange={setMode}
        inspectorOpen={inspectorOpen}
        onToggleInspector={() => {
          setInspectorOpen((o) => !o)
          setMobileSheetOpen((o) => !o)
        }}
        onExport={exportScores}
        hasScores={Object.keys(scores).length > 0}
        streaming={streaming}
      />

      <div className="relative flex min-h-0 flex-1">
        {/* Conversation */}
        <main
          className={cn(
            'flex min-w-0 flex-col',
            inspectorOpen ? 'w-full lg:w-[65%]' : 'w-full',
          )}
        >
          <div
            ref={listRef}
            className="flex-1 overflow-y-auto px-4 py-8 sm:px-8 lg:px-10"
            aria-live="polite"
            aria-relevant="additions"
          >
            {messages.length === 0 ? (
              <EmptyState onPick={(q) => send(q)} />
            ) : (
              <div className="mx-auto flex max-w-3xl flex-col gap-10 lg:max-w-none">
                {renderItems.map((item) => {
                  if (item.type === 'user') {
                    return <UserMessage key={item.msg.id} content={item.msg.content} />
                  }
                  if (item.type === 'compare') {
                    return (
                      <CompareBlock
                        key={item.grounded.id}
                        grounded={item.grounded}
                        base={item.base}
                        scores={scores}
                        onScore={updateScore}
                        onCiteHover={setHighlightedChunkId}
                        onCiteClick={scrollToChunk}
                        highlightedChunkId={highlightedChunkId}
                      />
                    )
                  }
                  return (
                    <AssistantMessage
                      key={item.msg.id}
                      msg={item.msg}
                      score={scores[item.msg.id]}
                      onScore={updateScore}
                      onCiteHover={setHighlightedChunkId}
                      onCiteClick={scrollToChunk}
                      highlightedChunkId={highlightedChunkId}
                    />
                  )
                })}
              </div>
            )}
          </div>

          <Composer
            value={input}
            onChange={setInput}
            onSend={() => send()}
            disabled={streaming}
            mode={mode}
          />
        </main>

        {/* Desktop inspector */}
        {inspectorOpen && (
          <aside
            className={cn(
              'hidden w-[35%] min-w-[280px] flex-col border-l border-line lg:flex',
              'dark:border-[var(--color-line-dark)]',
              'bg-canvas dark:bg-[var(--color-canvas-dark)]',
            )}
          >
            <Inspector
              chunks={filteredChunks}
              allCount={activeChunks.length}
              typeFilter={typeFilter}
              countryFilter={countryFilter}
              onToggleType={(t) => toggleFilter(typeFilter, t, setTypeFilter)}
              onToggleCountry={(c) => toggleFilter(countryFilter, c, setCountryFilter)}
              highlightedChunkId={highlightedChunkId}
              chunkRefs={chunkRefs}
              onHoverChunk={setHighlightedChunkId}
              mode={mode}
            />
          </aside>
        )}

        {/* Mobile bottom sheet */}
        {mobileSheetOpen && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-label="Retrieved context">
            <button
              type="button"
              className="absolute inset-0 bg-ink/30 dark:bg-black/50"
              aria-label="Close context panel"
              onClick={() => setMobileSheetOpen(false)}
            />
            <div
              className={cn(
                'absolute inset-x-0 bottom-0 flex max-h-[75dvh] flex-col rounded-t-[6px]',
                'border-t border-line bg-canvas',
                'dark:border-[var(--color-line-dark)] dark:bg-[var(--color-canvas-elevated-dark)]',
              )}
            >
              <div className="flex items-center justify-between border-b border-line px-4 py-3 dark:border-[var(--color-line-dark)]">
                <span className="font-mono text-xs tracking-wide text-ink-muted dark:text-[var(--color-ink-muted-dark)]">
                  Retrieved context
                </span>
                <button
                  type="button"
                  onClick={() => setMobileSheetOpen(false)}
                  className="rounded-[4px] p-1.5 text-ink-muted hover:bg-accent-soft dark:text-[var(--color-ink-muted-dark)] dark:hover:bg-[var(--color-accent-soft-dark)]"
                  aria-label="Close"
                >
                  <X size={16} />
                </button>
              </div>
              <Inspector
                chunks={filteredChunks}
                allCount={activeChunks.length}
                typeFilter={typeFilter}
                countryFilter={countryFilter}
                onToggleType={(t) => toggleFilter(typeFilter, t, setTypeFilter)}
                onToggleCountry={(c) => toggleFilter(countryFilter, c, setCountryFilter)}
                highlightedChunkId={highlightedChunkId}
                chunkRefs={chunkRefs}
                onHoverChunk={setHighlightedChunkId}
                mode={mode}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Subcomponents (same file)
// =============================================================================
function Header({
  dark,
  onToggleDark,
  mode,
  onModeChange,
  inspectorOpen,
  onToggleInspector,
  onExport,
  hasScores,
  streaming,
}) {
  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex flex-wrap items-center gap-3 border-b border-line',
        'bg-canvas px-4 py-3 sm:px-6',
        'dark:border-[var(--color-line-dark)] dark:bg-[var(--color-canvas-dark)]',
      )}
    >
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[15px] font-medium tracking-tight sm:text-base">
          Culturally-grounded RAG
        </h1>
        <p className="mt-0.5 font-mono text-[11px] text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
          {MOCK.corpus.documentCount} documents · {MOCK.corpus.regions.join(', ')}
        </p>
      </div>

      <ModeToggle mode={mode} onChange={onModeChange} disabled={streaming} />

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onExport}
          disabled={!hasScores}
          title="Export evaluation scores as JSON"
          className={cn(
            'rounded-[4px] p-2 text-ink-muted transition-colors',
            'hover:bg-accent-soft hover:text-accent',
            'disabled:cursor-not-allowed disabled:opacity-40',
            'dark:text-[var(--color-ink-muted-dark)] dark:hover:bg-[var(--color-accent-soft-dark)] dark:hover:text-[var(--color-accent-dark)]',
          )}
          aria-label="Export scores"
        >
          <Download size={16} />
        </button>
        <button
          type="button"
          onClick={onToggleDark}
          className="rounded-[4px] p-2 text-ink-muted hover:bg-accent-soft hover:text-accent dark:text-[var(--color-ink-muted-dark)] dark:hover:bg-[var(--color-accent-soft-dark)] dark:hover:text-[var(--color-accent-dark)]"
          aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {dark ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button
          type="button"
          onClick={onToggleInspector}
          className="rounded-[4px] p-2 text-ink-muted hover:bg-accent-soft hover:text-accent dark:text-[var(--color-ink-muted-dark)] dark:hover:bg-[var(--color-accent-soft-dark)] dark:hover:text-[var(--color-accent-dark)]"
          aria-label={inspectorOpen ? 'Hide retrieved context' : 'Show retrieved context'}
          aria-pressed={inspectorOpen}
        >
          {inspectorOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
        </button>
      </div>
    </header>
  )
}

function ModeToggle({ mode, onChange, disabled }) {
  return (
    <div
      role="radiogroup"
      aria-label="Answer mode"
      className={cn(
        'flex rounded-[6px] border border-line p-0.5',
        'dark:border-[var(--color-line-dark)]',
      )}
    >
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          role="radio"
          aria-checked={mode === m.id}
          disabled={disabled}
          onClick={() => onChange(m.id)}
          className={cn(
            'rounded-[4px] px-2.5 py-1.5 font-mono text-[11px] tracking-wide transition-colors sm:px-3',
            mode === m.id
              ? 'bg-accent text-white dark:bg-[var(--color-accent-dark)] dark:text-[var(--color-canvas-dark)]'
              : 'text-ink-muted hover:text-ink dark:text-[var(--color-ink-muted-dark)] dark:hover:text-[var(--color-ink-dark)]',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          {m.label}
        </button>
      ))}
    </div>
  )
}

function EmptyState({ onPick }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-start pt-6 sm:pt-16">
      <p className="text-[17px] leading-[1.65] text-ink-muted dark:text-[var(--color-ink-muted-dark)]">
        Ask about tech ecosystems and developer communities in Nigeria and Ghana.
        Answers in Grounded mode are retrieved from a curated corpus of reports,
        community blogs, forum threads, and transcribed talks.
      </p>
      <p className="mt-8 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
        Example questions
      </p>
      <ul className="mt-3 grid w-full gap-2 sm:grid-cols-2">
        {MOCK.exampleQuestions.map((q) => (
          <li key={q.id}>
            <button
              type="button"
              onClick={() => onPick(q.text)}
              className={cn(
                'group flex h-full w-full flex-col items-start rounded-[6px] border border-line',
                'bg-canvas-elevated px-4 py-3.5 text-left transition-colors',
                'hover:border-accent hover:bg-accent-soft',
                'dark:border-[var(--color-line-dark)] dark:bg-[var(--color-canvas-elevated-dark)]',
                'dark:hover:border-[var(--color-accent-dark)] dark:hover:bg-[var(--color-accent-soft-dark)]',
              )}
            >
              <span className="font-mono text-[10px] uppercase tracking-wider text-accent dark:text-[var(--color-accent-dark)]">
                {q.label}
              </span>
              <span className="mt-1.5 text-[14px] leading-[1.55] text-ink dark:text-[var(--color-ink-dark)]">
                {q.text}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function UserMessage({ content }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[min(36rem,90%)] pl-8 text-right text-[15px] leading-[1.65] text-ink-muted dark:text-[var(--color-ink-muted-dark)]">
        {content}
      </p>
    </div>
  )
}

function AssistantMessage({
  msg,
  score,
  onScore,
  onCiteHover,
  onCiteClick,
  highlightedChunkId,
  compactLabel,
}) {
  return (
    <article className="w-full">
      {compactLabel && (
        <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
          {compactLabel}
        </p>
      )}
      <div className="text-[16px] leading-[1.7] text-ink dark:text-[var(--color-ink-dark)]">
        <AnswerBody
          content={msg.content}
          citations={msg.citations}
          streaming={msg.streaming}
          onCiteHover={onCiteHover}
          onCiteClick={onCiteClick}
          highlightedChunkId={highlightedChunkId}
        />
        {msg.streaming && <span className="streaming-caret" aria-hidden="true" />}
      </div>

      {!msg.streaming && msg.answerMode !== 'base' && (
        <AnswerMeta meta={msg.meta} />
      )}
      {!msg.streaming && msg.answerMode === 'base' && msg.meta?.latencyMs > 0 && (
        <p className="mt-3 font-mono text-[11px] text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
          {msg.meta.latencyMs} ms
        </p>
      )}

      {!msg.streaming && (
        <EvalRubric
          messageId={msg.id}
          value={score}
          onChange={(patch) => onScore(msg.id, patch)}
        />
      )}
    </article>
  )
}

function CompareBlock({
  grounded,
  base,
  scores,
  onScore,
  onCiteHover,
  onCiteClick,
  highlightedChunkId,
}) {
  return (
    <div className="w-full">
      <div className="grid gap-0 md:grid-cols-2">
        <div className="md:pr-6">
          <AssistantMessage
            msg={grounded}
            score={scores[grounded.id]}
            onScore={onScore}
            onCiteHover={onCiteHover}
            onCiteClick={onCiteClick}
            highlightedChunkId={highlightedChunkId}
            compactLabel="Grounded (RAG)"
          />
        </div>
        <div
          className={cn(
            'border-t border-line pt-8 md:border-l md:border-t-0 md:pl-6 md:pt-0',
            'dark:border-[var(--color-line-dark)]',
          )}
        >
          <AssistantMessage
            msg={base}
            score={scores[base.id]}
            onScore={onScore}
            onCiteHover={onCiteHover}
            onCiteClick={onCiteClick}
            highlightedChunkId={highlightedChunkId}
            compactLabel="Base model"
          />
        </div>
      </div>
    </div>
  )
}

function AnswerBody({
  content,
  citations = [],
  streaming,
  onCiteHover,
  onCiteClick,
  highlightedChunkId,
}) {
  const nodes = useMemo(() => parseCitations(content), [content])

  return (
    <p className="whitespace-pre-wrap">
      {nodes.map((node, i) => {
        if (node.type === 'text') return <span key={i}>{node.value}</span>
        const chunk = citations[node.index - 1]
        const id = chunk?.id
        return (
          <CitationChip
            key={i}
            n={node.index}
            active={id && highlightedChunkId === id}
            disabled={!id}
            onMouseEnter={() => id && onCiteHover?.(id)}
            onMouseLeave={() => onCiteHover?.(null)}
            onClick={() => id && onCiteClick?.(id)}
            onKeyDown={(e) => {
              if ((e.key === 'Enter' || e.key === ' ') && id) {
                e.preventDefault()
                onCiteClick?.(id)
              }
            }}
          />
        )
      })}
      {streaming ? null : null}
    </p>
  )
}

function parseCitations(text) {
  const nodes = []
  const re = /\[(\d+)\]/g
  let last = 0
  let m
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push({ type: 'text', value: text.slice(last, m.index) })
    nodes.push({ type: 'cite', index: Number(m[1]) })
    last = m.index + m[0].length
  }
  if (last < text.length) nodes.push({ type: 'text', value: text.slice(last) })
  return nodes
}

function CitationChip({ n, active, disabled, ...props }) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={`Citation ${n}`}
      className={cn(
        'relative -top-0.5 mx-0.5 inline-flex h-[1.1rem] min-w-[1.1rem] items-center justify-center',
        'rounded-[3px] border px-1 font-mono text-[10px] leading-none transition-colors',
        active
          ? 'border-accent bg-accent text-white dark:border-[var(--color-accent-dark)] dark:bg-[var(--color-accent-dark)] dark:text-[var(--color-canvas-dark)]'
          : 'border-line bg-accent-soft text-accent dark:border-[var(--color-line-dark)] dark:bg-[var(--color-accent-soft-dark)] dark:text-[var(--color-accent-dark)]',
        'hover:border-accent disabled:cursor-default disabled:opacity-50',
      )}
      {...props}
    >
      {n}
    </button>
  )
}

function AnswerMeta({ meta }) {
  if (!meta) return null
  return (
    <div
      className={cn(
        'mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2',
        'font-mono text-[11px] text-ink-faint',
        'dark:border-[var(--color-line-dark)] dark:text-[var(--color-ink-faint-dark)]',
      )}
    >
      <span>{meta.retrievalCount} retrieved</span>
      <span aria-hidden="true">·</span>
      <span>{meta.latencyMs} ms</span>
      {meta.noContext && (
        <>
          <span aria-hidden="true">·</span>
          <span
            className="text-warn dark:text-[var(--color-warn-dark)]"
            role="status"
          >
            no relevant context found
          </span>
        </>
      )}
    </div>
  )
}

function EvalRubric({ messageId, value = {}, onChange }) {
  return (
    <div
      className={cn(
        'mt-4 rounded-[6px] border border-line px-3 py-3',
        'dark:border-[var(--color-line-dark)]',
      )}
    >
      <p className="mb-2.5 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
        Researcher rubric · {messageId.slice(-6)}
      </p>
      <div className="flex flex-col gap-2.5">
        {RUBRIC_DIMS.map((dim) => (
          <div key={dim.id} className="flex flex-wrap items-center gap-2 sm:gap-3">
            <span className="w-36 shrink-0 text-[13px] text-ink-muted dark:text-[var(--color-ink-muted-dark)]">
              {dim.label}
            </span>
            <div
              role="radiogroup"
              aria-label={dim.label}
              className="flex rounded-[4px] border border-line dark:border-[var(--color-line-dark)]"
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  role="radio"
                  aria-checked={value[dim.id] === n}
                  onClick={() => onChange({ [dim.id]: n })}
                  className={cn(
                    'min-w-[1.75rem] border-r border-line px-2 py-1 font-mono text-[11px] last:border-r-0',
                    'dark:border-[var(--color-line-dark)]',
                    value[dim.id] === n
                      ? 'bg-accent text-white dark:bg-[var(--color-accent-dark)] dark:text-[var(--color-canvas-dark)]'
                      : 'text-ink-muted hover:bg-accent-soft dark:text-[var(--color-ink-muted-dark)] dark:hover:bg-[var(--color-accent-soft-dark)]',
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <label className="mt-3 block">
        <span className="sr-only">Optional note</span>
        <textarea
          rows={2}
          placeholder="Optional note…"
          value={value.note || ''}
          onChange={(e) => onChange({ note: e.target.value })}
          className={cn(
            'mt-1 w-full resize-y rounded-[4px] border border-line bg-transparent px-2.5 py-2',
            'text-[13px] leading-relaxed text-ink placeholder:text-ink-faint',
            'dark:border-[var(--color-line-dark)] dark:text-[var(--color-ink-dark)] dark:placeholder:text-[var(--color-ink-faint-dark)]',
          )}
        />
      </label>
    </div>
  )
}

function Inspector({
  chunks,
  allCount,
  typeFilter,
  countryFilter,
  onToggleType,
  onToggleCountry,
  highlightedChunkId,
  chunkRefs,
  onHoverChunk,
  mode,
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-line px-4 py-3 dark:border-[var(--color-line-dark)]">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-muted dark:text-[var(--color-ink-muted-dark)]">
            Retrieved context
          </h2>
          <span className="font-mono text-[11px] text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
            {mode === 'base' ? 'n/a' : `${chunks.length}/${allCount}`}
          </span>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {SOURCE_TYPES.map((t) => (
            <FilterChip
              key={t}
              label={t}
              active={typeFilter.has(t)}
              onClick={() => onToggleType(t)}
            />
          ))}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {COUNTRIES.map((c) => (
            <FilterChip
              key={c}
              label={c}
              active={countryFilter.has(c)}
              onClick={() => onToggleCountry(c)}
            />
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {mode === 'base' ? (
          <p className="px-1 py-6 text-[13px] leading-relaxed text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
            Base model mode does not retrieve corpus chunks.
          </p>
        ) : chunks.length === 0 ? (
          <p className="px-1 py-6 text-[13px] leading-relaxed text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
            {allCount === 0
              ? 'Send a grounded or compare question to populate retrieved chunks.'
              : 'No chunks match the current filters.'}
          </p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {chunks.map((chunk, i) => (
              <ChunkCard
                key={chunk.id}
                rank={i + 1}
                chunk={chunk}
                highlighted={highlightedChunkId === chunk.id}
                refCallback={(el) => {
                  chunkRefs.current[chunk.id] = el
                }}
                onHover={onHoverChunk}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function FilterChip({ label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-[4px] border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors',
        active
          ? 'border-accent bg-accent text-white dark:border-[var(--color-accent-dark)] dark:bg-[var(--color-accent-dark)] dark:text-[var(--color-canvas-dark)]'
          : 'border-line text-ink-muted hover:border-accent dark:border-[var(--color-line-dark)] dark:text-[var(--color-ink-muted-dark)]',
      )}
    >
      {label}
    </button>
  )
}

function ChunkCard({ chunk, rank, highlighted, refCallback, onHover }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <li
      ref={refCallback}
      onMouseEnter={() => onHover?.(chunk.id)}
      onMouseLeave={() => onHover?.(null)}
      className={cn(
        'rounded-[6px] border px-3 py-2.5 transition-colors',
        highlighted
          ? 'border-accent bg-accent-soft dark:border-[var(--color-accent-dark)] dark:bg-[var(--color-accent-soft-dark)]'
          : 'border-line bg-canvas-elevated dark:border-[var(--color-line-dark)] dark:bg-[var(--color-canvas-elevated-dark)]',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium leading-snug">{chunk.title}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="rounded-[3px] border border-line px-1.5 py-px font-mono text-[9px] uppercase tracking-wider text-ink-muted dark:border-[var(--color-line-dark)] dark:text-[var(--color-ink-muted-dark)]">
              {chunk.sourceType}
            </span>
            <span className="font-mono text-[10px] text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
              {chunk.country}
            </span>
            <span className="font-mono text-[10px] text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
              #{rank}
            </span>
          </div>
        </div>
        <span className="shrink-0 font-mono text-[10px] text-ink-faint dark:text-[var(--color-ink-faint-dark)]">
          {chunk.score.toFixed(2)}
        </span>
      </div>

      <div className="mt-2 h-1 overflow-hidden rounded-[2px] bg-line dark:bg-[var(--color-line-dark)]">
        <div
          className="h-full bg-accent dark:bg-[var(--color-accent-dark)]"
          style={{ width: `${Math.round(chunk.score * 100)}%` }}
        />
      </div>

      <p
        className={cn(
          'mt-2 text-[12.5px] leading-[1.55] text-ink-muted dark:text-[var(--color-ink-muted-dark)]',
          !expanded && 'line-clamp-3',
        )}
      >
        {chunk.text}
      </p>
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="mt-1 inline-flex items-center gap-0.5 font-mono text-[10px] text-accent dark:text-[var(--color-accent-dark)]"
      >
        {expanded ? 'Collapse' : 'Expand'}
        <ChevronDown size={12} className={cn('transition-transform', expanded && 'rotate-180')} />
      </button>
    </li>
  )
}

function Composer({ value, onChange, onSend, disabled, mode }) {
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div
      className={cn(
        'border-t border-line bg-canvas px-4 py-3 sm:px-8 lg:px-10',
        'dark:border-[var(--color-line-dark)] dark:bg-[var(--color-canvas-dark)]',
      )}
    >
      <div className="mx-auto flex max-w-3xl items-end gap-2 lg:max-w-none">
        <label className="sr-only" htmlFor="chat-input">
          Message
        </label>
        <textarea
          id="chat-input"
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={
            mode === 'compare'
              ? 'Ask once — compare grounded vs base…'
              : mode === 'base'
                ? 'Ask the base model…'
                : 'Ask about Nigeria & Ghana tech communities…'
          }
          className={cn(
            'max-h-36 min-h-[44px] flex-1 resize-none rounded-[6px] border border-line',
            'bg-canvas-elevated px-3.5 py-2.5 text-[15px] leading-relaxed',
            'placeholder:text-ink-faint disabled:opacity-60',
            'dark:border-[var(--color-line-dark)] dark:bg-[var(--color-canvas-elevated-dark)]',
            'dark:placeholder:text-[var(--color-ink-faint-dark)]',
          )}
        />
        <button
          type="button"
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className={cn(
            'inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-[6px]',
            'bg-accent text-white transition-opacity',
            'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40',
            'dark:bg-[var(--color-accent-dark)] dark:text-[var(--color-canvas-dark)]',
          )}
          aria-label="Send message"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}
