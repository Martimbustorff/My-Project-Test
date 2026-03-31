import React, { useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  TextInput, ActivityIndicator, useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, recColor } from '@/constants/Colors';
import { Gauge } from '@/components/Gauge';
import { apiGet } from '@/constants/Api';

interface AgentVote {
  agent_name: string;
  score: number;
  confidence: number;
  signal: string;
  reasons: string[];
  weight: number;
}

interface DebateResult {
  debate_summary?: string;
  key_risk?: string;
  key_catalyst?: string;
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
  debate_result?: DebateResult;
}

const QUICK_SYMBOLS = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'BTC-USD', 'ETH-USD', 'SPY'];

const AGENT_ICONS: Record<string, string> = {
  Technical:   '🔬',
  Fundamental: '📊',
  Momentum:    '📈',
  Sentiment:   '📰',
  Macro:       '🌍',
};

function RecoBadge({ label }: { label: string }) {
  const color = recColor(label);
  return (
    <View style={[styles.badge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label.toUpperCase()}</Text>
    </View>
  );
}

function AgentCard({ vote, isDesktop }: { vote: AgentVote; isDesktop: boolean }) {
  const color = vote.score > 0 ? Colors.green : vote.score < 0 ? Colors.red : Colors.yellow;
  const icon = AGENT_ICONS[vote.agent_name] ?? '🤖';
  const abs = Math.abs(vote.score ?? 0);
  const widthPct = `${Math.min(abs * 100, 100)}%` as any;

  return (
    <View style={styles.agentCard}>
      {/* Header row */}
      <View style={styles.agentCardHeader}>
        <Text style={styles.agentCardTitle}>
          {icon} {vote.agent_name}
        </Text>
        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
          <View style={[styles.badge, { backgroundColor: color + '22', borderColor: color }]}>
            <Text style={[styles.badgeText, { color }]}>{vote.signal ?? scoreToRec(vote.score ?? 0)}</Text>
          </View>
          <Text style={[styles.agentScoreValue, { color }]}>
            {(vote.score ?? 0) >= 0 ? '+' : ''}{(vote.score ?? 0).toFixed(2)}
          </Text>
        </View>
      </View>

      {/* Score bar — layered track + fill + accent */}
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: widthPct, backgroundColor: color + '55' }]} />
        <View style={[styles.barAccent, { width: widthPct, backgroundColor: color }]} />
      </View>

      {/* Reasons */}
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

function scoreToRec(score: number): string {
  if (score >= 0.6)  return 'STRONG BUY';
  if (score >= 0.25) return 'BUY';
  if (score > -0.25) return 'HOLD';
  if (score > -0.6)  return 'SELL';
  return 'STRONG SELL';
}

