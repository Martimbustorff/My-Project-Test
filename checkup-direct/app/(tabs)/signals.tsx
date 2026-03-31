import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View, Text, FlatList, StyleSheet,
  TouchableOpacity, ActivityIndicator, ScrollView, Animated,
  useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, recColor } from '@/constants/Colors';
import { apiGet } from '@/constants/Api';

interface Signal {
  symbol: string;
  timestamp: string;
  action?: string;
  confidence?: number;
  consensus_score: number;
  recommendation: string;
  direction: string;
  agreement_pct?: number;
  technical_score?: number;
  sentiment_score?: number;
  momentum_score?: number;
  fundamental_score?: number;
  macro_score?: number;
  price?: number;
}

interface MacroData {
  regime?: string;
  vix?: number;
  yield_curve?: number;
  score_adjustment?: number;
}

interface AnalysisCache {
  key_reasons?: string[];
  key_risks?: string[];
}

type FilterType = 'all' | 'strong' | 'longs' | 'shorts';

function buildVotes(sig: Signal) {
  return [
    { name: 'Technical',   icon: '🔬', score: sig.technical_score   ?? 0 },
    { name: 'Fundamental', icon: '📊', score: sig.fundamental_score ?? 0 },
    { name: 'Momentum',    icon: '📈', score: sig.momentum_score    ?? 0 },
    { name: 'Sentiment',   icon: '📰', score: sig.sentiment_score   ?? 0 },
    { name: 'Macro',       icon: '🌍', score: sig.macro_score       ?? 0 },
  ];
}

function scoreToSignal(score: number): string {
  if (score >= 0.6)  return 'STRONG BUY';
  if (score >= 0.25) return 'BUY';
  if (score > -0.25) return 'HOLD';
  if (score > -0.6)  return 'SELL';
  return 'STRONG SELL';
}

function timeAgo(isoDate: string): { text: string; isRecent: boolean; isVeryRecent: boolean } {
  const diff = (Date.now() - new Date(isoDate).getTime()) / 1000;
  const isVeryRecent = diff < 300;
  const isRecent = diff < 3600;
  let text = '';
  if (diff < 60)       text = `${Math.floor(diff)}s ago`;
  else if (diff < 3600)  text = `${Math.floor(diff / 60)}m ago`;
  else if (diff < 86400) text = `${Math.floor(diff / 3600)}h ago`;
  else                   text = `${Math.floor(diff / 86400)}d ago`;
  return { text, isRecent, isVeryRecent };
}

function urgencyDotColor(rec: string): string {
  const u = rec.toUpperCase();
  if (u === 'STRONG BUY')  return Colors.green;
  if (u === 'STRONG SELL') return Colors.red;
  return Colors.yellow;
}

function PulsingDot({ color }: { color: string }) {
  const anim = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 0.3, duration: 700, useNativeDriver: true }),
        Animated.timing(anim, { toValue: 1,   duration: 700, useNativeDriver: true }),
      ])
    ).start();
  }, [anim]);
  return <Animated.View style={[styles.urgencyDot, { backgroundColor: color, opacity: anim }]} />;
}

