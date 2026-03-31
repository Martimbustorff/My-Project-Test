/**
 * Ask Tab — Natural language research query interface.
 * Users type a query; all 5 trading agents scan a stock universe
 * and return the strongest consensus buy/sell opportunities.
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Animated,
  useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, recColor } from '@/constants/Colors';
import { apiPost } from '@/constants/Api';
import { showToast } from '@/components/Toast';

// ── Types ──────────────────────────────────────────────────────────────────────

interface ResearchResult {
  symbol: string;
  recommendation: string;
  direction: string;
  consensus_score: number;
  confidence: number;
  projected_upside: string;
  time_horizon: string;
  key_reasons: string[];
  technical_score: number;
  fundamental_score: number;
  momentum_score: number;
  sentiment_score: number;
  macro_score: number;
  price: number;
}

interface ResearchResponse {
  query: string;
  intent: string;
  total_scanned: number;
  total_matches: number;
  summary: string;
  results: ResearchResult[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const SUGGESTION_CHIPS = [
  { label: 'Best small caps 2yr', query: 'Best small cap growth stocks for a 2 year investment horizon' },
  { label: 'Tech momentum plays', query: 'Top tech stocks with strong momentum and bullish sentiment' },
  { label: 'Crypto opportunities', query: 'Best crypto assets to buy with strong consensus' },
  { label: 'Value undervalued', query: 'Most undervalued large cap value stocks right now' },
  { label: 'Short opportunities', query: 'Stocks with strong sell signals and downside momentum' },
];

const AGENT_INFO = [
  { label: 'Technical Agent',    emoji: '🔬', key: 'technical_score' },
  { label: 'Fundamental Agent',  emoji: '📊', key: 'fundamental_score' },
  { label: 'Momentum Agent',     emoji: '📈', key: 'momentum_score' },
  { label: 'Sentiment Agent',    emoji: '📰', key: 'sentiment_score' },
  { label: 'Macro Agent',        emoji: '🌍', key: 'macro_score' },
] as const;

// ── Sub-components ─────────────────────────────────────────────────────────────

function AgentProgressBar({ label, emoji }: { label: string; emoji: string }) {
  const progress = useRef(new Animated.Value(0.3)).current;

  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(progress, { toValue: 0.9, duration: 1200 + Math.random() * 600, useNativeDriver: false }),
        Animated.timing(progress, { toValue: 0.3, duration: 1000 + Math.random() * 400, useNativeDriver: false }),
      ])
    );
    anim.start();
    return () => anim.stop();
  }, []);

  const barWidth = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  return (
    <View style={loadingStyles.row}>
      <Text style={loadingStyles.emoji}>{emoji}</Text>
      <Text style={loadingStyles.agentLabel}>{label}</Text>
      <View style={loadingStyles.track}>
        <Animated.View style={[loadingStyles.fill, { width: barWidth }]} />
      </View>
      <Text style={loadingStyles.status}>analyzing...</Text>
    </View>
  );
}

function AgentDot({ score }: { score: number }) {
  let color = Colors.yellow;
  if (score >= 0.6) color = Colors.green;
  else if (score <= 0.4) color = Colors.red;
  return <View style={[resultStyles.agentDot, { backgroundColor: color }]} />;
}

function DirectionBadge({ direction }: { direction: string }) {
  const isLong = direction?.toUpperCase() === 'LONG';
  const color = isLong ? Colors.green : Colors.red;
  const bg = isLong ? Colors.greenDim : Colors.redDim;
  return (
    <View style={[resultStyles.dirBadge, { backgroundColor: bg, borderColor: color }]}>
      <Text style={[resultStyles.dirText, { color }]}>
        {isLong ? '▲ LONG' : '▼ SHORT'}
      </Text>
    </View>
  );
}

function RecoBadge({ label }: { label: string }) {
  const color = recColor(label);
  return (
    <View style={[resultStyles.recoBadge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[resultStyles.recoText, { color }]}>{label?.toUpperCase?.() ?? '—'}</Text>
    </View>
  );
}

function UpsideBadge({ upside }: { upside: string }) {
  if (!upside) return null;
  return (
    <View style={resultStyles.upsideBadge}>
      <Text style={resultStyles.upsideText}>{upside}</Text>
    </View>
  );
}

function HorizonChip({ horizon }: { horizon: string }) {
  if (!horizon) return null;
  return (
    <View style={resultStyles.horizonChip}>
      <Text style={resultStyles.horizonText}>{horizon}</Text>
    </View>
  );
}

function ResultCard({
  result,
  rank,
  onAnalyze,
}: {
  result: ResearchResult;
  rank: number;
  onAnalyze: (symbol: string) => void;
}) {
  const scoreBarWidth = `${Math.round((result.consensus_score ?? 0) * 100)}%`;

  return (
    <View style={resultStyles.card}>
      {/* Header row */}
      <View style={resultStyles.headerRow}>
        <View style={resultStyles.rankCircle}>
          <Text style={resultStyles.rankText}>{rank}</Text>
        </View>
        <Text style={resultStyles.symbol}>{result.symbol ?? '—'}</Text>
        <DirectionBadge direction={result.direction ?? ''} />
        {result.price != null && (
          <Text style={resultStyles.price}>${result.price?.toFixed(2)}</Text>
        )}
      </View>

      {/* Badges row */}
      <View style={resultStyles.badgesRow}>
        <RecoBadge label={result.recommendation ?? ''} />
        {result.consensus_score != null && (
          <View style={resultStyles.consensusBadge}>
            <Text style={resultStyles.consensusText}>
              {Math.round(result.consensus_score * 100)}% consensus
            </Text>
          </View>
        )}
        <UpsideBadge upside={result.projected_upside ?? ''} />
        <HorizonChip horizon={result.time_horizon ?? ''} />
      </View>

      {/* Score bar */}
      <View style={resultStyles.scoreTrack}>
        <View style={[resultStyles.scoreFill, { width: scoreBarWidth as any }]} />
      </View>

      {/* Agent breakdown */}
      <View style={resultStyles.agentRow}>
        {AGENT_INFO.map((a) => (
          <View key={a.key} style={resultStyles.agentItem}>
            <Text style={resultStyles.agentEmoji}>{a.emoji}</Text>
            <AgentDot score={(result as any)[a.key] ?? 0.5} />
          </View>
        ))}
      </View>

      {/* Key reasons */}
      {result.key_reasons?.slice(0, 2).map((reason, i) => (
        <View key={i} style={resultStyles.reasonRow}>
          <Text style={resultStyles.bullet}>•</Text>
          <Text style={resultStyles.reasonText} numberOfLines={2}>{reason}</Text>
        </View>
      ))}

      {/* Analyze button */}
      <TouchableOpacity
        style={resultStyles.analyzeBtn}
        onPress={() => onAnalyze(result.symbol)}
        activeOpacity={0.75}
      >
        <Text style={resultStyles.analyzeBtnText}>Analyze {result.symbol} →</Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Main Screen ────────────────────────────────────────────────────────────────

