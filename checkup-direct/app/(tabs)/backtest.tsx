import React, { useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  TextInput, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { apiGet } from '@/constants/Api';

interface AgentVote {
  agent_name: string;
  score: number;
  confidence: number;
  signal: string;
  reasons: string[];
  weight: number;
}

interface AnalysisResult {
  symbol: string;
  timestamp: string;
  price: number;
  change_pct: number;
  votes: AgentVote[];
  consensus_score: number;
  recommendation: string;
  direction: string;
  confidence: number;
  agreement_pct: number;
  bull_agents: string[];
  bear_agents: string[];
  key_reasons: string[];
  key_risks: string[];
}

const QUICK_SYMBOLS = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'BTC-USD'];

const AGENT_ICONS: Record<string, string> = {
  Technical:   '🔬',
  Fundamental: '📊',
  Momentum:    '📈',
  Sentiment:   '📰',
};

function signalBadgeColor(rec: string): string {
  const u = rec.toUpperCase();
  if (u === 'STRONG BUY') return '#00D4AA';
  if (u === 'BUY')         return '#00A86B';
  if (u === 'HOLD')        return '#FFD700';
  if (u === 'SELL')        return '#FF8C00';
  if (u === 'STRONG SELL') return '#FF4757';
  return Colors.textMuted;
}