function RecoBadge({ label }: { label: string }) {
  const color = recColor(label);
  return (
    <View style={[styles.badge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label.toUpperCase()}</Text>
    </View>
  );
}

function DirectionBadge({ direction }: { direction: string }) {
  const isLong = direction === 'LONG';
  const color = isLong ? Colors.green : Colors.red;
  return (
    <View style={[styles.dirBadge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.dirBadgeText, { color }]}>{direction}</Text>
    </View>
  );
}

function MiniScoreBar({ score }: { score: number }) {
  const abs = Math.abs(score);
  const color = score > 0 ? Colors.green : score < 0 ? Colors.red : Colors.textMuted;
  return (
    <View style={styles.miniBarBg}>
      <View style={[styles.miniBarFill, { width: `${Math.min(abs * 100, 100)}%` as any, backgroundColor: color }]} />
    </View>
  );
}

interface MacroStripProps {
  macro: MacroData | null;
}
function MacroStrip({ macro }: MacroStripProps) {
  if (!macro) return null;
  const regime = macro.regime ?? 'NEUTRAL';
  const regimeEmoji = regime === 'RISK ON' ? '🟢' : regime === 'RISK OFF' ? '🔴' : '🟡';
  const adj = macro.score_adjustment ?? 0;
  return (
    <View style={styles.macroStrip}>
      <Text style={styles.macroRegime}>{regimeEmoji} {regime}</Text>
      {macro.vix != null && (
        <Text style={styles.macroPill}>VIX: <Text style={styles.macroVal}>{macro.vix.toFixed(1)}</Text></Text>
      )}
      {macro.yield_curve != null && (
        <Text style={styles.macroPill}>Yield Curve: <Text style={styles.macroVal}>{macro.yield_curve.toFixed(2)}%</Text></Text>
      )}
      <Text style={[styles.macroAdj, { color: adj >= 0 ? Colors.green : Colors.red }]}>
        {adj >= 0 ? '+' : ''}{adj.toFixed(2)}
      </Text>
    </View>
  );
}

interface SignalCardProps {
  item: Signal;
  expanded: boolean;
  onPress: () => void;
  analysisCache: AnalysisCache | null;
}

function SignalCard({ item, expanded, onPress, analysisCache }: SignalCardProps) {
  const { text: timeText, isVeryRecent, isRecent } = timeAgo(item.timestamp);
  const dotColor = urgencyDotColor(item.recommendation);
  const timeColor = isVeryRecent ? Colors.text : isRecent ? Colors.textSecondary : Colors.textMuted;
  const votes = buildVotes(item);

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.85}>
      {/* Row 1: symbol + badges + time */}
      <View style={styles.cardRow1}>
        <View style={styles.cardRow1Left}>
          {isVeryRecent
            ? <PulsingDot color={dotColor} />
            : <View style={[styles.urgencyDot, { backgroundColor: dotColor }]} />
          }
          <Text style={styles.symbolText}>{item.symbol}</Text>
        </View>
        <View style={styles.cardRow1Right}>
          <RecoBadge label={item.recommendation ?? item.action ?? 'HOLD'} />
          <DirectionBadge direction={item.direction ?? 'LONG'} />
          <Text style={[styles.timestampText, { color: timeColor }]}>{timeText}</Text>
        </View>
      </View>

      {/* Row 2: score + agreement + price */}
      <View style={styles.cardRow2}>
        <Text style={styles.metaText}>
          Score:{' '}
          <Text style={{ color: (item.consensus_score ?? 0) > 0 ? Colors.green : Colors.red, fontWeight: '700' }}>
            {(item.consensus_score ?? 0).toFixed(2)}
          </Text>
        </Text>
        <Text style={styles.metaSep}>·</Text>
        <Text style={styles.metaText}>
          Agreement: <Text style={styles.metaHighlight}>{(item.agreement_pct ?? 0).toFixed(0)}%</Text>
        </Text>
        <Text style={styles.metaSep}>·</Text>
        <Text style={styles.metaText}>${(item.price ?? 0).toFixed(2)}</Text>
      </View>

      {/* Expand hint */}
      {!expanded && (
        <Text style={styles.expandHint}>Tap to expand agent breakdown ▼</Text>
      )}

      {/* Expanded */}
      {expanded && (
        <View style={styles.expandedSection}>
          <View style={styles.expandDivider} />
          <Text style={styles.sectionLabel}>Agent Votes</Text>
          {votes.map(vote => {
            const sig = scoreToSignal(vote.score);
            const color = recColor(sig);
            return (
              <View key={vote.name} style={styles.agentRow}>
                <Text style={styles.agentIcon}>{vote.icon}</Text>
                <Text style={styles.agentName}>{vote.name.padEnd(14)}</Text>
                <View style={styles.agentBarContainer}>
                  <MiniScoreBar score={vote.score} />
                </View>
                <View style={[styles.agentBadge, { backgroundColor: color + '22', borderColor: color }]}>
                  <Text style={[styles.agentBadgeText, { color }]}>{sig}</Text>
                </View>
                <Text style={[styles.agentScore, { color: vote.score > 0 ? Colors.green : vote.score < 0 ? Colors.red : Colors.textMuted }]}>
                  {vote.score >= 0 ? '+' : ''}{vote.score.toFixed(2)}
                </Text>
              </View>
            );
          })}

          {analysisCache?.key_reasons && analysisCache.key_reasons.length > 0 && (
            <View style={styles.caseSection}>
              <Text style={styles.caseSectionTitle}>🐂 Bull Case</Text>
              {analysisCache.key_reasons.map((r, i) => (
                <Text key={i} style={styles.bulletText}>• {r}</Text>
              ))}
            </View>
          )}

          {analysisCache?.key_risks && analysisCache.key_risks.length > 0 && (
            <View style={styles.caseSection}>
              <Text style={styles.caseSectionTitle}>🐻 Bear Case</Text>
              {analysisCache.key_risks.map((r, i) => (
                <Text key={i} style={styles.bulletText}>• {r}</Text>
              ))}
            </View>
          )}

          <Text style={styles.collapseHint}>Tap to collapse ▲</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

export default function SignalsScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= 900;

  const [signals, setSignals]               = useState<Signal[]>([]);
  const [macro, setMacro]                   = useState<MacroData | null>(null);
  const [loading, setLoading]               = useState(true);
  const [filter, setFilter]                 = useState<FilterType>('all');
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);
  const [analysisBySymbol, setAnalysisBySymbol] = useState<Record<string, AnalysisCache>>({});
  const [error, setError]                   = useState<string | null>(null);

  const loadMacro = useCallback(async () => {
    try {
      const data = await apiGet<MacroData>('/api/insights/macro');
      setMacro(data);
    } catch { /* non-blocking */ }
  }, []);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await apiGet<Signal[]>('/api/signals/latest?limit=50');
      const arr = Array.isArray(data) ? data : [];
      arr.sort((a, b) => Math.abs(b.consensus_score ?? 0) - Math.abs(a.consensus_score ?? 0));
      setSignals(arr);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    loadMacro();
  }, [load, loadMacro]);

  // Auto-refresh every 20 seconds
  useEffect(() => {
    const i = setInterval(() => { load(); loadMacro(); }, 20_000);
    return () => clearInterval(i);
  }, [load, loadMacro]);

  const handleCardPress = useCallback(async (symbol: string) => {
    if (expandedSymbol === symbol) {
      setExpandedSymbol(null);
      return;
    }
    setExpandedSymbol(symbol);
    if (!analysisBySymbol[symbol]) {
      try {
        const data = await apiGet<AnalysisCache>(`/api/analysis/${symbol}`);
        setAnalysisBySymbol(prev => ({ ...prev, [symbol]: data }));
      } catch {
        setAnalysisBySymbol(prev => ({ ...prev, [symbol]: {} }));
      }
    }
  }, [expandedSymbol, analysisBySymbol]);

  const displayed = signals.filter(s => {
    if (filter === 'strong') return Math.abs(s.consensus_score ?? 0) > 0.4;
    if (filter === 'longs')  return s.direction === 'LONG';
    if (filter === 'shorts') return s.direction === 'SHORT';
    return true;
  });

  const FILTERS: { key: FilterType; label: string }[] = [
    { key: 'all',    label: 'All' },
    { key: 'strong', label: 'Strong' },
    { key: 'longs',  label: 'Longs' },
    { key: 'shorts', label: 'Shorts' },
  ];

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Loading signals...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={[styles.header, isDesktop && styles.headerDesktop]}>
        <Text style={styles.headerTitle}>Signals ⚡</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
        >
          {FILTERS.map(f => (
            <TouchableOpacity
              key={f.key}
              style={[styles.filterBtn, filter === f.key && styles.filterBtnActive]}
              onPress={() => setFilter(f.key)}
            >
              <Text style={[styles.filterText, filter === f.key && styles.filterTextActive]}>
                {f.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Macro strip */}
      <MacroStrip macro={macro} />

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>
            {error === 'UNAUTHORIZED' ? 'Session expired — please log in again' : 'Could not reach API server'}
          </Text>
        </View>
      )}

      <FlatList
        data={displayed}
        keyExtractor={item => item.symbol + item.timestamp}
        contentContainerStyle={[styles.listContent, isDesktop && styles.listContentDesktop]}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>🔭</Text>
            <Text style={styles.emptyText}>No signals yet — run a market scan first</Text>
          </View>
        }
        renderItem={({ item }) => (
          <SignalCard
            item={item}
            expanded={expandedSymbol === item.symbol}
            onPress={() => handleCardPress(item.symbol)}
            analysisCache={analysisBySymbol[item.symbol] ?? null}
          />
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: Colors.textSecondary, marginTop: 12 },

  header: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 8,
  },
  headerDesktop: { paddingHorizontal: 24 },
  headerTitle: { fontSize: 24, fontWeight: 'bold', color: Colors.text },

  filterRow: { paddingVertical: 2, gap: 6 },
  filterBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  filterBtnActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  filterText: { fontSize: 12, color: Colors.textSecondary, fontWeight: '600' },
  filterTextActive: { color: '#fff' },

  macroStrip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    flexWrap: 'wrap',
  },
  macroRegime: { fontSize: 12, fontWeight: '700', color: Colors.text },
  macroPill: { fontSize: 11, color: Colors.textSecondary },
  macroVal: { color: Colors.text, fontWeight: '600' },
  macroAdj: { fontSize: 11, fontWeight: '700', marginLeft: 'auto' },

  errorBanner: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: '#3D1010',
    borderRadius: 8,
    padding: 12,
  },
  errorText: { color: Colors.red, fontSize: 13 },

  listContent: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 40 },
  listContentDesktop: { paddingHorizontal: 24, maxWidth: 900, alignSelf: 'center' as any, width: '100%' },

  empty: { alignItems: 'center', paddingTop: 60, gap: 12 },
  emptyIcon: { fontSize: 40 },
  emptyText: { color: Colors.textSecondary, textAlign: 'center', lineHeight: 22, fontSize: 14 },

  card: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardRow1: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
    flexWrap: 'wrap',
    gap: 6,
  },
  cardRow1Left: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardRow1Right: { flexDirection: 'row', gap: 6, alignItems: 'center', flexWrap: 'wrap' },
  urgencyDot: { width: 10, height: 10, borderRadius: 5 },
  symbolText: { fontSize: 18, fontWeight: '800', color: Colors.text },

  badge: { borderRadius: 4, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1 },
  badgeText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  dirBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, borderWidth: 1 },
  dirBadgeText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },

  cardRow2: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' },
  metaText: { fontSize: 12, color: Colors.textSecondary },
  metaSep: { fontSize: 12, color: Colors.textMuted },
  metaHighlight: { color: Colors.text, fontWeight: '600' },

  timestampText: { fontSize: 11, fontWeight: '600' },

  expandHint: { fontSize: 10, color: Colors.textMuted, marginTop: 6, textAlign: 'right' },

  expandedSection: { marginTop: 4 },
  expandDivider: { height: 1, backgroundColor: Colors.border, marginVertical: 12 },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 10,
  },

  agentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 6,
  },
  agentIcon: { fontSize: 14, width: 20 },
  agentName: { fontSize: 11, color: Colors.textSecondary, width: 88, fontFamily: 'monospace' },
  agentBarContainer: { flex: 1 },
  miniBarBg: {
    height: 5,
    backgroundColor: Colors.border,
    borderRadius: 3,
    overflow: 'hidden',
  },
  miniBarFill: { height: 5, borderRadius: 3 },
  agentBadge: {
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderWidth: 1,
    minWidth: 72,
    alignItems: 'center',
  },
  agentBadgeText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.3 },
  agentScore: { fontSize: 11, fontWeight: '600', width: 38, textAlign: 'right' },

  caseSection: { marginTop: 12 },
  caseSectionTitle: { fontSize: 13, fontWeight: '700', color: Colors.text, marginBottom: 6 },
  bulletText: { fontSize: 12, color: Colors.textSecondary, lineHeight: 18, marginBottom: 3 },

  collapseHint: { fontSize: 10, color: Colors.textMuted, marginTop: 10, textAlign: 'right' },
});