export default function AskScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= 900;
  const router = useRouter();

  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState('');

  const handleSubmit = useCallback(async (q?: string) => {
    const finalQuery = (q ?? query).trim();
    if (!finalQuery) return;
    setLoading(true);
    setError('');
    setResponse(null);
    try {
      const res = await apiPost<ResearchResponse>('/api/research/query', { query: finalQuery });
      setResponse(res);
    } catch (err: any) {
      setError(err?.message ?? 'An unknown error occurred.');
    } finally {
      setLoading(false);
    }
  }, [query]);

  const handleChip = useCallback((chipQuery: string) => {
    setQuery(chipQuery);
    handleSubmit(chipQuery);
  }, [handleSubmit]);

  const handleAnalyze = useCallback((symbol: string) => {
    showToast({ message: `Go to Analysis tab and search ${symbol}`, type: 'info' });
    router.push(`/backtest?symbol=${symbol}` as any);
  }, [router]);

  // ── Render helpers ─────────────────────────────────────────────────────────

  function renderInputArea() {
    return (
      <View style={[inputStyles.container, isDesktop && inputStyles.containerDesktop]}>
        <TextInput
          style={inputStyles.textInput}
          placeholder={'Ask anything... e.g. \'Best small caps for 2 year horizon\' or \'Tech stocks with strong momentum\''}
          placeholderTextColor={Colors.textMuted}
          value={query}
          onChangeText={setQuery}
          multiline
          numberOfLines={3}
          onSubmitEditing={() => handleSubmit()}
          blurOnSubmit
        />
        <TouchableOpacity
          style={[inputStyles.submitBtn, loading && inputStyles.submitBtnDisabled]}
          onPress={() => handleSubmit()}
          disabled={loading || !query.trim()}
          activeOpacity={0.8}
        >
          <Text style={inputStyles.submitBtnText}>⚡ Research</Text>
        </TouchableOpacity>
      </View>
    );
  }

  function renderChips() {
    return (
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={chipStyles.row}
      >
        {SUGGESTION_CHIPS.map((chip) => (
          <TouchableOpacity
            key={chip.label}
            style={chipStyles.chip}
            onPress={() => handleChip(chip.query)}
            activeOpacity={0.75}
          >
            <Text style={chipStyles.chipText}>{chip.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    );
  }

  function renderLoading() {
    return (
      <View style={loadingStyles.container}>
        <Text style={loadingStyles.title}>Scanning market universe...</Text>
        {AGENT_INFO.map((a) => (
          <AgentProgressBar key={a.key} label={a.label} emoji={a.emoji} />
        ))}
      </View>
    );
  }

  function renderEmpty() {
    return (
      <View style={emptyStyles.container}>
        <Text style={emptyStyles.icon}>🧠</Text>
        <Text style={emptyStyles.title}>Research anything</Text>
        <Text style={emptyStyles.subtitle}>
          Ask about specific sectors, time horizons, strategies. All 5 agents will analyze a curated universe of stocks and return the strongest consensus signals.
        </Text>
        {renderChips()}
      </View>
    );
  }

  function renderError() {
    return (
      <View style={errorStyles.card}>
        <Text style={errorStyles.icon}>⚠</Text>
        <Text style={errorStyles.title}>Research failed</Text>
        <Text style={errorStyles.message}>{error}</Text>
        <TouchableOpacity
          style={errorStyles.retryBtn}
          onPress={() => handleSubmit()}
          activeOpacity={0.8}
        >
          <Text style={errorStyles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  function renderResults() {
    if (!response) return null;
    const { summary, results, total_scanned, total_matches, intent } = response;

    return (
      <View style={isDesktop ? { maxWidth: 1200, alignSelf: 'center', width: '100%' } : undefined}>
        {/* Meta info */}
        <View style={summaryStyles.metaRow}>
          {intent ? <Text style={summaryStyles.intentBadge}>{intent}</Text> : null}
          {total_scanned != null && (
            <Text style={summaryStyles.metaText}>
              {total_matches} matches from {total_scanned} scanned
            </Text>
          )}
        </View>

        {/* Summary card */}
        {summary ? (
          <View style={summaryStyles.card}>
            <Text style={summaryStyles.summaryText}>{summary}</Text>
          </View>
        ) : null}

        {/* Result cards grid */}
        {results?.length > 0 ? (
          <View style={isDesktop ? resultStyles.grid : undefined}>
            {results.map((result, idx) => (
              <View key={result.symbol ?? idx} style={isDesktop ? resultStyles.gridItem : undefined}>
                <ResultCard result={result} rank={idx + 1} onAnalyze={handleAnalyze} />
              </View>
            ))}
          </View>
        ) : (
          <View style={emptyResultStyles.container}>
            <Text style={emptyResultStyles.text}>No results matched your query. Try rephrasing or broadening your search.</Text>
          </View>
        )}
      </View>
    );
  }

  // ── Main render ────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Ask 🧠</Text>
          <Text style={styles.headerSubtitle}>Natural language market research</Text>
        </View>

        {/* Input area */}
        {renderInputArea()}

        {/* Chips shown above loading/results when a response exists */}
        {!loading && !response && !error && renderChips()}

        {/* States */}
        {loading && renderLoading()}
        {!loading && error && renderError()}
        {!loading && !error && response && renderResults()}
        {!loading && !error && !response && <View style={{ height: 32 }} />}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scroll: {
    flex: 1,
  },
  content: {
    paddingBottom: 60,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 12,
  },
  headerTitle: {
    color: Colors.text,
    fontSize: 26,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  headerSubtitle: {
    color: Colors.textSecondary,
    fontSize: 13,
    marginTop: 2,
  },
});

const inputStyles = StyleSheet.create({
  container: {
    marginHorizontal: 16,
    marginBottom: 12,
  },
  containerDesktop: {
    maxWidth: 700,
    alignSelf: 'center',
    width: '100%',
  },
  textInput: {
    backgroundColor: Colors.surfaceAlt,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 12,
    color: Colors.text,
    fontSize: 15,
    lineHeight: 22,
    padding: 14,
    minHeight: 80,
    textAlignVertical: 'top',
    marginBottom: 10,
  },
  submitBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 10,
    paddingVertical: 13,
    alignItems: 'center',
  },
  submitBtnDisabled: {
    opacity: 0.4,
  },
  submitBtnText: {
    color: Colors.background,
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
});

const chipStyles = StyleSheet.create({
  row: {
    paddingHorizontal: 16,
    paddingBottom: 16,
    gap: 8,
    flexDirection: 'row',
  },
  chip: {
    backgroundColor: Colors.surfaceAlt,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  chipText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '500',
  },
});

const loadingStyles = StyleSheet.create({
  container: {
    marginHorizontal: 16,
    marginTop: 8,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 14,
    padding: 20,
  },
  title: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 0.5,
    marginBottom: 16,
    textTransform: 'uppercase',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
    gap: 8,
  },
  emoji: {
    fontSize: 16,
    width: 22,
    textAlign: 'center',
  },
  agentLabel: {
    color: Colors.text,
    fontSize: 13,
    fontWeight: '500',
    width: 150,
  },
  track: {
    flex: 1,
    height: 6,
    backgroundColor: Colors.surfaceAlt,
    borderRadius: 3,
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    backgroundColor: Colors.primary,
    borderRadius: 3,
  },
  status: {
    color: Colors.textMuted,
    fontSize: 11,
    width: 72,
    textAlign: 'right',
  },
});

const summaryStyles = StyleSheet.create({
  card: {
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: Colors.surface,
    borderLeftWidth: 3,
    borderLeftColor: Colors.green,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 12,
    padding: 16,
  },
  summaryText: {
    color: Colors.text,
    fontSize: 14,
    lineHeight: 22,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    marginBottom: 10,
    gap: 10,
    flexWrap: 'wrap',
  },
  intentBadge: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: '700',
    backgroundColor: Colors.primaryGlow,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 10,
    overflow: 'hidden',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  metaText: {
    color: Colors.textMuted,
    fontSize: 12,
  },
});

const resultStyles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
    gap: 12,
  },
  gridItem: {
    width: 'calc(50% - 6px)' as any,
    minWidth: 300,
  },
  card: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 14,
    padding: 16,
    marginHorizontal: 16,
    marginBottom: 12,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    gap: 10,
  },
  rankCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.surfaceAlt,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankText: {
    color: Colors.textSecondary,
    fontSize: 12,
    fontWeight: '700',
  },
  symbol: {
    color: Colors.text,
    fontSize: 20,
    fontWeight: '800',
    flex: 1,
    letterSpacing: 0.5,
  },
  price: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
  dirBadge: {
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  dirText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  badgesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 12,
  },
  recoBadge: {
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  recoText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  consensusBadge: {
    backgroundColor: Colors.surfaceAlt,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  consensusText: {
    color: Colors.textSecondary,
    fontSize: 11,
    fontWeight: '600',
  },
  upsideBadge: {
    backgroundColor: Colors.greenDim,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  upsideText: {
    color: Colors.green,
    fontSize: 11,
    fontWeight: '700',
  },
  horizonChip: {
    backgroundColor: Colors.surfaceAlt,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  horizonText: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: '500',
  },
  scoreTrack: {
    height: 4,
    backgroundColor: Colors.surfaceAlt,
    borderRadius: 2,
    marginBottom: 12,
    overflow: 'hidden',
  },
  scoreFill: {
    height: '100%',
    backgroundColor: Colors.primary,
    borderRadius: 2,
  },
  agentRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 12,
  },
  agentItem: {
    alignItems: 'center',
    gap: 4,
  },
  agentEmoji: {
    fontSize: 14,
  },
  agentDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  reasonRow: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 4,
  },
  bullet: {
    color: Colors.textMuted,
    fontSize: 13,
    lineHeight: 19,
  },
  reasonText: {
    color: Colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
    flex: 1,
  },
  analyzeBtn: {
    marginTop: 12,
    backgroundColor: Colors.surfaceAlt,
    borderWidth: 1,
    borderColor: Colors.borderLight,
    borderRadius: 8,
    paddingVertical: 9,
    alignItems: 'center',
  },
  analyzeBtnText: {
    color: Colors.primary,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
});

const emptyStyles = StyleSheet.create({
  container: {
    alignItems: 'center',
    paddingTop: 60,
    paddingHorizontal: 32,
  },
  icon: {
    fontSize: 56,
    marginBottom: 16,
  },
  title: {
    color: Colors.text,
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 10,
    textAlign: 'center',
  },
  subtitle: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 22,
    textAlign: 'center',
    marginBottom: 28,
  },
});

const emptyResultStyles = StyleSheet.create({
  container: {
    alignItems: 'center',
    paddingVertical: 40,
    paddingHorizontal: 32,
  },
  text: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 22,
    textAlign: 'center',
  },
});

const errorStyles = StyleSheet.create({
  card: {
    marginHorizontal: 16,
    marginTop: 8,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.red + '55',
    borderLeftWidth: 3,
    borderLeftColor: Colors.red,
    borderRadius: 14,
    padding: 20,
    alignItems: 'center',
  },
  icon: {
    color: Colors.red,
    fontSize: 28,
    marginBottom: 8,
  },
  title: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 6,
  },
  message: {
    color: Colors.textSecondary,
    fontSize: 13,
    lineHeight: 20,
    textAlign: 'center',
    marginBottom: 16,
  },
  retryBtn: {
    backgroundColor: Colors.surfaceAlt,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 8,
    paddingHorizontal: 24,
    paddingVertical: 10,
  },
  retryText: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
});