function RecoBadge({ label }: { label: string }) {
  const color = signalBadgeColor(label);
  return (
    <View style={[styles.badge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label.toUpperCase()}</Text>
    </View>
  );
}

function ScoreBar({ score }: { score: number }) {
  const abs = Math.abs(score);
  const color = score > 0 ? Colors.green : score < 0 ? Colors.red : Colors.textMuted;
  return (
    <View style={styles.scoreBarBg}>
      <View style={[styles.scoreBarFill, { width: `${Math.min(abs * 100, 100)}%`, backgroundColor: color }]} />
    </View>
  );
}

function AgentCard({ vote }: { vote: AgentVote }) {
  const icon = AGENT_ICONS[vote.agent_name] ?? '';
  const agentLabel = `${icon} ${vote.agent_name} Analysis`;
  return (
    <View style={styles.agentCard}>
      <Text style={styles.agentCardTitle}>{agentLabel}</Text>
      <View style={styles.agentScoreRow}>
        <View style={{ flex: 1, marginRight: 12 }}>
          <ScoreBar score={vote.score} />
        </View>
        <Text style={[styles.agentScoreValue, {
          color: vote.score > 0 ? Colors.green : vote.score < 0 ? Colors.red : Colors.textMuted,
        }]}>
          {vote.score >= 0 ? '+' : ''}{vote.score.toFixed(2)}
        </Text>
        <RecoBadge label={vote.signal} />
      </View>
      {vote.reasons && vote.reasons.length > 0 && (
        <View style={styles.reasonsList}>
          {vote.reasons.map((r, i) => (
            <Text key={i} style={styles.bulletText}>• {r}</Text>
          ))}
        </View>
      )}
    </View>
  );
}

export default function AnalysisScreen() {
  const [symbol, setSymbol]       = useState('');
  const [loading, setLoading]     = useState(false);
  const [result, setResult]       = useState<AnalysisResult | null>(null);
  const [error, setError]         = useState<string | null>(null);

  const analyze = useCallback(async (sym: string) => {
    const s = sym.trim().toUpperCase();
    if (!s) return;
    setSymbol(s);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await apiGet<AnalysisResult>(`/api/analysis/${s}`);
      setResult(data);
    } catch (e: any) {
      setError(e.message === 'UNAUTHORIZED' ? 'Session expired' : e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleAnalyze = () => analyze(symbol);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <Text style={styles.headerTitle}>Analysis</Text>

        {/* Search section */}
        <View style={styles.searchCard}>
          <TextInput
            style={styles.searchInput}
            value={symbol}
            onChangeText={setSymbol}
            autoCapitalize="characters"
            placeholder="Enter symbol (e.g. AAPL, BTC-USD)"
            placeholderTextColor={Colors.textMuted}
            returnKeyType="search"
            onSubmitEditing={handleAnalyze}
          />
          <TouchableOpacity
            style={[styles.analyzeBtn, loading && { opacity: 0.7 }]}
            onPress={handleAnalyze}
            disabled={loading}
          >
            <Text style={styles.analyzeBtnText}>Analyze</Text>
          </TouchableOpacity>

          {/* Quick symbol chips */}
          <View style={styles.chipsRow}>
            {QUICK_SYMBOLS.map(s => (
              <TouchableOpacity
                key={s}
                style={[styles.chip, symbol === s && styles.chipActive]}
                onPress={() => analyze(s)}
              >
                <Text style={[styles.chipText, symbol === s && styles.chipTextActive]}>{s}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Loading state */}
        {loading && (
          <View style={styles.center}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.loadingText}>Analyzing {symbol}...</Text>
          </View>
        )}

        {/* Error state */}
        {error && !loading && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>Could not load analysis: {error}</Text>
          </View>
        )}

        {/* Empty state */}
        {!loading && !error && !result && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>
              Enter a stock symbol above to get a full multi-agent analysis
            </Text>
            <View style={styles.chipsRow}>
              {QUICK_SYMBOLS.map(s => (
                <TouchableOpacity
                  key={s}
                  style={styles.chip}
                  onPress={() => analyze(s)}
                >
                  <Text style={styles.chipText}>{s}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

        {/* Results */}
        {result && !loading && (
          <>
            {/* Summary card */}
            <View style={styles.summaryCard}>
              <View style={styles.summaryTop}>
                <View>
                  <Text style={styles.summarySymbol}>{result.symbol}</Text>
                  <View style={styles.summaryPriceRow}>
                    <Text style={styles.summaryPrice}>${result.price?.toFixed(2)}</Text>
                    {result.change_pct != null && (
                      <Text style={[styles.summaryChange, { color: result.change_pct >= 0 ? Colors.green : Colors.red }]}>
                        {result.change_pct >= 0 ? '+' : ''}{result.change_pct.toFixed(2)}%
                      </Text>
                    )}
                  </View>
                </View>
              </View>
              <View style={styles.summaryMeta}>
                <RecoBadge label={result.recommendation} />
                <Text style={styles.summaryMetaText}>
                  Confidence: <Text style={styles.summaryMetaValue}>{((result.confidence ?? 0) * 100).toFixed(0)}%</Text>
                </Text>
                <Text style={styles.summaryMetaText}>
                  Agreement: <Text style={styles.summaryMetaValue}>{result.agreement_pct?.toFixed(0) ?? '—'}%</Text>
                </Text>
              </View>
            </View>

            {/* Agent Breakdown */}
            {result.votes && result.votes.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>Agent Breakdown</Text>
                {result.votes.map((vote, i) => (
                  <AgentCard key={i} vote={vote} />
                ))}
              </>
            )}

            {/* Debate */}
            {((result.key_reasons && result.key_reasons.length > 0) ||
              (result.key_risks && result.key_risks.length > 0)) && (
              <>
                <Text style={styles.sectionTitle}>Debate</Text>
                <View style={styles.debateCard}>
                  {result.key_reasons && result.key_reasons.length > 0 && (
                    <View style={styles.caseSection}>
                      <Text style={styles.caseSectionTitle}>🐂 Bull Case</Text>
                      {result.key_reasons.map((r, i) => (
                        <Text key={i} style={styles.bulletText}>• {r}</Text>
                      ))}
                    </View>
                  )}
                  {result.key_risks && result.key_risks.length > 0 && (
                    <View style={[styles.caseSection, result.key_reasons && result.key_reasons.length > 0 && styles.caseDivider]}>
                      <Text style={styles.caseSectionTitle}>🐻 Bear Case</Text>
                      {result.key_risks.map((r, i) => (
                        <Text key={i} style={styles.bulletText}>• {r}</Text>
                      ))}
                    </View>
                  )}
                </View>
              </>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: 16, paddingBottom: 40 },

  headerTitle: { fontSize: 26, fontWeight: 'bold', color: Colors.text, marginBottom: 16 },

  searchCard: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  searchInput: {
    backgroundColor: Colors.surfaceAlt,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 10,
    height: 46,
    paddingHorizontal: 14,
    color: Colors.text,
    fontSize: 15,
    marginBottom: 10,
  },
  analyzeBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 10,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  analyzeBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  chipsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: Colors.surfaceAlt,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  chipActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  chipText: { fontSize: 12, color: Colors.textSecondary, fontWeight: '600' },
  chipTextActive: { color: '#fff' },

  center: { alignItems: 'center', paddingVertical: 40 },
  loadingText: { color: Colors.textSecondary, marginTop: 12 },

  errorBanner: {
    backgroundColor: '#3D1010',
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
  },
  errorText: { color: Colors.red, fontSize: 13 },

  emptyState: { alignItems: 'center', paddingVertical: 40 },
  emptyText: {
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    fontSize: 14,
    marginBottom: 20,
  },

  summaryCard: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  summaryTop: { marginBottom: 12 },
  summarySymbol: { fontSize: 22, fontWeight: '900', color: Colors.text },
  summaryPriceRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginTop: 4 },
  summaryPrice: { fontSize: 18, fontWeight: '700', color: Colors.text },
  summaryChange: { fontSize: 14, fontWeight: '600' },
  summaryMeta: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  summaryMetaText: { fontSize: 13, color: Colors.textSecondary },
  summaryMetaValue: { color: Colors.text, fontWeight: '600' },

  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 10,
  },

  agentCard: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  agentCardTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.text,
    marginBottom: 10,
  },
  agentScoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  scoreBarBg: {
    height: 6,
    backgroundColor: Colors.border,
    borderRadius: 3,
    overflow: 'hidden',
  },
  scoreBarFill: { height: 6, borderRadius: 3 },
  agentScoreValue: { fontSize: 13, fontWeight: '700', width: 42, textAlign: 'right' },
  reasonsList: { marginTop: 4 },
  bulletText: { fontSize: 12, color: Colors.textSecondary, lineHeight: 18, marginBottom: 3 },

  badge: { borderRadius: 4, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1 },
  badgeText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  debateCard: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  caseSection: {},
  caseDivider: {
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  caseSectionTitle: { fontSize: 14, fontWeight: '700', color: Colors.text, marginBottom: 8 },
});