export default function AnalysisScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= 900;

  const [symbol, setSymbol]   = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult]   = useState<AnalysisResult | null>(null);
  const [error, setError]     = useState<string | null>(null);

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
      setError(e.message === 'UNAUTHORIZED' ? 'Session expired' : (e.message ?? 'Unknown error'));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleAnalyze = () => analyze(symbol);

  // Desktop: left/right split layout
  if (isDesktop) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.desktopLayout}>
          {/* LEFT PANEL */}
          <ScrollView
            style={styles.leftPanel}
            contentContainerStyle={styles.leftPanelContent}
            keyboardShouldPersistTaps="handled"
          >
            <Text style={styles.headerTitle}>Analysis 🔬</Text>

            {/* Search */}
            <View style={styles.searchCard}>
              <TextInput
                style={styles.searchInput}
                value={symbol}
                onChangeText={setSymbol}
                autoCapitalize="characters"
                placeholder="e.g. AAPL, BTC-USD"
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

            {loading && (
              <View style={styles.center}>
                <ActivityIndicator size="large" color={Colors.primary} />
                <Text style={styles.loadingText}>Consulting 5 agents...</Text>
              </View>
            )}

            {error && !loading && (
              <View style={styles.errorBanner}>
                <Text style={styles.errorText}>Error: {error}</Text>
                <TouchableOpacity onPress={handleAnalyze} style={styles.retryBtn}>
                  <Text style={styles.retryBtnText}>Retry</Text>
                </TouchableOpacity>
              </View>
            )}

            {result && !loading && (
              <>
                {/* Summary card */}
                <View style={styles.summaryCard}>
                  <Text style={styles.summarySymbol}>{result.symbol}</Text>
                  <View style={styles.summaryPriceRow}>
                    <Text style={styles.summaryPrice}>${(result.price ?? 0).toFixed(2)}</Text>
                    {result.change_pct != null && (
                      <Text style={[styles.summaryChange, { color: result.change_pct >= 0 ? Colors.green : Colors.red }]}>
                        {result.change_pct >= 0 ? '▲' : '▼'} {Math.abs(result.change_pct).toFixed(2)}%
                      </Text>
                    )}
                  </View>
                  <View style={styles.summaryMeta}>
                    <RecoBadge label={result.recommendation ?? 'HOLD'} />
                    <Text style={styles.summaryMetaText}>
                      Confidence: <Text style={styles.summaryMetaValue}>{((result.confidence ?? 0) * 100).toFixed(0)}%</Text>
                    </Text>
                    <Text style={styles.summaryMetaText}>
                      Agreement: <Text style={styles.summaryMetaValue}>{(result.agreement_pct ?? 0).toFixed(0)}%</Text>
                    </Text>
                  </View>
                </View>

                {/* Gauge */}
                <View style={styles.gaugeContainer}>
                  <Gauge
                    score={result.consensus_score ?? 0}
                    recommendation={result.recommendation ?? 'HOLD'}
                    size={160}
                  />
                </View>

                {/* Bull / Bear cases */}
                {(result.key_reasons?.length > 0 || result.key_risks?.length > 0) && (
                  <View style={styles.casesCard}>
                    {result.key_reasons && result.key_reasons.length > 0 && (
                      <View style={styles.caseSection}>
                        <Text style={styles.caseSectionTitle}>🐂 Bull Case</Text>
                        {result.key_reasons.map((r, i) => (
                          <Text key={i} style={styles.bulletText}>• {r}</Text>
                        ))}
                      </View>
                    )}
                    {result.key_risks && result.key_risks.length > 0 && (
                      <View style={[styles.caseSection, result.key_reasons?.length > 0 && styles.caseDivider]}>
                        <Text style={styles.caseSectionTitle}>🐻 Bear Case</Text>
                        {result.key_risks.map((r, i) => (
                          <Text key={i} style={styles.bulletText}>• {r}</Text>
                        ))}
                      </View>
                    )}
                  </View>
                )}
              </>
            )}

            {!loading && !error && !result && (
              <View style={styles.emptyState}>
                <Text style={styles.emptyText}>
                  Enter a symbol above to run a full multi-agent analysis
                </Text>
              </View>
            )}
          </ScrollView>

          {/* RIGHT PANEL */}
          <ScrollView style={styles.rightPanel} contentContainerStyle={styles.rightPanelContent}>
            {result && !loading ? (
              <>
                <Text style={styles.sectionTitle}>Agent Breakdown</Text>
                {result.votes && result.votes.length > 0
                  ? result.votes.map((vote, i) => (
                      <AgentCard key={i} vote={vote} isDesktop={isDesktop} />
                    ))
                  : <Text style={styles.noDataText}>No agent votes available</Text>
                }

                {result.debate_result && (
                  <>
                    <Text style={[styles.sectionTitle, { marginTop: 20 }]}>Debate Summary</Text>
                    <View style={styles.debateCard}>
                      <Text style={styles.debateTitle}>🤖 Claude's Analysis</Text>
                      {result.debate_result.debate_summary ? (
                        <Text style={styles.debateSummary}>{result.debate_result.debate_summary}</Text>
                      ) : null}
                      {result.debate_result.key_risk ? (
                        <Text style={styles.debateRisk}>⚠ {result.debate_result.key_risk}</Text>
                      ) : null}
                      {result.debate_result.key_catalyst ? (
                        <Text style={styles.debateCatalyst}>🚀 {result.debate_result.key_catalyst}</Text>
                      ) : null}
                    </View>
                  </>
                )}
              </>
            ) : (
              <View style={styles.rightEmptyState}>
                <Text style={styles.rightEmptyText}>
                  {loading ? 'Analysis in progress...' : 'Agent breakdown will appear here'}
                </Text>
              </View>
            )}
          </ScrollView>
        </View>
      </SafeAreaView>
    );
  }

  // Mobile: single column
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <Text style={styles.headerTitle}>Analysis 🔬</Text>

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

        {loading && (
          <View style={styles.center}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.loadingText}>Consulting 5 agents...</Text>
          </View>
        )}

        {error && !loading && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>Error: {error}</Text>
            <TouchableOpacity onPress={handleAnalyze} style={styles.retryBtn}>
              <Text style={styles.retryBtnText}>Retry</Text>
            </TouchableOpacity>
          </View>
        )}

        {!loading && !error && !result && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>
              Enter a stock symbol above to get a full multi-agent analysis
            </Text>
          </View>
        )}

        {result && !loading && (
          <>
            {/* Summary */}
            <View style={styles.summaryCard}>
              <Text style={styles.summarySymbol}>{result.symbol}</Text>
              <View style={styles.summaryPriceRow}>
                <Text style={styles.summaryPrice}>${(result.price ?? 0).toFixed(2)}</Text>
                {result.change_pct != null && (
                  <Text style={[styles.summaryChange, { color: result.change_pct >= 0 ? Colors.green : Colors.red }]}>
                    {result.change_pct >= 0 ? '▲' : '▼'} {Math.abs(result.change_pct).toFixed(2)}%
                  </Text>
                )}
              </View>
              <View style={styles.summaryMeta}>
                <RecoBadge label={result.recommendation ?? 'HOLD'} />
                <Text style={styles.summaryMetaText}>
                  Confidence: <Text style={styles.summaryMetaValue}>{((result.confidence ?? 0) * 100).toFixed(0)}%</Text>
                </Text>
                <Text style={styles.summaryMetaText}>
                  Agreement: <Text style={styles.summaryMetaValue}>{(result.agreement_pct ?? 0).toFixed(0)}%</Text>
                </Text>
              </View>
            </View>

            {/* Gauge centered */}
            <View style={styles.gaugeContainer}>
              <Gauge
                score={result.consensus_score ?? 0}
                recommendation={result.recommendation ?? 'HOLD'}
                size={140}
              />
            </View>

            {/* Agent breakdown */}
            {result.votes && result.votes.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>Agent Breakdown</Text>
                {result.votes.map((vote, i) => (
                  <AgentCard key={i} vote={vote} isDesktop={isDesktop} />
                ))}
              </>
            )}

            {/* Debate */}
            {result.debate_result && (
              <>
                <Text style={styles.sectionTitle}>Debate Summary</Text>
                <View style={styles.debateCard}>
                  <Text style={styles.debateTitle}>🤖 Claude's Analysis</Text>
                  {result.debate_result.debate_summary ? (
                    <Text style={styles.debateSummary}>{result.debate_result.debate_summary}</Text>
                  ) : null}
                  {result.debate_result.key_risk ? (
                    <Text style={styles.debateRisk}>⚠ {result.debate_result.key_risk}</Text>
                  ) : null}
                  {result.debate_result.key_catalyst ? (
                    <Text style={styles.debateCatalyst}>🚀 {result.debate_result.key_catalyst}</Text>
                  ) : null}
                </View>
              </>
            )}

            {/* Bull / Bear */}
            {(result.key_reasons?.length > 0 || result.key_risks?.length > 0) && (
              <>
                <Text style={styles.sectionTitle}>Debate</Text>
                <View style={styles.casesCard}>
                  {result.key_reasons && result.key_reasons.length > 0 && (
                    <View style={styles.caseSection}>
                      <Text style={styles.caseSectionTitle}>🐂 Bull Case</Text>
                      {result.key_reasons.map((r, i) => (
                        <Text key={i} style={styles.bulletText}>• {r}</Text>
                      ))}
                    </View>
                  )}
                  {result.key_risks && result.key_risks.length > 0 && (
                    <View style={[styles.caseSection, result.key_reasons?.length > 0 && styles.caseDivider]}>
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

  // Desktop split layout
  desktopLayout: { flex: 1, flexDirection: 'row' },
  leftPanel: { width: '40%', borderRightWidth: 1, borderRightColor: Colors.border },
  leftPanelContent: { padding: 24, paddingBottom: 40 },
  rightPanel: { flex: 1 },
  rightPanelContent: { padding: 24, paddingBottom: 40 },

  rightEmptyState: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80 },
  rightEmptyText: { color: Colors.textMuted, fontSize: 14, textAlign: 'center' },

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
  loadingText: { color: Colors.textSecondary, marginTop: 12, fontSize: 14 },

  errorBanner: {
    backgroundColor: '#3D1010',
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
    gap: 10,
  },
  errorText: { color: Colors.red, fontSize: 13 },
  retryBtn: {
    backgroundColor: Colors.red + '33',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
    alignSelf: 'flex-start',
  },
  retryBtnText: { color: Colors.red, fontSize: 13, fontWeight: '700' },

  emptyState: { alignItems: 'center', paddingVertical: 40 },
  emptyText: {
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    fontSize: 14,
    marginBottom: 20,
  },
  noDataText: { color: Colors.textMuted, fontSize: 13, textAlign: 'center', paddingVertical: 20 },

  summaryCard: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  summarySymbol: { fontSize: 22, fontWeight: '900', color: Colors.text },
  summaryPriceRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginTop: 4, marginBottom: 12 },
  summaryPrice: { fontSize: 18, fontWeight: '700', color: Colors.text },
  summaryChange: { fontSize: 14, fontWeight: '600' },
  summaryMeta: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  summaryMetaText: { fontSize: 13, color: Colors.textSecondary },
  summaryMetaValue: { color: Colors.text, fontWeight: '600' },

  gaugeContainer: { alignItems: 'center', marginVertical: 20 },

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
  agentCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  agentCardTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.text,
  },
  agentScoreValue: { fontSize: 13, fontWeight: '700', width: 42, textAlign: 'right' },

  barTrack: {
    height: 8,
    backgroundColor: Colors.border,
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 10,
    position: 'relative',
  },
  barFill: {
    position: 'absolute',
    top: 0,
    left: 0,
    bottom: 0,
    borderRadius: 4,
  },
  barAccent: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    height: 2,
    borderRadius: 1,
  },

  reasonsList: { marginTop: 4 },
  bulletText: { fontSize: 12, color: Colors.textSecondary, lineHeight: 18, marginBottom: 3 },

  badge: { borderRadius: 4, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1 },
  badgeText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  casesCard: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 16,
    marginBottom: 16,
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

  debateCard: {
    backgroundColor: Colors.surfaceAlt,
    borderRadius: 14,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.primary + '44',
    gap: 8,
  },
  debateTitle: { fontSize: 14, fontWeight: '700', color: Colors.primary, marginBottom: 4 },
  debateSummary: { fontSize: 13, color: Colors.text, lineHeight: 20 },
  debateRisk: { fontSize: 13, color: Colors.red, lineHeight: 20 },
  debateCatalyst: { fontSize: 13, color: Colors.green, lineHeight: 20 },
});
